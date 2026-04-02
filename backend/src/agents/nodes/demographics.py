"""
인구통계 Agent — 주거인구, 연령별 분포, 가구구성 분석

주요 데이터 소스:
  - 통계청 SGIS (주거인구, 연령별 분포, 가구구성)
"""
from src.agents.state import AgentState


def analyze_resident_population(state: AgentState) -> dict:
    """
    주거인구 분석 — 대상 동의 주거인구 규모 및 밀도

    Returns:
        dict: 총 주거인구, 면적 대비 밀도, 증감 추이
    """
    # TODO: SGIS API로 주거인구 조회
    # TODO: 최근 3년 인구 증감 추이
    # TODO: 1인가구 비율 계산
    pass


def analyze_age_distribution(state: AgentState) -> dict:
    """
    연령별 분포 분석 — 타겟 연령대 비율 계산

    Returns:
        dict: 연령대별 인구 비율, 타겟 연령대 집중도
    """
    # TODO: 10세 단위 연령별 인구 조회
    # TODO: 업종별 타겟 연령대(constants.py)와 매칭
    # TODO: 타겟 집중도 = 타겟 연령대 비율 / 전체 비율
    pass


def analyze_household_composition(state: AgentState) -> dict:
    """
    가구구성 분석 — 1인가구, 맞벌이, 가족 등 소비패턴 유형

    Returns:
        dict: 가구 유형별 비율, 평균 가구원 수, 소비 성향 추정
    """
    # TODO: 가구 유형별 데이터 조회
    # TODO: 소비 성향 추정 (1인가구 → 편의점/카페 선호 등)
    pass


def demographics_node(state: AgentState) -> AgentState:
    """
    인구통계 Agent 메인 노드 — LangGraph에서 호출되는 진입점

    주거인구 + 연령 + 가구구성을 종합하여 state에 결과 추가
    """
    # TODO: 3가지 분석 실행
    # TODO: state.district_data.resident_population에 반영
    pass
