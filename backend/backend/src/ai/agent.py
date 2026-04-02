import asyncio
from langgraph.graph import StateGraph, END
from ..schemas.state import AgentState
from ..schemas.models import SimulationRequest
from .nodes import analyze_market_node, analyze_competition_node, supervisor_node

def should_continue(state: AgentState) -> str:
    """순환 루프 제어용 edge 판단 함수"""
    if state.is_completed:
        return END
    else:
        # 미완료 시 재분석 노드로 보내는 방식 (현재는 단순화)
        return "analyze_market"

def create_simulation_graph() -> StateGraph:
    """마포구 시장조사 시뮬레이터 핵심 워크플로우 그래프 생성"""
    # 1. StateGraph 선언 (상태 클래스 주입)
    workflow = StateGraph(AgentState)
    
    # 2. 파이프라인 노드 추가
    workflow.add_node("analyze_market", analyze_market_node)
    workflow.add_node("analyze_competition", analyze_competition_node)
    workflow.add_node("supervisor", supervisor_node)
    
    # 3. 엣지 제어 (노드 실행 순서 지정)
    workflow.set_entry_point("analyze_market")
    workflow.add_edge("analyze_market", "analyze_competition")
    workflow.add_edge("analyze_competition", "supervisor")
    
    # 조건부 엣지로 루프를 탈출하거나 반복
    workflow.add_conditional_edges(
        "supervisor",
        should_continue,
    )
    
    # 그래프 컴파일
    app = workflow.compile()
    return app

async def run_simulation_dummy() -> None:
    """테스트용 더미 실행 함수"""
    print("\n--- 마포구 시장조사 시뮬레이터 테스트 실행 ---")
    app = create_simulation_graph()
    
    # 더미 초기 상태 (프론트엔드 입력 가정)
    initial_request = SimulationRequest(
        target_dong="망원1동",
        business_type="카페",
        budget=5000,
        persona="예비 창업자 (B2C)"
    )
    
    initial_state = AgentState(request=initial_request)
    
    # 워크플로우 실행
    print("Agent 플로우 시작...\n")
    final_state = await app.ainvoke(initial_state)
    
    print("\n--- 시뮬레이션 종료 ---")
    print(f"최종 상태 결과물: \n{final_state.get('final_result') if isinstance(final_state, dict) else getattr(final_state, 'final_result', None)}")


if __name__ == "__main__":
    asyncio.run(run_simulation_dummy())
