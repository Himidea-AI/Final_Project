import asyncio
from langgraph.graph import StateGraph, END

from src.schemas.state import AgentState
from src.agents.nodes.market_analyst import market_analyst_node
from src.agents.nodes.population import population_analyst_node
from src.agents.nodes.legal import legal_analyst_node
from src.agents.nodes.synthesis import synthesis_node


async def parallel_analysis_node(state: AgentState) -> dict:
    """
    3개 분석 에이전트를 병렬 실행 (LLM supervisor 제거 → API 호출 4회 절감)

    market_analyst / population_analyst / legal_analyst 를 asyncio.gather로
    동시에 실행하고 결과를 합산하여 반환합니다.
    """
    print("--- [PARALLEL ANALYSIS] 3개 에이전트 병렬 실행 시작 ---")

    market_result, population_result, legal_result = await asyncio.gather(
        market_analyst_node(state),
        population_analyst_node(state),
        legal_analyst_node(state),
    )

    # 각 에이전트의 analysis_results를 하나로 병합
    merged_analysis = dict(state.get("analysis_results", {}))
    for result in (market_result, population_result, legal_result):
        merged_analysis.update(result.get("analysis_results", {}))

    # analysis_metrics 병합
    merged_metrics = dict(state.get("analysis_metrics", {}))
    for result in (market_result, population_result, legal_result):
        merged_metrics.update(result.get("analysis_metrics", {}))

    # overall_legal_risk는 legal 결과 우선
    overall_legal_risk = (
        legal_result.get("overall_legal_risk")
        or state.get("overall_legal_risk", "caution")
    )

    print("--- [PARALLEL ANALYSIS] 3개 에이전트 완료 ---")

    return {
        "analysis_results": merged_analysis,
        "analysis_metrics": merged_metrics,
        "market_data": market_result.get("market_data", state.get("market_data", {})),
        "legal_info": legal_result.get("legal_info", state.get("legal_info", [])),
        "overall_legal_risk": overall_legal_risk,
        "current_agent": "parallel_analysis",
    }


def build_graph() -> StateGraph:
    """
    상권분석 워크플로우 그래프 빌드 (방향 B: 병렬 실행)

    START → parallel_analysis (market + population + legal 동시) → synthesis → END

    변경 전: supervisor(LLM) 4회 호출 + 3개 에이전트 순차 실행
    변경 후: supervisor 제거 + 3개 에이전트 병렬 실행 → LLM 호출 4회 절감, 속도 ~3배
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
