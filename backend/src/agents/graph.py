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

# 전체 파이프라인 토큰 예산 (입력+출력 합산 추정치 기준)
# gpt-4.1-mini: 입력 $0.15/1M, 출력 $0.60/1M
_TOKEN_BUDGET_PER_RUN = 8000  # 토큰 초과 시 경고 로그


def _estimate_tokens(text: str) -> int:
    """텍스트 토큰 수 추정 (영문 4자, 한글 2자 ≈ 1토큰 근사)"""
    return max(len(text) // 3, 1)


def _count_result_tokens(result: dict) -> int:
    """에이전트 결과 dict에서 문자열 필드 토큰 합산"""
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


async def parallel_analysis_node(state: AgentState) -> dict:
    """
    6개 에이전트 병렬 실행

    market_analyst / population_analyst / legal_node / district_ranking /
    demographic_depth / trend_forecaster 를 asyncio.gather로 동시에 실행하고
    결과를 합산합니다.

    - market / population / legal / demographic_depth / trend: 사용자 선택 행정동 심층 분석 (LLM)
    - district_ranking: 마포구 16개 전체 행정동 정량 스코어링 (LLM 없음)
    """
    t_start = time.perf_counter()
    print("--- [PARALLEL ANALYSIS] 6개 에이전트 병렬 실행 시작 ---")

    # 동일 dong에 대한 get_population_trends 중복 쿼리 방지용 공유 Task 캐시 초기화
    _clear_shared_population_cache()

    (
        market_result,
        population_result,
        legal_result,
        ranking_result,
        demographic_result,
        trend_result,
    ) = await asyncio.gather(
        market_analyst_node(state),
        population_analyst_node(state),
        legal_node(state),
        district_ranking_node(state),
        demographic_depth_node(state),
        trend_forecaster_node(state),
    )

    # analysis_results 병합 (demographic_depth / trend_forecast 포함; legal_risks·market_report 등 기존 키 보존)
    merged_analysis = dict(state.get("analysis_results", {}))
    for result in (market_result, population_result, legal_result, demographic_result, trend_result):
        merged_analysis.update(result.get("analysis_results", {}))

    # analysis_metrics 병합
    merged_metrics = dict(state.get("analysis_metrics", {}))
    for result in (market_result, population_result, legal_result, demographic_result, trend_result):
        merged_metrics.update(result.get("analysis_metrics", {}))

    # overall_legal_risk는 legal 결과 우선
    overall_legal_risk = legal_result.get("overall_legal_risk") or state.get("overall_legal_risk", "caution")

    # 총 토큰 사용량 추정 및 예산 경고
    token_market = _count_result_tokens(market_result)
    token_pop = _count_result_tokens(population_result)
    token_legal = _count_result_tokens(legal_result)
    token_demo = _count_result_tokens(demographic_result)
    token_trend = _count_result_tokens(trend_result)
    token_total = token_market + token_pop + token_legal + token_demo + token_trend
    elapsed = time.perf_counter() - t_start

    print(
        f"--- [PARALLEL ANALYSIS] 완료 ({elapsed:.1f}s) | "
        f"토큰 추정 - market:{token_market} pop:{token_pop} legal:{token_legal} "
        f"demo:{token_demo} trend:{token_trend} "
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
        "scouting_results": ranking_result.get("scouting_results", []),
        "winner_district": ranking_result.get("winner_district", state.get("target_district", "")),
        "top_3_candidates": ranking_result.get("top_3_candidates", []),
        "current_agent": "parallel_analysis",
    }


def build_graph() -> StateGraph:
    """
    상권분석 워크플로우 그래프 빌드 (방향 B: 병렬 실행)

    START → parallel_analysis (market + population + legal + demographic + trend 동시) → synthesis → END

    변경 전: supervisor(LLM) 4회 호출 + 3개 에이전트 순차 실행
    변경 후: supervisor 제거 + 6개 에이전트 병렬 실행 → LLM 호출 절감, 속도 ~3배
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("parallel_analysis", parallel_analysis_node)
    workflow.add_node("synthesis", synthesis_node)

    workflow.set_entry_point("parallel_analysis")
    workflow.add_edge("parallel_analysis", "synthesis")
    workflow.add_edge("synthesis", END)

    return workflow


def compile_graph():
    """그래프 컴파일"""
    return build_graph().compile()


# 하위 호환성 유지
compile_workflow = compile_graph
