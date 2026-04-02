"""
Supervisor Node — 분석 결과의 충분성 판단 및 재분석 루프 제어

모든 Agent의 분석이 끝난 후 호출되어:
  1. 각 Agent의 결과 신뢰도를 평가
  2. 데이터 누락/불일치를 감지
  3. 재분석이 필요하면 iteration_count 증가 후 루프 재시작
  4. 충분하면 리포트 생성으로 넘김
"""
from src.agents.state import AgentState


def evaluate_confidence(state: AgentState) -> float:
    """
    분석 결과 신뢰도 평가 — 데이터 완성도와 일관성 체크

    Returns:
        float: 0.0 ~ 1.0 신뢰도 점수
    """
    # TODO: 필수 데이터 필드 존재 여부 확인
    # TODO: 분석 결과 간 논리적 일관성 검증
    # TODO: 신뢰도 점수 산출
    pass


def identify_gaps(state: AgentState) -> list:
    """
    데이터 갭 식별 — 재분석이 필요한 영역 리스트

    Returns:
        list: 재분석이 필요한 Agent 이름 리스트
    """
    # TODO: 각 Agent의 결과가 None이거나 불충분한지 확인
    # TODO: 결과 간 모순 발견 시 해당 Agent 지정
    pass


def supervisor_node(state: AgentState) -> AgentState:
    """
    Supervisor 메인 노드 — LangGraph에서 호출되는 진입점

    신뢰도 평가 → 갭 식별 → iteration_count 증가 또는 완료 판단
    edges.py의 should_reanalyze()가 이 결과를 보고 분기
    """
    # TODO: evaluate_confidence() 실행
    # TODO: 신뢰도 낮으면 identify_gaps() 실행
    # TODO: state.iteration_count += 1
    # TODO: 재분석 대상 정보를 state에 기록
    pass
