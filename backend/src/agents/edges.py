"""
조건부 경로 로직 — Supervisor 노드의 분기 판단
재분석이 필요한지, 리포트를 생성할지 결정
"""
from src.agents.state import AgentState


MAX_ITERATIONS = 3  # 최대 재분석 반복 횟수


def should_reanalyze(state: AgentState) -> str:
    """
    Supervisor 노드 이후 분기 조건

    재분석 조건:
    - 분석 결과의 신뢰도가 낮은 경우
    - 데이터 누락이 있는 경우
    - 최대 반복 횟수 미만인 경우

    Returns:
        "reanalyze" — 데이터 수집부터 다시 시작
        "generate_report" — 리포트 생성으로 이동
    """
    # TODO: 신뢰도 기준 판단 로직 구현
    # TODO: 데이터 완성도 체크
    # TODO: iteration_count 기반 루프 제어

    if state.iteration_count >= MAX_ITERATIONS:
        return "generate_report"

    # 기본: 리포트 생성
    return "generate_report"
