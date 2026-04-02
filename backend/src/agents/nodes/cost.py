"""
비용산정 Agent — 임대료, 인건비, 원가율 등 운영비 산출

주요 데이터 소스:
  - 국토교통부 실거래가 API (임대료 추이)
  - 소상공인 데이터 (인건비, 원가율)
"""
from src.agents.state import AgentState


def estimate_rent(state: AgentState) -> dict:
    """
    임대료 추정 — 대상 동의 상가 임대료 시세

    Returns:
        dict: 평균 임대료, 보증금, 최근 추이, 면적 기준
    """
    # TODO: 국토교통부 API로 상가 임대 실거래가 조회
    # TODO: 평형대별 평균 임대료 산출
    # TODO: 최근 12개월 임대료 추이
    pass


def estimate_labor_cost(state: AgentState) -> dict:
    """
    인건비 추정 — 업종별 필요 인원 및 인건비

    Returns:
        dict: 필요 직원 수, 월 총 인건비, 최저임금 기반 산출
    """
    # TODO: 업종별 평균 직원 수 산출
    # TODO: 최저임금 기반 인건비 계산
    # TODO: 파트타임/풀타임 비율 적용
    pass


def estimate_operating_cost(state: AgentState) -> dict:
    """
    운영비 종합 — 원가율, 관리비, 마케팅비 등

    Returns:
        dict: 항목별 월 운영비, 총 고정비, 변동비
    """
    # TODO: 업종별 평균 원가율 적용
    # TODO: 관리비/전기/수도 추정
    # TODO: BEP 계산을 위한 고정비/변동비 분리
    pass


def cost_node(state: AgentState) -> AgentState:
    """
    비용산정 Agent 메인 노드 — LangGraph에서 호출되는 진입점

    임대료 + 인건비 + 운영비를 종합하여 state에 결과 추가
    """
    # TODO: 3가지 비용 추정 실행
    # TODO: state.district_data에 비용 데이터 반영
    pass
