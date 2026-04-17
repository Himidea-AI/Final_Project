"""
전체 마포구 행정동 입지 랭킹 에이전트

LLM 없이 Python 연산만으로 16개 행정동을 정량 점수화하여 순위를 산출합니다.
market / population / legal 에이전트와 asyncio.gather로 병렬 실행됩니다.

점수 산식 (100점 만점, 동적 가중치):
  population_weight=True  (기본): 매출 35% + 인구 45% + 임대료 20%
  population_weight=False       : 매출 50% + 인구 10% + 임대료 40%

추가 패널티:
  - 임대료 예산 초과: 1.5배 초과 시 -50%, 1~1.5배 초과 시 비례 감점
  - 공실률 패널티: 5~10% → -15%, 10%+ → -30% (네이버 부동산 월세 매물 기준, 2026-04)
"""

import asyncio
import json
import redis.asyncio as aioredis
from sqlalchemy import select, func
from src.schemas.state import AgentState
from src.config.constants import MAPO_DISTRICTS
from src.config.settings import settings
from src.agents.nodes.market_analyst import db_client, market_tool
from src.database.models import NaverVacancy, StoreQuarterly

_CACHE_TTL = 86400  # 24시간


async def _load_vacancy_map() -> tuple[dict[str, float], bool]:
    """
    동별 공실률 계산 (2026-04 기준 네이버 부동산 월세 매물)

    공실률 = 월세 매물 수 / 최신 분기 영업 점포 수 * 100
    store_quarterly 최신 분기 기준 (방법 B — 더 정확)

    Returns:
        (vacancy_rate_map, success): DB 로드 성공 여부 플래그 포함.
        성공 시 success=True, 실패 시 빈 dict + success=False
        (프론트/응답에서 '공실 데이터 반영됨' vs '공실 미반영' 구분 표시용)
    """
    try:
        async with db_client.get_session() as session:
            # 1) 동별 월세 매물 수 합산
            vacancy_stmt = (
                select(NaverVacancy.dong_name, func.sum(NaverVacancy.listing_count).label("wolse_count"))
                .where(NaverVacancy.trade_type == "월세")
                .group_by(NaverVacancy.dong_name)
            )
            vacancy_rows = (await session.execute(vacancy_stmt)).fetchall()
            wolse_map = {r.dong_name: int(r.wolse_count) for r in vacancy_rows}

            # 2) 동별 최신 분기 영업 점포 수
            max_quarter_stmt = select(func.max(StoreQuarterly.quarter))
            max_quarter = (await session.execute(max_quarter_stmt)).scalar()

            store_stmt = (
                select(StoreQuarterly.dong_name, func.sum(StoreQuarterly.store_count).label("store_count"))
                .where(StoreQuarterly.quarter == max_quarter)
                .group_by(StoreQuarterly.dong_name)
            )
            store_rows = (await session.execute(store_stmt)).fetchall()
            store_map = {r.dong_name: int(r.store_count) for r in store_rows if r.store_count}

        # 3) 공실률 계산
        vacancy_rate_map: dict[str, float] = {}
        for dong in MAPO_DISTRICTS:
            wolse = wolse_map.get(dong, 0)
            store_count = store_map.get(dong, 0)
            if store_count > 0:
                vacancy_rate_map[dong] = round(wolse / store_count * 100, 2)
            else:
                vacancy_rate_map[dong] = 0.0

        print(
            f"[district_ranking] 공실률 로드 완료 — 상위 3개: "
            f"{sorted(vacancy_rate_map.items(), key=lambda x: -x[1])[:3]}"
        )
        return vacancy_rate_map, True

    except Exception as e:
        print(f"[district_ranking] 공실률 로드 실패 (패널티 비활성화): {e}")
        return {}, False


async def _score_single_district(dong_name: str, business_type: str) -> dict:
    """단일 행정동 원시 지표 수집 (예외 발생 시 0 반환)"""
    try:
        sales_data, pop_data, rent_data = await asyncio.gather(
            market_tool.get_commercial_insights(dong_name, business_type),
            market_tool.get_population_trends(dong_name),
            market_tool.get_rent_insight(dong_name),
            return_exceptions=True,
        )

        sales_growth = 0.0
        if not isinstance(sales_data, Exception) and "error" not in (sales_data or {}):
            sales_growth = float(sales_data.get("qoq_growth") or 0)

        pop_growth = 0.0
        if not isinstance(pop_data, Exception) and "error" not in (pop_data or {}):
            pop_growth = float(pop_data.get("qoq_growth") or 0)

        avg_rent = 0.0
        if not isinstance(rent_data, Exception) and "error" not in (rent_data or {}):
            avg_rent = float(rent_data.get("avg_rent_3_3m2") or 0)

        return {
            "district": dong_name,
            "sales_growth": round(sales_growth, 2),
            "pop_growth": round(pop_growth, 2),
            "avg_rent": avg_rent,
        }
    except Exception as e:
        print(f"[district_ranking] {dong_name} 점수 산출 실패 (무시): {e}")
        return {"district": dong_name, "sales_growth": 0.0, "pop_growth": 0.0, "avg_rent": 0.0}


def _normalize_and_rank(
    raw: list[dict],
    population_weight: bool = True,
    monthly_rent_budget: int = 0,
    store_area: float = 15.0,
    vacancy_rate_map: dict[str, float] | None = None,
) -> list[dict]:
    """
    16개 동의 원시 지표를 0~100으로 정규화 후 가중 합산 → 내림차순 정렬

    population_weight=True  : 매출35% + 인구45% + 임대료20%
    population_weight=False : 매출50% + 인구10% + 임대료40%
    monthly_rent_budget > 0 : 예산 초과 동에 페널티 적용
    vacancy_rate_map        : 공실률 높은 동 추가 패널티 (5~10%: -15%, 10%+: -30%)
    """
    if not raw:
        return []

    vacancy_rate_map = vacancy_rate_map or {}

    # 동적 가중치
    if population_weight:
        w_sales, w_pop, w_rent = 0.35, 0.45, 0.20
    else:
        w_sales, w_pop, w_rent = 0.50, 0.10, 0.40

    # 예산 기반 평당 허용 임대료 계산 (0이면 필터 비활성화)
    budget_per_3_3m2 = (monthly_rent_budget / max(store_area, 1)) if monthly_rent_budget > 0 else 0

    def _minmax(vals: list[float], reverse: bool = False) -> list[float]:
        lo, hi = min(vals), max(vals)
        if hi == lo:
            return [50.0] * len(vals)
        norm = [(v - lo) / (hi - lo) * 100 for v in vals]
        return [100 - n for n in norm] if reverse else norm

    sales_norm = _minmax([r["sales_growth"] for r in raw])
    pop_norm = _minmax([r["pop_growth"] for r in raw])
    rent_norm = _minmax([r["avg_rent"] for r in raw], reverse=True)  # 낮은 임대료 = 높은 점수

    ranked = []
    for i, r in enumerate(raw):
        score = sales_norm[i] * w_sales + pop_norm[i] * w_pop + rent_norm[i] * w_rent

        # 예산 초과 페널티
        if budget_per_3_3m2 > 0 and r["avg_rent"] > 0:
            if r["avg_rent"] > budget_per_3_3m2 * 1.5:
                score *= 0.5
            elif r["avg_rent"] > budget_per_3_3m2:
                ratio = r["avg_rent"] / budget_per_3_3m2
                score *= max(1.0 - (ratio - 1.0) * 0.5, 0.5)

        # 공실률 패널티: 높은 공실 = 상권 활력 저하
        vacancy_rate = vacancy_rate_map.get(r["district"], 0.0)
        if vacancy_rate >= 10.0:
            score *= 0.70  # 공실률 10% 이상: -30%
        elif vacancy_rate >= 5.0:
            score *= 0.85  # 공실률 5~10%: -15%

        ranked.append(
            {
                **r,
                "score": round(score, 1),
                "sales_score": round(sales_norm[i], 1),
                "pop_score": round(pop_norm[i], 1),
                "rent_score": round(rent_norm[i], 1),
                "vacancy_rate": vacancy_rate,  # 프론트엔드 표시용
            }
        )

    ranked.sort(key=lambda x: x["score"], reverse=True)

    for idx, item in enumerate(ranked):
        item["rank"] = idx + 1

    return ranked


async def district_ranking_node(state: AgentState) -> dict:
    """
    마포구 16개 행정동 전수 스코어링 노드

    market / population / legal 에이전트와 함께 asyncio.gather로 병렬 실행됩니다.
    결과:
      scouting_results  : 점수 내림차순 전체 랭킹 리스트 (vacancy_rate 포함)
      winner_district   : 1순위 행정동
      top_3_candidates  : 2~4순위 행정동 리스트
    """
    business_type = state.get("business_type", "카페")
    population_weight = state.get("population_weight", True)
    monthly_rent_budget = state.get("monthly_rent_budget", 0)
    store_area = state.get("store_area", 15.0)

    # Redis 캐시 조회 — 동일 조건 재요청 시 DB 쿼리 없이 즉시 반환
    cache_key = f"v2:ranking:{business_type}:{population_weight}:{monthly_rent_budget}:{store_area}"
    _redis = None
    try:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        cached = await _redis.get(cache_key)
        if cached:
            cached_data = json.loads(cached)
            print(f"[district_ranking] 캐시 히트: {cache_key}")
            await _redis.aclose()
            return {
                "scouting_results": cached_data["scouting_results"],
                "winner_district": cached_data["winner_district"],
                "top_3_candidates": cached_data["top_3_candidates"],
                "vacancy_applied": cached_data["vacancy_applied"],
                "current_agent": "district_ranking",
            }
    except Exception as e:
        print(f"[district_ranking] Redis 캐시 조회 실패 (무시하고 계속): {e}")
        if _redis is not None:
            try:
                await _redis.aclose()
            except Exception:
                pass
        _redis = None

    print(
        f"--- [DISTRICT RANKING] 마포구 {len(MAPO_DISTRICTS)}개 행정동 스코어링 시작 "
        f"(인구가중치={population_weight}, 예산={monthly_rent_budget:,}원, 면적={store_area}평) ---"
    )

    if db_client.engine is None:
        await db_client.connect()

    # 16개 동 점수 + 공실률 병렬 로드
    tasks = [_score_single_district(dong, business_type) for dong in MAPO_DISTRICTS]
    raw_scores, vacancy_result = await asyncio.gather(
        asyncio.gather(*tasks),
        _load_vacancy_map(),
    )
    vacancy_rate_map, vacancy_applied = vacancy_result

    ranked = _normalize_and_rank(
        list(raw_scores),
        population_weight=population_weight,
        monthly_rent_budget=monthly_rent_budget,
        store_area=store_area,
        vacancy_rate_map=vacancy_rate_map,
    )

    winner = ranked[0]["district"] if ranked else state.get("target_district", "서교동")
    top_3 = [r["district"] for r in ranked[1:4]]

    print(f"--- [DISTRICT RANKING] 완료 — 1위: {winner}, 후보: {top_3}, 공실반영={vacancy_applied} ---")

    # Redis 캐시 저장
    if _redis is not None:
        try:
            await _redis.set(
                cache_key,
                json.dumps(
                    {
                        "scouting_results": ranked,
                        "winner_district": winner,
                        "top_3_candidates": top_3,
                        "vacancy_applied": vacancy_applied,
                    },
                    ensure_ascii=False,
                ),
                ex=_CACHE_TTL,
            )
            print(f"[district_ranking] 캐시 저장: {cache_key} (TTL: {_CACHE_TTL}s)")
        except Exception as e:
            print(f"[district_ranking] Redis 캐시 저장 실패 (무시): {e}")
        finally:
            try:
                await _redis.aclose()
            except Exception:
                pass

    return {
        "scouting_results": ranked,
        "winner_district": winner,
        "top_3_candidates": top_3,
        "vacancy_applied": vacancy_applied,  # 공실 DB 로드 성공 여부
        "current_agent": "district_ranking",
    }
