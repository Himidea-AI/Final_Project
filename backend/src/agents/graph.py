import asyncio
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage

from src.schemas.state import AgentState
# 1. 예진 님의 5인 체제 노드들만 남기고 나머지는 제거했습니다.
from src.agents.nodes.supervisor import supervisor_node
from src.agents.nodes.market_analyst import market_analyst_node
from src.agents.nodes.population import population_analyst_node
from src.agents.nodes.legal import legal_analyst_node
from src.agents.nodes.strategy_synthesizer import strategy_synthesizer_node as synthesis_node


def build_graph() -> StateGraph:
    """
    상권분석 워크플로우 그래프 빌드
    context_analyst → legal → strategy_synthesizer → END
    """
    workflow = StateGraph(AgentState)

    # 노드 등록 (5인 체제)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("market_analyst", market_analyst_node)
    workflow.add_node("population_analyst", population_analyst_node)
    workflow.add_node("legal_analyst", legal_analyst_node)
    workflow.add_node("synthesis", synthesis_node)

    # 진입점 설정
    workflow.set_entry_point("supervisor")

    # 중앙 통제 라우팅 (Supervisor -> Workers)
    workflow.add_conditional_edges(
        "supervisor",
        lambda x: x["next_step"],
        {
            "market_analyst": "market_analyst",
            "population_analyst": "population_analyst",
            "legal_analyst": "legal_analyst",
            "FINISH": "synthesis",
        },
    )

    # 작업 완료 후 복귀 (Workers -> Supervisor)
    workflow.add_edge("market_analyst", "supervisor")
    workflow.add_edge("population_analyst", "supervisor")
    workflow.add_edge("legal_analyst", "supervisor")

    # 최종 합성 후 종료 (Synthesis -> END)
    workflow.add_edge("synthesis", END)

    return workflow


def compile_graph():
    """그래프 컴파일"""
    builder = build_graph()
    return builder.compile()


# ★★★ [중요] 로그인 오류를 해결하는 핵심 열쇠 ★★★
compile_workflow = compile_graph


# --- 로컬 테스트 코드 (필요할 때 터미널에서 실행 가능) ---
async def test_run():
    app = compile_graph()

    initial_state = {
        "messages": [
            HumanMessage(
                content="홍대(서교동) 구역에 카페를 차리려고 합니다. 상권 분석과 주의해야 할 법률 정보를 알려주세요."
            )
        ],
        "business_type": "카페",
        "brand_name": "Antigravity Coffee",
        "target_district": "서교동",
        "market_data": {},
        "legal_info": [],
        "analysis_results": {},
        "current_agent": "start",
        "next_step": "",
        "errors": [],
    }

    final_state = initial_state
    async for event in app.astream(initial_state):
        for node_name, output in event.items():
            print(f"\n▶ [실행 중인 노드: {node_name}]")
            final_state.update(output)

    print("\n=== [FINAL STATE] ===")
    print(f"analysis_results: {final_state.get('analysis_results', {})}")


if __name__ == "__main__":
    asyncio.run(test_run())
