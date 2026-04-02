"""
LangGraph 에이전트 패키지

워크플로우 구성:
  - state.py      : AgentState — 모든 Agent가 공유하는 Pydantic 상태 객체
  - graph.py      : StateGraph 정의 및 컴파일 (8개 노드 + supervisor + 조건부 엣지)
  - edges.py      : 조건부 경로 로직 (재분석 필요 여부 판단)
  - nodes/        : Agent별 분석 노드 (commercial, population, demographics, cost,
                    competition, trend, legal, report, supervisor)

담당: B — AI Agent 개발자
"""
