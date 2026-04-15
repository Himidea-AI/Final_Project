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


def _normalize_and_rank(raw: list[dict]) -> list[dict]:
    """
    16개 동의 원시 지표를 0~100으로 정규화 후 가중 합산 → 내림차순 정렬
    """
    if not raw:
        return []

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
        score = sales_norm[i] * 0.4 + pop_norm[i] * 0.3 + rent_norm[i] * 0.3
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
    print(f"--- [DISTRICT RANKING] 마포구 {len(MAPO_DISTRICTS)}개 행정동 스코어링 시작 ---")

    if db_client.engine is None:
        await db_client.connect()

    # 16개 동 병렬 점수 산출
    tasks = [_score_single_district(dong, business_type) for dong in MAPO_DISTRICTS]
    raw_scores = await asyncio.gather(*tasks)

    ranked = _normalize_and_rank(list(raw_scores))

    winner = ranked[0]["district"] if ranked else state.get("target_district", "서교동")
    top_3 = [r["district"] for r in ranked[1:4]]

    print(f"--- [DISTRICT RANKING] 완료 — 1위: {winner}, 후보: {top_3} ---")

    return {
        "scouting_results": ranked,
        "winner_district": winner,
        "top_3_candidates": top_3,
        "current_agent": "district_ranking",
    }
