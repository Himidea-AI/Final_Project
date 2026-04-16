import asyncio
from langgraph.graph import StateGraph, END

from src.schemas.state import AgentState
from src.agents.nodes.market_analyst import market_analyst_node
from src.agents.nodes.population import population_analyst_node
from src.agents.nodes.legal import legal_node
from src.agents.nodes.synthesis import synthesis_node
from src.agents.nodes.district_ranking import district_ranking_node


async def parallel_analysis_node(state: AgentState) -> dict:
    """
    4개 에이전트 병렬 실행

    market_analyst / population_analyst / legal_node / district_ranking 을
    asyncio.gather로 동시에 실행하고 결과를 합산합니다.

    - market / population / legal: 사용자 선택 행정동 심층 분석 (LLM)
    - district_ranking: 마포구 16개 전체 행정동 정량 스코어링 (LLM 없음)
    """
    print("--- [PARALLEL ANALYSIS] 4개 에이전트 병렬 실행 시작 ---")

    market_result, population_result, legal_result, ranking_result = await asyncio.gather(
        market_analyst_node(state),
        population_analyst_node(state),
        legal_node(state),
        district_ranking_node(state),
    )

    # analysis_results 병합
    merged_analysis = dict(state.get("analysis_results", {}))
    for result in (market_result, population_result, legal_result):
        merged_analysis.update(result.get("analysis_results", {}))

    # analysis_metrics 병합
    merged_metrics = dict(state.get("analysis_metrics", {}))
    for result in (market_result, population_result, legal_result):
        merged_metrics.update(result.get("analysis_metrics", {}))

    # overall_legal_risk는 legal 결과 우선
    overall_legal_risk = legal_result.get("overall_legal_risk") or state.get("overall_legal_risk", "caution")

    print("--- [PARALLEL ANALYSIS] 4개 에이전트 완료 ---")

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