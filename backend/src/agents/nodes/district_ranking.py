"""
전체 마포구 행정동 입지 랭킹 에이전트

LLM 없이 Python 연산만으로 16개 행정동을 정량 점수화하여 순위를 산출합니다.
market / population / legal 에이전트와 asyncio.gather로 병렬 실행됩니다.

점수 산식 (100점 만점):
  - 매출 성장률 (QoQ)  40%
  - 유동인구 성장률 (QoQ) 30%
  - 임대료 저렴도       30%
"""

import asyncio
from src.schemas.state import AgentState
from src.config.constants import MAPO_DISTRICTS
from src.agents.nodes.market_analyst import db_client, market_tool

_CACHE_TTL = 86400  # 24시간


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
) -> list[dict]:
    """
    16개 동의 원시 지표를 0~100으로 정규화 후 가중 합산 → 내림차순 정렬

    population_weight=True  : 매출35% + 인구45% + 임대료20%
    population_weight=False : 매출50% + 인구10% + 임대료40%
    monthly_rent_budget > 0 : 예산 초과 동에 페널티 적용
    """
    if not raw:
        return []

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

        # 예산 초과 페널티: 평당 임대료가 예산의 1.5배 이상이면 점수 50% 감점
        if budget_per_3_3m2 > 0 and r["avg_rent"] > 0:
            if r["avg_rent"] > budget_per_3_3m2 * 1.5:
                score *= 0.5
            elif r["avg_rent"] > budget_per_3_3m2:
                ratio = r["avg_rent"] / budget_per_3_3m2
                score *= max(1.0 - (ratio - 1.0) * 0.5, 0.5)

        ranked.append({
            **r,
            "score": round(score, 1),
            "sales_score": round(sales_norm[i], 1),
            "pop_score": round(pop_norm[i], 1),
            "rent_score": round(rent_norm[i], 1),
        })

    ranked.sort(key=lambda x: x["score"], reverse=True)

    for idx, item in enumerate(ranked):
        item["rank"] = idx + 1

    return ranked


async def district_ranking_node(state: AgentState) -> dict:
    """
    마포구 16개 행정동 전수 스코어링 노드

    market / population / legal 에이전트와 함께 asyncio.gather로 병렬 실행됩니다.
    결과:
      scouting_results  : 점수 내림차순 전체 랭킹 리스트
      winner_district   : 1순위 행정동
      top_3_candidates  : 2~4순위 행정동 리스트
    """
    business_type = state.get("business_type", "카페")
    population_weight = state.get("population_weight", True)
    monthly_rent_budget = state.get("monthly_rent_budget", 0)
    store_area = state.get("store_area", 15.0)

    print(
        f"--- [DISTRICT RANKING] 마포구 {len(MAPO_DISTRICTS)}개 행정동 스코어링 시작 "
        f"(인구가중치={population_weight}, 예산={monthly_rent_budget:,}원, 면적={store_area}평) ---"
    )

    if db_client.engine is None:
        await db_client.connect()

    # 16개 동 병렬 점수 산출
    tasks = [_score_single_district(dong, business_type) for dong in MAPO_DISTRICTS]
    raw_scores = await asyncio.gather(*tasks)

    ranked = _normalize_and_rank(
        list(raw_scores),
        population_weight=population_weight,
        monthly_rent_budget=monthly_rent_budget,
        store_area=store_area,
    )

    winner = ranked[0]["district"] if ranked else state.get("target_district", "서교동")
    top_3 = [r["district"] for r in ranked[1:4]]

    print(f"--- [DISTRICT RANKING] 완료 — 1위: {winner}, 후보: {top_3} ---")

    return {
        "scouting_results": ranked,
        "winner_district": winner,
        "top_3_candidates": top_3,
        "current_agent": "district_ranking",
    }
