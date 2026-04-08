import asyncio
from src.agents.state import AgentState
from src.agents.nodes.competition import competition_node

def run_test():
    print("--- 미로피쉬 디지털 트윈 시뮬레이션 테스트 ---")
    state = AgentState(target_district="망원1동", business_type="카페")
    res = competition_node(state)
    print("\n최종 반영된 상태(State) 결과:")
    print(res.analysis_results.cannibalization_impact)

if __name__ == "__main__":
    run_test()
