import asyncio
from typing import Literal
from langgraph.graph import StateGraph, END  # <--- 이 줄이 있는지 꼭 확인하세요!
from langchain_core.messages import HumanMessage

# backend/src/agents/graph.py 상단

from src.agents.nodes import (
    supervisor_node,
    market_analyst_node,
    population_analyst_node,
    legal_analyst_node,
    synthesis_node
)

from src.schemas.state import AgentState
from src.agents.nodes.context_analyst import context_analyst_node
from src.agents.nodes.strategy_synthesizer import strategy_synthesizer_node


def build_graph() -> StateGraph:
    """
    상권분석 워크플로우 그래프 빌드 (2노드 선형 파이프라인)
    ContextAnalyst(스카우팅/비교) -> StrategySynthesizer(법률/최종합성)
    """
    workflow = StateGraph(AgentState)

    # 1. 노드 등록
    workflow.add_node("context_analyst", context_analyst_node)
    workflow.add_node("strategy_synthesizer", strategy_synthesizer_node)

    # 2. 진입점 및 선형 경로 설정
    workflow.set_entry_point("context_analyst")
    workflow.add_edge("context_analyst", "strategy_synthesizer")
    workflow.add_edge("strategy_synthesizer", END)

    return workflow


def compile_workflow():
    """그래프 컴파일"""
    builder = build_graph()
    return builder.compile()


# --- 로컬 테스트 코드 ---
async def test_run():
    app = compile_workflow()

    # 셈플 입력값: 홍대(서교동) 카페 창업 시나리오
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

    print("\n" + "=" * 50)
    print("🚀 [LANGGRAPH SIMULATION START] 홍대 카페 창업 시나리오")
    print("=" * 50)
    print(f"사용자 질문: {initial_state['messages'][0].content}")

    final_state = initial_state

    async for event in app.astream(initial_state):
        for node_name, output in event.items():
            print(f"\n▶ [실행 중인 노드: {node_name}]")
            # 상태 업데이트 추적
            final_state.update(output)

    # -----------------------------------------------------
    # 최종 리포트 출력 (Final Report)
    # -----------------------------------------------------
    print("\n" + "=" * 50)
    print("📋 [FINAL ANALYSIS REPORT: 홍대 카페 창업]")
    print("=" * 50)

    # 1. 상권 요약
    market_summary = final_state.get("analysis_results", {}).get(
        "market_summary", "데이터 없음"
    )
    print(f"📍 [상권 분석 요약]\n   {market_summary}")

    # 2. 법률 리스크 요약
    legal_risks = final_state.get("analysis_results", {}).get(
        "legal_risks", "데이터 없음"
    )
    print(f"\n⚖️ [법률 리스크 요약]\n   {legal_risks}")

    # 3. 상세 지표 (상권)
    md = final_state.get("market_data", {})
    if md:
        print(f"\n📊 [상세 지표]")
        print(f"   - 구역: {md.get('district_name')}")
        print(f"   - 유동 인구: {md.get('floating_pop', {}).get('total', 0):,}명")
        print(f"   - 경쟁 매장: {md.get('store_count')}개")
        print(f"   - 예상 매출: {md.get('avg_revenue', 0):,}원")

    print("\n" + "=" * 50)
    print("✨ [시뮬레이션 종료]")
    print("=" * 50)


if __name__ == "__main__":
    # 비동기 실행
    asyncio.run(test_run())
