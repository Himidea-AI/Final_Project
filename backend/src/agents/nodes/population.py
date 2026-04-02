"""
유동인구 Agent — 시간대/요일별 유동인구 흐름 분석

주요 데이터 소스:
  - 서울 열린데이터광장 (유동인구, 지하철 승하차)
"""
from src.agents.state import AgentState


def analyze_floating_population(state: AgentState) -> dict:
    """
    유동인구 분석 — 시간대/요일별 유동인구 패턴

    Returns:
        dict: 평일/주말 유동인구, 시간대별 분포, 피크 시간
    """
    # TODO: 서울 열린데이터 API로 유동인구 조회
    # TODO: 시간대별(06~24시) 유동인구 분포
    # TODO: 평일 vs 주말 패턴 비교
    pass


def analyze_subway_traffic(state: AgentState) -> dict:
    """
    지하철 승하차 분석 — 가장 가까운 역의 승하차 데이터

    Returns:
        dict: 최근접 역명, 일평균 승하차, 시간대별 분포
    """
    # TODO: 대상 동의 최근접 지하철역 확인
    # TODO: 월별 승하차 데이터 조회
    # TODO: 출퇴근/점심/저녁 패턴 분석
    pass


def population_node(state: AgentState) -> AgentState:
    """
    유동인구 Agent 메인 노드 — LangGraph에서 호출되는 진입점

    유동인구 + 지하철 승하차를 종합하여 state에 결과 추가
    """
    # TODO: 2가지 분석 실행
    # TODO: state.district_data.floating_population에 반영
    pass
