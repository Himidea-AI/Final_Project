import asyncio
import time
from langgraph.graph import StateGraph, END

from src.schemas.state import AgentState
from src.agents.nodes.market_analyst import market_analyst_node
from src.agents.nodes.population import population_analyst_node
from src.agents.nodes.legal import legal_node
from src.agents.nodes.synthesis import synthesis_node
from src.agents.nodes.district_ranking import district_ranking_node, _clear_shared_population_cache
from src.agents.nodes.demographic_depth import demographic_depth_node
from src.agents.nodes.trend_forecaster import trend_forecaster_node
from src.agents.nodes.competitor_intel import competitor_intel_node
from src.agents.nodes.operational_fit import operational_fit_node
from src.agents.tools import MarketDataTool as _MarketDataTool

_BIZ_TO_INDUSTRY_CODE: dict[str, str] = _MarketDataTool._SALES_CODE_MAP

# 전체 파이프라인 토큰 예산 (입력+출력 합산 추정치 기준)
# gpt-4.1-mini: 입력 $0.15/1M, 출력 $0.60/1M
_TOKEN_BUDGET_PER_RUN = 16000  # 토큰 초과 시 경고 로그 (legal 에이전트 평균 7k, 전체 평균 10k)


def _estimate_tokens(text: str) -> int:
    return max(len(text) // 3, 1)


def _count_result_tokens(result: dict) -> int:
    total = 0
    for v in result.values():
        if isinstance(v, str):
            total += _estimate_tokens(v)
        elif isinstance(v, dict):
            total += _count_result_tokens(v)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, str):
                    total += _estimate_tokens(item)
                elif isinstance(item, dict):
                    total += _count_result_tokens(item)
    return total


async def ranking_phase_node(state: AgentState) -> dict:
    """
    Phase 1: district_ranking 단독 실행 (LLM 없음, ~5-10초)

    winner_district를 먼저 확정해야 Phase 2 LLM 에이전트들이
    올바른 동(winner)을 기준으로 분석할 수 있음.
    """
    t_start = time.perf_counter()
    print("--- [PHASE 1] district_ranking 실행 시작 (winner 확정) ---")

    _clear_shared_population_cache()
    ranking_result = await district_ranking_node(state)

    winner = ranking_result.get("winner_district", state.get("target_district", ""))
    elapsed = time.perf_counter() - t_start
    print(f"--- [PHASE 1] 완료 ({elapsed:.1f}s) | winner={winner} ---")

    return {
        "scouting_results": ranking_result.get("scouting_results", []),
        "winner_district": winner,
        "top_3_candidates": ranking_result.get("top_3_candidates", []),
        "vacancy_applied": ranking_result.get("vacancy_applied", False),
        "vacancy_spots": ranking_result.get("vacancy_spots", []),
        "analysis_results": ranking_result.get("analysis_results", {}),
        "current_agent": "ranking_phase",
    }


async def llm_analysis_phase_node(state: AgentState) -> dict:
    """
    Phase 2: 6개 LLM 에이전트 병렬 실행

    target_district를 Phase 1에서 확정된 winner_district로 덮어쓰고 실행.
    이로써 시장/인구/법률 분석 데이터가 추천 1위 동을 기준으로 생성됨.
    """
    t_start = time.perf_counter()

    # winner_district를 분석 기준동으로 사용 (Phase 1에서 확정)
    winner = state.get("winner_district") or state.get("target_district", "")
    original_target = state.get("target_district", "")
    if winner and winner != original_target:
        print(f"--- [PHASE 2] target_district 교체: {original_target} → {winner} (winner 기준 분석) ---")
    else:
        print(f"--- [PHASE 2] target_district={winner} (변경 없음) ---")

    # winner를 target_district로 주입한 상태로 LLM 에이전트 실행
    analysis_state = dict(state)
    analysis_state["target_district"] = winner

    print("--- [PHASE 2] 6개 LLM 에이전트 병렬 실행 시작 ---")
    (
        market_result,
        population_result,
        legal_result,
        demographic_result,
        trend_result,
        competitor_result,
    ) = await asyncio.gather(
        market_analyst_node(analysis_state),
        population_analyst_node(analysis_state),
        legal_node(analysis_state),
        demographic_depth_node(analysis_state),
        trend_forecaster_node(analysis_state),
        competitor_intel_node(analysis_state),
    )

    # analysis_results 병합 (Phase 1 ranking 결과 보존)
    merged_analysis = dict(state.get("analysis_results", {}))
    for result in (
        market_result,
        population_result,
        legal_result,
        demographic_result,
        trend_result,
        competitor_result,
    ):
        merged_analysis.update(result.get("analysis_results", {}))

    # analysis_metrics 병합
    merged_metrics = dict(state.get("analysis_metrics", {}))
    for result in (
        market_result,
        population_result,
        legal_result,
        demographic_result,
        trend_result,
        competitor_result,
    ):
        merged_metrics.update(result.get("analysis_metrics", {}))

    overall_legal_risk = legal_result.get("overall_legal_risk") or state.get("overall_legal_risk", "caution")

    token_market = _count_result_tokens(market_result)
    token_pop = _count_result_tokens(population_result)
    token_legal = _count_result_tokens(legal_result)
    token_demo = _count_result_tokens(demographic_result)
    token_trend = _count_result_tokens(trend_result)
    token_competitor = _count_result_tokens(competitor_result)
    token_total = token_market + token_pop + token_legal + token_demo + token_trend + token_competitor
    elapsed = time.perf_counter() - t_start

    print(
        f"--- [PHASE 2] 완료 ({elapsed:.1f}s) | "
        f"토큰 추정 - market:{token_market} pop:{token_pop} legal:{token_legal} "
        f"demo:{token_demo} trend:{token_trend} competitor:{token_competitor} "
        f"합계:{token_total}/{_TOKEN_BUDGET_PER_RUN} ---"
    )
    if token_total > _TOKEN_BUDGET_PER_RUN:
        print(f"[WARNING] [TOKEN BUDGET] 추정 토큰 {token_total}이 예산 {_TOKEN_BUDGET_PER_RUN}을 초과했습니다.")

    return {
        "analysis_results": merged_analysis,
        "analysis_metrics": merged_metrics,
        "market_data": market_result.get("market_data", state.get("market_data", {})),
        "legal_info": legal_result.get("legal_info", state.get("legal_info", [])),
        "overall_legal_risk": overall_legal_risk,
        "competitor_intel_result": competitor_result.get("competitor_intel_result", {}),
        # winner_district는 Phase 1에서 이미 state에 설정됨 — 여기서 덮어쓰지 않음
        "current_agent": "llm_analysis_phase",
    }


async def ml_prediction_phase_node(state: AgentState) -> dict:
    """
    Phase 2.5: TCN ML 모델 실행 (winner 동 기준)

    LLM 에이전트 분석이 끝난 뒤 TCN으로 실제 수치(매출/BEP/폐업률)를 계산.
    결과를 state에 저장해 synthesis 프롬프트에 주입 → LLM이 추측 대신 실측값 사용.
    """
    t_start = time.perf_counter()
    winner = state.get("winner_district") or state.get("target_district", "")
    print(f"--- [PHASE 2.5] TCN 실행 시작 (winner={winner}) ---")

    try:
        from src.services.dong_resolver import resolve_dong_code
        from models.interface import ModelOutput

        dong_code = resolve_dong_code(winner)
        if not dong_code:
            raise ValueError(f"동 코드 조회 실패: {winner}")

        biz = state.get("business_type", "카페")
        industry_code = _BIZ_TO_INDUSTRY_CODE.get(biz, "CS100010")

        sim_result = ModelOutput.generate(dong_code, industry_code, biz, model="tcn")
        elapsed = time.perf_counter() - t_start
        monthly_rev = sim_result.get("revenue_forecast", {}).get("quarterly_avg", 0)
        bep = sim_result.get("bep", {}).get("bep_months", "?")
        closure = sim_result.get("closure_rate", {}).get("closure_rate", "?")
        print(
            f"--- [PHASE 2.5] TCN 완료 ({elapsed:.1f}s) | "
            f"월매출={monthly_rev:,.0f}원 BEP={bep}개월 폐업률={closure} ---"
        )

        # SHAP 분석 — synthesis 프롬프트 주입용 (main.py 중복 실행 대체)
        shap_result: dict = {}
        try:
            from models.explainability.shap_analysis import explain_tcn_prediction

            shap_result = explain_tcn_prediction(dong_code, industry_code)
            top_feat = (shap_result.get("feature_importance") or [{}])[0].get("feature_ko", "N/A")
            print(f"--- [PHASE 2.5] SHAP 완료 | top_feat={top_feat} ---")
        except Exception as _shap_err:
            print(f"--- [PHASE 2.5] SHAP 실패 (무시): {_shap_err} ---")

        return {"tcn_sim_result": sim_result, "shap_result": shap_result}

    except Exception as e:
        elapsed = time.perf_counter() - t_start
        print(f"--- [PHASE 2.5] TCN 실패 ({elapsed:.1f}s): {e} ---")
        return {"tcn_sim_result": {}, "shap_result": {}}


def build_graph() -> StateGraph:
    """
    상권분석 워크플로우 그래프 빌드 (2단계 실행)

    Phase 0: operational_fit (Python, LLM 없음, ~50ms)
      → 교통·집객 인프라 16동 점수 계산 → state.operational_fit_results

    Phase 1: ranking_phase (district_ranking, LLM 없음, ~5-10초)
      → winner_district 확정 (operational_fit 결과 15% 반영)

    Phase 2: llm_analysis_phase (6개 LLM 에이전트 병렬, winner 동 기준)
      → 시장/인구/법률 등 분석 데이터가 winner 동에서 생성

    Phase 2.5: ml_prediction_phase (TCN, winner 기준 실측 수치)

    Phase 3: synthesis (winner + 모든 에이전트 결과 기반 최종 리포트)
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("operational_fit", operational_fit_node)
    workflow.add_node("ranking_phase", ranking_phase_node)
    workflow.add_node("llm_analysis_phase", llm_analysis_phase_node)
    workflow.add_node("ml_prediction_phase", ml_prediction_phase_node)
    workflow.add_node("synthesis", synthesis_node)

    workflow.set_entry_point("operational_fit")
    workflow.add_edge("operational_fit", "ranking_phase")
    workflow.add_edge("ranking_phase", "llm_analysis_phase")
    workflow.add_edge("llm_analysis_phase", "ml_prediction_phase")
    workflow.add_edge("ml_prediction_phase", "synthesis")
    workflow.add_edge("synthesis", END)

    return workflow


def compile_graph():
    """그래프 컴파일"""
    return build_graph().compile()


# 하위 호환성 유지
compile_workflow = compile_graph
