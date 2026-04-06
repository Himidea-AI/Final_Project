"""
리포트 Agent — 모든 분석 결과를 종합한 최종 보고서 생성

LLM을 활용하여 분석 데이터를 자연어 보고서로 변환하고,
동별 비교표, 추천 의견, 리스크 요약을 포함
"""

from ..state import AgentState


def generate_summary(state: AgentState) -> str:
    """
    경영진 요약 생성 — 1페이지 분량의 핵심 요약

    Returns:
        str: 마크다운 형식의 경영진 요약
    """
    # TODO: LLM으로 분석 결과 종합 요약 생성
    # TODO: 핵심 수치 (매출 예측, BEP, 생존율) 포함
    # TODO: 추천 동 및 이유
    pass


def generate_comparison_table(state: AgentState) -> dict:
    """
    동별 비교표 생성 — MVP 3개 동의 항목별 비교

    Returns:
        dict: 비교 항목별 3개 동 수치, 순위
    """
    # TODO: 각 동의 점수/매출/BEP/생존율 비교
    # TODO: 항목별 순위 산출
    # TODO: 종합 추천 순위
    pass


def generate_risk_report(state: AgentState) -> dict:
    """
    리스크 종합 보고서 — 카니발리제이션 + 경쟁 + 법률 리스크

    Returns:
        dict: 리스크 카테고리별 상세 내용, 대응 방안
    """
    # TODO: 카니발리제이션 영향 상세
    # TODO: 경쟁 리스크 요약
    # TODO: 법률 리스크 요약
    # TODO: 종합 리스크 레벨
    pass


def report_node(state: AgentState) -> AgentState:
    """
    리포트 Agent 메인 노드 — LangGraph에서 호출되는 진입점

    요약 + 비교표 + 리스크를 종합하여 최종 보고서 생성, state.report에 저장
    """
    # TODO: 3가지 보고서 생성
    # TODO: state.report에 최종 보고서 저장
    # TODO: state.status = "completed"
    pass
