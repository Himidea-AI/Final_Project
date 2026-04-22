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
  - 용도지역 패널티: danger(영업 제한) → -50%, caution(회색지역) → -15%
"""

import asyncio
import json
import logging
import redis.asyncio as aioredis
from sqlalchemy import select, func

logger = logging.getLogger(__name__)
from src.schemas.state import AgentState
from src.config.constants import BIZ_NORMALIZE, BIZ_TYPE_LABEL, DISTRICT_ZONE_MAP, MAPO_DISTRICTS, ZONING_RULES
from src.config.settings import settings
from src.agents.nodes._attribution_helpers import build_attribution
from src.agents.nodes.market_analyst import db_client, market_tool
from src.database.models import NaverVacancy, StoreQuarterly
from src.services.population_api import MAPO_DONG_CODES

_CACHE_TTL = 86400  # 24시간

# ── SEMAS / NAVER 클라이언트 (싱글톤, API 키 없으면 None) ──
_semas_client = None
_naver_client = None


def _init_optional_clients():
    """API 키가 있을 때만 클라이언트 생성 (서버 시작 시 1회)"""
    global _semas_client, _naver_client
    if _semas_client is None and settings.semas_api_key:
        from src.services.semas_api import SemasAPIClient

        _semas_client = SemasAPIClient(api_key=settings.semas_api_key)
    if _naver_client is None and settings.naver_client_id and settings.naver_client_secret:
        from src.services.sns_trend import NaverTrendClient

        _naver_client = NaverTrendClient(
            client_id=settings.naver_client_id,
            client_secret=settings.naver_client_secret,
        )


async def _load_vacancy_spots(dong_names: list[str]) -> list[dict]:
    """
    지정 동들의 실제 공실 좌표 목록 반환 (월세 매물, 좌표 유효한 것만)

    Returns: [{id, lat, lon, dong_name, listing_count}, ...]
    """
    try:
        async with db_client.get_session() as session:
            stmt = select(
                NaverVacancy.id,
                NaverVacancy.lat,
                NaverVacancy.lon,
                NaverVacancy.dong_name,
                NaverVacancy.listing_count,
            ).where(
                NaverVacancy.trade_type == "월세",
                NaverVacancy.dong_name.in_(dong_names),
                NaverVacancy.lat.isnot(None),
                NaverVacancy.lon.isnot(None),
            )
            rows = (await session.execute(stmt)).fetchall()
        spots = [
            {
                "id": r.id,
                "lat": r.lat,
                "lon": r.lon,
                "dong_name": r.dong_name,
                "listing_count": r.listing_count or 1,
            }
            for r in rows
        ]
        logger.info(f"[district_ranking] 공실 스팟 {len(spots)}개 로드 (동: {dong_names})")
        return spots
    except Exception as e:
        logger.warning(f"[district_ranking] 공실 스팟 로드 실패: {e}")
        return []


# 동일 invocation 내 중복 DB 쿼리 방지용 비동기 Task 공유 dict.
# district_ranking_node와 population_analyst_node가 asyncio.gather로 병렬 실행되어
# 동일 target_district에 대해 market_tool.get_population_trends를 두 번 호출하는 문제를 막는다.
# parallel_analysis_node 진입 시 _clear_shared_population_cache()로 초기화.
_pop_trends_tasks: dict[str, asyncio.Task] = {}

# DB 커넥션 풀 고갈 방지 — 16개 동 동시 조회 시 pool_size(3)+overflow(5)=8 초과 방지
_db_semaphore = asyncio.Semaphore(4)


async def _safe_population_trends(dong: str) -> dict:
    """get_population_trends를 호출하되 exception 시 빈 dict 반환 (다른 awaiter 보호)."""
    try:
        return await market_tool.get_population_trends(dong)
    except Exception as e:
        logger.warning(f"[shared_population_trends] {dong} 인구 데이터 조회 실패: {e}")
        return {"error": str(e)}


def shared_population_trends(dong: str) -> asyncio.Task:
    """동일 dong에 대한 get_population_trends 호출을 단일 Task로 dedupe.

    첫 호출자가 Task를 생성하고, 같은 dong에 대한 후속 호출자는 같은 Task를 await한다.
    asyncio는 cooperative multitasking이므로 if-check와 dict 할당 사이에 race condition은 없다.
    _safe_population_trends로 감싸서 exception이 다른 awaiter에 전파되지 않음.
    """
    if dong not in _pop_trends_tasks:
        _pop_trends_tasks[dong] = asyncio.create_task(_safe_population_trends(dong))
    return _pop_trends_tasks[dong]


def _clear_shared_population_cache() -> None:
    """parallel_analysis_node 진입 시 호출 — 요청 간 Task 누적 방지."""
    _pop_trends_tasks.clear()


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

        # 3) 공실률 계산 — 점포 데이터 없는 동은 0.0이 아닌 미반영 처리
        vacancy_rate_map: dict[str, float] = {}
        for dong in MAPO_DISTRICTS:
            wolse = wolse_map.get(dong, 0)
            store_count = store_map.get(dong, 0)
            if store_count > 0:
                vacancy_rate_map[dong] = round(wolse / store_count * 100, 2)
            # store_count=0이면 vacancy_rate_map에 미포함 → 패널티 0 (데이터 부재와 0% 구분)

        logger.info(
            f"[district_ranking] 공실률 로드 완료 - 상위 3개: "
            f"{sorted(vacancy_rate_map.items(), key=lambda x: -x[1])[:3]}"
        )
        return vacancy_rate_map, True

    except Exception as e:
        logger.warning(f"[district_ranking] 공실률 로드 실패 (패널티 비활성화): {e}")
        return {}, False


async def _fetch_semas_density(dong_name: str, business_type: str) -> int | None:
    """SEMAS API — 행정동 업종 밀집도 (점포 수). API 키 없거나 실패 시 None."""
    if _semas_client is None:
        return None
    try:
        dong_code = MAPO_DONG_CODES.get(dong_name)
        if not dong_code:
            return None
        biz_code = {"카페": "Q01A01", "음식점": "Q01A02", "편의점": "Q02A01"}.get(
            BIZ_TYPE_LABEL.get(business_type.lower(), business_type), "Q01"
        )
        result = await _semas_client.get_business_density(dong_code, biz_code)
        items = result.get("items", [])
        return sum(item.get("store_count", 0) for item in items) if items else None
    except Exception as e:
        logger.debug(f"[district_ranking] SEMAS 밀집도 조회 실패 ({dong_name}): {e}")
        return None


async def _fetch_naver_trend(dong_name: str, business_type: str) -> float | None:
    """NAVER DataLab — 동+업종 검색 트렌드 성장률(%). API 키 없거나 실패 시 None."""
    if _naver_client is None:
        return None
    try:
        biz_label = BIZ_TYPE_LABEL.get(business_type.lower(), business_type)
        result = await _naver_client.get_district_trend(dong_name, biz_label)
        growth = result.get("growth_rate")
        return float(growth) if growth is not None else None
    except Exception as e:
        logger.debug(f"[district_ranking] NAVER 트렌드 조회 실패 ({dong_name}): {e}")
        return None


async def _score_single_district(dong_name: str, business_type: str) -> dict:
    """
    단일 행정동 원시 지표 수집.
    DB 데이터 없는 항목은 None으로 반환 — 0.0과 구분하여 정규화 왜곡 방지.
    SEMAS 밀집도, NAVER 트렌드는 API 키 있을 때만 조회 (없으면 None).
    """
    try:
        # 기본 3축 + 선택 2축 병렬 조회
        results = await asyncio.gather(
            market_tool.get_commercial_insights(dong_name, business_type),
            shared_population_trends(dong_name),
            market_tool.get_rent_insight(dong_name),
            _fetch_semas_density(dong_name, business_type),
            _fetch_naver_trend(dong_name, business_type),
            return_exceptions=True,
        )
        sales_data, pop_data, rent_data, semas_density, naver_trend = results

        # None = DB 데이터 없음, 0.0 = 실제 성장률 0
        sales_growth = None
        if not isinstance(sales_data, Exception) and "error" not in (sales_data or {}):
            sales_growth = float(sales_data.get("qoq_growth") or 0)

        pop_growth = None
        if not isinstance(pop_data, Exception) and "error" not in (pop_data or {}):
            pop_growth = float(pop_data.get("qoq_growth") or 0)

        avg_rent = None
        if not isinstance(rent_data, Exception) and "error" not in (rent_data or {}):
            val = rent_data.get("avg_rent_3_3m2")
            if val:
                avg_rent = float(val)

        # SEMAS/NAVER는 Exception이면 None 처리
        if isinstance(semas_density, Exception):
            semas_density = None
        if isinstance(naver_trend, Exception):
            naver_trend = None

        logger.debug(
            f"[district_ranking] {dong_name}: sales={sales_growth}, pop={pop_growth}, "
            f"rent={avg_rent}, density={semas_density}, trend={naver_trend}"
        )
        return {
            "district": dong_name,
            "sales_growth": sales_growth,
            "pop_growth": pop_growth,
            "avg_rent": avg_rent,
            "semas_density": semas_density,
            "naver_trend": naver_trend,
        }
    except Exception as e:
        logger.warning(f"[district_ranking] {dong_name} 점수 산출 실패 (무시): {e}")
        return {
            "district": dong_name,
            "sales_growth": None,
            "pop_growth": None,
            "avg_rent": None,
            "semas_density": None,
            "naver_trend": None,
        }


def _normalize_and_rank(
    raw: list[dict],
    population_weight: bool = True,
    monthly_rent_budget: int = 0,
    store_area: float = 15.0,
    vacancy_rate_map: dict[str, float] | None = None,
    business_type: str = "",
) -> list[dict]:
    """
    16개 동의 원시 지표를 0~100으로 정규화 후 가중 합산 → 내림차순 정렬

    population_weight=True  : 매출35% + 인구45% + 임대료20%
    population_weight=False : 매출50% + 인구10% + 임대료40%
    monthly_rent_budget > 0 : 예산 초과 동에 페널티 적용
    vacancy_rate_map        : 공실률 높은 동 추가 패널티 (5~10%: -15%, 10%+: -30%)
    business_type           : 용도지역 규제 패널티 판정용 업종 코드
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

    def _minmax(vals: list[float | None], reverse: bool = False, floor: float = 0.0) -> list[float]:
        """
        None = DB 데이터 없음 → 중간값(50) 부여, 실데이터만 min-max 정규화.
        전체가 None이거나 실데이터 편차 없으면 50 반환.

        floor: 최저 score 하한 (UX 가독성용). 기본 0, 예: 10 이면 최저 10, 최고 100.
            - 정규화 결과가 0으로 떨어지면 프론트에서 "데이터 없음"처럼 보여 혼란 → 소폭 floor 부여.
        """
        real = [v for v in vals if v is not None]
        if not real:
            return [50.0] * len(vals)
        lo, hi = min(real), max(real)
        scale = 100.0 - floor
        results = []
        for v in vals:
            if v is None:
                results.append(50.0)  # 데이터 없음 → 중간값
            elif hi == lo:
                results.append(50.0)
            else:
                raw_norm = (v - lo) / (hi - lo)  # 0.0 ~ 1.0
                if reverse:
                    raw_norm = 1.0 - raw_norm
                results.append(raw_norm * scale + floor)
        return results

    # [FIX] pop/sales/rent 모두 floor 10 적용 — min-max 최저값이 0 으로 떨어져
    # IndicatorGrid 에 "유동인구 0" 같은 결측처럼 보이는 문제 방지 (UX 가독성).
    sales_norm = _minmax([r["sales_growth"] for r in raw], floor=10.0)
    pop_norm = _minmax([r["pop_growth"] for r in raw], floor=10.0)
    rent_norm = _minmax([r["avg_rent"] for r in raw], reverse=True, floor=10.0)  # 낮은 임대료 = 높은 점수

    # SEMAS 밀집도 (역방향 — 적을수록 좋음: 경쟁 낮음)
    density_vals = [r.get("semas_density") for r in raw]
    has_density = any(v is not None for v in density_vals)
    density_norm = _minmax(density_vals, reverse=True) if has_density else None

    # NAVER 트렌드 (정방향 — 높을수록 좋음: 상승 상권)
    trend_vals = [r.get("naver_trend") for r in raw]
    has_trend = any(v is not None for v in trend_vals)
    trend_norm = _minmax(trend_vals) if has_trend else None

    # 데이터 커버리지 로그
    sales_hit = sum(1 for r in raw if r["sales_growth"] is not None)
    pop_hit = sum(1 for r in raw if r["pop_growth"] is not None)
    rent_hit = sum(1 for r in raw if r["avg_rent"] is not None)
    density_hit = sum(1 for v in density_vals if v is not None)
    trend_hit = sum(1 for v in trend_vals if v is not None)
    logger.info(
        f"[district_ranking] 데이터 커버리지 — 매출:{sales_hit}/16, 인구:{pop_hit}/16, "
        f"임대료:{rent_hit}/16, 밀집도:{density_hit}/16, 트렌드:{trend_hit}/16"
    )

    # 가중치 재분배: 경쟁밀도 15% (5% → 15%: 포화 업종 진입 페널티 강화), 트렌드 5%
    # 경쟁밀도는 매출에서 차감 — 인구/임대료 가중치는 유지
    w_density = 0.15 if has_density else 0.0
    w_trend = 0.05 if has_trend else 0.0
    w_sales_adj = max(w_sales - w_density - w_trend, 0.05)  # 매출 가중치 최소 5% 보장

    ranked = []
    for i, r in enumerate(raw):
        score = sales_norm[i] * w_sales_adj + pop_norm[i] * w_pop + rent_norm[i] * w_rent
        if density_norm is not None:
            score += density_norm[i] * w_density
        if trend_norm is not None:
            score += trend_norm[i] * w_trend

        # 예산 초과 페널티
        if budget_per_3_3m2 > 0 and r["avg_rent"] is not None and r["avg_rent"] > 0:
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

        # 용도지역 규제 패널티: legal_node와 동일한 DISTRICT_ZONE_MAP/ZONING_RULES 사용
        zoning_risk = "safe"
        if business_type:
            type_label = BIZ_TYPE_LABEL.get(business_type.lower(), business_type)
            zone = DISTRICT_ZONE_MAP.get(r["district"], "근린상업지역")
            rules = ZONING_RULES.get(zone, {"허용": [], "제한": []})
            if type_label in rules["제한"]:
                zoning_risk = "danger"
                score *= 0.50  # 영업 제한 업종: -50%
            elif type_label not in rules["허용"] and rules["제한"]:
                zoning_risk = "caution"
                score *= 0.85  # 회색지역: -15%

        ranked.append(
            {
                **r,
                # None → 0.0으로 직렬화 (프론트엔드 호환)
                "sales_growth": r["sales_growth"] if r["sales_growth"] is not None else 0.0,
                "pop_growth": r["pop_growth"] if r["pop_growth"] is not None else 0.0,
                "avg_rent": r["avg_rent"] if r["avg_rent"] is not None else 0.0,
                "score": round(score, 1),
                "sales_score": round(sales_norm[i], 1),
                "pop_score": round(pop_norm[i], 1),
                "rent_score": round(rent_norm[i], 1),
                "density_score": round(density_norm[i], 1) if density_norm else None,
                "trend_score": round(trend_norm[i], 1) if trend_norm else None,
                "semas_density": r.get("semas_density"),
                "naver_trend": r.get("naver_trend"),
                "vacancy_rate": vacancy_rate,
                "zoning_risk": zoning_risk,
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

    # 캐시 키 정규화 (constants.py 단일 소스)
    _normalized_biz = BIZ_NORMALIZE.get(business_type.lower(), business_type)

    # Redis 캐시 조회 — 동일 조건 재요청 시 DB 쿼리 없이 즉시 반환 (DEBUG=true 시 스킵)
    cache_key = f"v4:ranking:{_normalized_biz}:{population_weight}:{monthly_rent_budget}:{store_area}"
    _redis = None
    try:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        cached = None if settings.debug else await _redis.get(cache_key)
        if cached:
            cached_data = json.loads(cached)
            logger.info(f"[district_ranking] 캐시 히트: {cache_key}")
            try:
                await _redis.aclose()
            except Exception:
                pass
            _cached_ranked = cached_data.get("scouting_results", []) or []
            # 캐시 히트 시에도 winner = scouting_results[0] (ranked[0]) 재계산
            _cached_winner = (
                _cached_ranked[0]["district"]
                if _cached_ranked and isinstance(_cached_ranked[0], dict)
                else cached_data.get("winner_district", "")
            )
            _cached_top_3 = [r["district"] for r in _cached_ranked[1:4] if isinstance(r, dict)]
            _cached_winner_score = 0
            if _cached_ranked:
                _first = _cached_ranked[0] if isinstance(_cached_ranked[0], dict) else {}
                _cached_winner_score = _first.get("final_score") or _first.get("score") or 0
            cached_ranking_attr = build_attribution(
                agent_id="district_ranking",
                display_name="행정동 랭킹",
                kind="Python",
                sources=["district_sales", "golmok_rent", "seoul_adstrd_flpop"],
                verdict=f"1위 {_cached_winner} ({_cached_winner_score}점)",
                reasoning="마포 16동 정량 스코어링 — 매출/인구/임대료 가중합 (캐시)",
                confidence=0.9,
            )
            _cached_analysis = dict(state.get("analysis_results", {}))
            _cached_analysis["district_ranking_result"] = {"agent_attribution": cached_ranking_attr}
            return {
                "scouting_results": cached_data["scouting_results"],
                "winner_district": _cached_winner,   # ranked[0] 재계산값
                "top_3_candidates": _cached_top_3,   # ranked[1:4] 재계산값
                "vacancy_applied": cached_data.get("vacancy_applied", False),
                "vacancy_spots": cached_data.get("vacancy_spots", []),
                "current_agent": "district_ranking",
                "analysis_results": _cached_analysis,
                "agent_attribution": cached_ranking_attr,
            }
    except Exception as e:
        logger.warning(f"[district_ranking] Redis 캐시 조회 실패 (무시하고 계속): {e}")
        if _redis is not None:
            try:
                await _redis.aclose()
            except Exception:
                pass
        _redis = None

    # 직접 호출 시(예: /analyze/quick) parallel_analysis_node를 거치지 않으므로
    # stale Task 방지를 위해 자체 초기화
    _clear_shared_population_cache()

    logger.info(
        f"--- [DISTRICT RANKING] 마포구 {len(MAPO_DISTRICTS)}개 행정동 스코어링 시작 "
        f"(인구가중치={population_weight}, 예산={monthly_rent_budget:,}원, 면적={store_area}평) ---"
    )

    _init_optional_clients()

    if db_client.engine is None:
        await db_client.connect()

    # 16개 동 점수 + 공실률 병렬 로드 (세마포어로 동시 DB 접근 제한)
    async def _guarded_score(dong: str) -> dict:
        async with _db_semaphore:
            return await _score_single_district(dong, business_type)

    tasks = [_guarded_score(dong) for dong in MAPO_DISTRICTS]
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
        business_type=business_type,
    )

    # winner는 항상 전체 채점 1위 — target_districts 필터 제거
    # (필터 적용 시 target_district=공덕동이면 공덕동이 무조건 winner가 되는 버그 방지)
    winner = ranked[0]["district"] if ranked else state.get("target_district", "서교동")
    top_3 = [r["district"] for r in ranked[1:4]]

    # winner + top_3 + 사용자 선택 동의 실제 공실 좌표 조회
    target_district = state.get("target_district", winner)
    dong_names = list(dict.fromkeys([winner, target_district] + top_3))
    vacancy_spots = await _load_vacancy_spots(dong_names)

    logger.info(
        f"--- [DISTRICT RANKING] 완료 - 1위: {winner}, 후보: {top_3}, 공실반영={vacancy_applied}, 스팟={len(vacancy_spots)}개 ---"
    )

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
                        "vacancy_spots": vacancy_spots,
                    },
                    ensure_ascii=False,
                ),
                ex=_CACHE_TTL,
            )
            logger.info(f"[district_ranking] 캐시 저장: {cache_key} (TTL: {_CACHE_TTL}s)")
        except Exception as e:
            logger.warning(f"[district_ranking] Redis 캐시 저장 실패 (무시): {e}")
        finally:
            try:
                await _redis.aclose()
            except Exception:
                pass

    _winner_score = 0
    if ranked:
        _first_ranked = ranked[0] if isinstance(ranked[0], dict) else {}
        _winner_score = _first_ranked.get("final_score") or _first_ranked.get("score") or 0
    ranking_attr = build_attribution(
        agent_id="district_ranking",
        display_name="행정동 랭킹",
        kind="Python",
        sources=["district_sales", "golmok_rent", "seoul_adstrd_flpop"],
        verdict=f"1위 {winner} ({_winner_score}점)",
        reasoning="마포 16동 정량 스코어링 — 매출/인구/임대료 가중합",
        confidence=0.9,
    )
    _analysis = dict(state.get("analysis_results", {}))
    _analysis["district_ranking_result"] = {"agent_attribution": ranking_attr}

    return {
        "scouting_results": ranked,
        "winner_district": winner,
        "top_3_candidates": top_3,
        "vacancy_applied": vacancy_applied,
        "vacancy_spots": vacancy_spots,
        "current_agent": "district_ranking",
        "analysis_results": _analysis,
        "agent_attribution": ranking_attr,
    }
