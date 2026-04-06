"""
LangGraph StateGraph 정의 및 컴파일
8개 분석 노드 + supervisor 노드를 연결하는 워크플로우 그래프
"""
from langgraph.graph import StateGraph, END

from src.agents.state import AgentState
from src.agents.nodes.commercial import commercial_node
from src.agents.nodes.population import population_node
from src.agents.nodes.demographics import demographics_node
from src.agents.nodes.cost import cost_node
from src.agents.nodes.competition import competition_node
from src.agents.nodes.trend import trend_node
from src.agents.nodes.legal import legal_node
from src.agents.nodes.report import report_node
from src.agents.nodes.supervisor import supervisor_node
from src.agents.edges import should_reanalyze


def build_graph() -> StateGraph:
    """
    상권분석 워크플로우 그래프 빌드

    흐름:
    1. 데이터 수집 (commercial, population, demographics — 병렬)
    2. 분석 (cost, competition, trend — 병렬)
    3. 법률 검토 (legal)
    4. Supervisor 판단 → 재분석 or 리포트 생성
    5. 리포트 생성 (report)
    """
    graph = StateGraph(AgentState)

    # ── 노드 등록 ──
    graph.add_node("commercial", commercial_node)
    graph.add_node("population", population_node)
    graph.add_node("demographics", demographics_node)
    graph.add_node("cost", cost_node)
    graph.add_node("competition", competition_node)
    graph.add_node("trend", trend_node)
    graph.add_node("legal", legal_node)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("report", report_node)

    # ── 엣지 연결 ──
    # Phase 1: 데이터 수집 (병렬)
    graph.set_entry_point("commercial")
    graph.add_edge("commercial", "population")
    graph.add_edge("population", "demographics")

    # Phase 2: 분석
    graph.add_edge("demographics", "cost")
    graph.add_edge("cost", "competition")
    graph.add_edge("competition", "trend")

    # Phase 3: 법률 검토
    graph.add_edge("trend", "legal")

    # Phase 4: Supervisor 판단
    graph.add_edge("legal", "supervisor")

    # Phase 5: 조건부 분기 — 재분석 or 리포트 생성
    graph.add_conditional_edges(
        "supervisor",
        should_reanalyze,
        {
            "reanalyze": "commercial",
            "generate_report": "report",
        },
    )

    # Phase 6: 리포트 → 종료
    graph.add_edge("report", END)

    return graph


def compile_graph():
    """그래프를 컴파일하여 실행 가능한 형태로 반환"""
    graph = build_graph()
    return graph.compile()

if __name__ == "__main__":
    app = compile_graph()
    print(app.get_graph().draw_mermaid())
