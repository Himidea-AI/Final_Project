import asyncio
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage

from src.schemas.state import AgentState
from src.agents.nodes.context_analyst import context_analyst_node
from src.agents.nodes.legal import legal_node
from src.agents.nodes.strategy_synthesizer import strategy_synthesizer_node


def build_graph() -> StateGraph:
    """
    상권분석 워크플로우 그래프 빌드
    context_analyst → legal → strategy_synthesizer → END
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("context_analyst", context_analyst_node)
    workflow.add_node("legal_analyst", legal_node)
    workflow.add_node("synthesis", strategy_synthesizer_node)

    workflow.set_entry_point("context_analyst")

    workflow.add_edge("context_analyst", "legal_analyst")
    workflow.add_edge("legal_analyst", "synthesis")
    workflow.add_edge("synthesis", END)

    return workflow


def compile_graph():
    """그래프 컴파일"""
    builder = build_graph()
    return builder.compile()


# main.py 호환용 별칭
compile_workflow = compile_graph


# --- 로컬 테스트 코드 ---
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
