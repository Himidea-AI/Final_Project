"""
inflow_node — 교통·집객 접근성 에이전트 (Python 전용, LLM 없음)

역할:
    마포 16동의 교통(지하철·버스)·집객시설 인프라 접근성을 0~100 점수화하여
    district_ranking 에이전트와 협력해 winner 결정에 15% 가중치로 기여한다.
    synthesis 프롬프트에는 evidence dict가 주입되어 자연어 근거로 활용된다.

책임 영역:
    - 교통 접근성: 지하철 거리·노선 수, 버스 정류장·승하차량
    - 집객 인프라: 병원·대학·백화점·극장 등 14종 시설 가중합
    (매출 예측·경쟁·법률 등 타 에이전트 영역은 책임지지 않음)

데이터 소스:
    - dong_subway_access (서울 424동 최근접역·거리)
    - bus_boarding_daily (371만 행 정류장별 일별 승하차)
    - seoul_adstrd_fclty (마포 16동 × 20종 집객시설 분기 집계)

공식:
    Hansen (1959) gravity accessibility + E2SFCA (McGrail & Humphreys 2009) Gaussian decay
    가중치 w_subway=0.10, w_bus=0.40, w_fclty=0.50 — 실매출 16동×8분기 회귀 R²=0.55 캘리브레이션

담당: A2 봉환
"""

from __future__ import annotations

import logging
import time

from src.agents.nodes._attribution_helpers import build_attribution
from src.schemas.state import AgentState
from src.services.inflow_scorer import score_all_districts

logger = logging.getLogger(__name__)


async def inflow_node(state: AgentState) -> dict:
    """교통·집객 접근성 판단 에이전트 (LLM 없음, ~50ms)."""
    t_start = time.perf_counter()
    logger.info("--- [OPERATIONAL_FIT] 시작 ---")

    try:
        results = await score_all_districts()
    except Exception as exc:
        logger.warning(f"[inflow] 점수 계산 실패 (빈 결과로 진행): {exc}")
        results = {}

    # 판정 대상 동: winner_district 우선, 없으면 target_district
    target = state.get("winner_district") or state.get("target_district") or ""
    target_fit = results.get(target, {}) if results else {}

    score_vals = [r["inflow_score"] for r in results.values()] if results else []
    elapsed = time.perf_counter() - t_start

    if results:
        verdict = (
            f"{target or '-'} {target_fit.get('inflow_score', 0):.0f}/100"
            if target_fit
            else f"16동 점수 범위 {min(score_vals):.1f}~{max(score_vals):.1f}"
        )
        reasoning = (
            "Hansen(1959) + E2SFCA(McGrail 2009) Gaussian decay 기반 "
            "지하철·버스·집객시설 종합 점수. 실매출 16동×8분기 회귀 R²=0.55."
        )
        confidence = 0.85
    else:
        verdict = "데이터 없음"
        reasoning = "점수 계산 실패 — 원천 테이블 조회 오류"
        confidence = 0.0

    attr = build_attribution(
        agent_id="inflow",
        display_name="교통·집객 접근성",
        kind="Python",
        sources=["dong_subway_access", "bus_boarding_daily", "seoul_adstrd_fclty"],
        verdict=verdict,
        reasoning=reasoning,
        confidence=confidence,
    )

    if results:
        logger.info(
            f"--- [OPERATIONAL_FIT] 완료 ({elapsed:.2f}s) | "
            f"16동 점수 {min(score_vals):.1f}~{max(score_vals):.1f} | "
            f"판정 {verdict} ---"
        )
    else:
        logger.warning(f"--- [OPERATIONAL_FIT] 완료 ({elapsed:.2f}s) | 결과 없음 ---")

    _analysis = dict(state.get("analysis_results", {}))
    _analysis["inflow_result"] = {
        "agent_attribution": attr,
        "target_district": target,
        "target_score": target_fit.get("inflow_score"),
        "target_evidence": target_fit.get("evidence"),
    }

    return {
        "inflow_results": results,
        "analysis_results": _analysis,
        "current_agent": "inflow",
    }
