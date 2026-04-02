"""
상권분석 Agent — 행정동별 업종밀도, 폐업률, 매출 규모 분석

주요 데이터 소스:
  - 소상공인시장진흥공단 API (업종밀도, 평균매출, 폐업률)
  - 우리마을가게 상권분석서비스 (상권 현황)
"""
from src.agents.state import AgentState


def analyze_business_density(state: AgentState) -> dict:
    """
    업종밀도 분석 — 대상 동의 업종별 점포 수 및 밀도 계산

    Returns:
        dict: 업종별 점포 수, 면적 대비 밀도, 전국 평균 대비 비율
    """
    # TODO: 소상공인 API로 대상 동 업종밀도 조회
    # TODO: 면적 대비 점포 밀도 계산
    # TODO: 전국/마포구 평균과 비교
    pass


def analyze_closure_rate(state: AgentState) -> dict:
    """
    폐업률 분석 — 대상 동의 최근 1/3/5년 폐업률 추이

    Returns:
        dict: 연도별 폐업률, 업종별 폐업률, 생존율
    """
    # TODO: 소상공인 API로 폐업 데이터 조회
    # TODO: 업종별/기간별 폐업률 계산
    # TODO: 신규 대비 폐업 비율 산출
    pass


def analyze_avg_revenue(state: AgentState) -> dict:
    """
    평균매출 분석 — 동일 업종의 동 평균 매출액

    Returns:
        dict: 월평균 매출, 분기별 추이, 상위/하위 매출 범위
    """
    # TODO: 카드 매출 데이터 기반 업종별 평균 산출
    # TODO: 시간대별/요일별 매출 패턴
    pass


def commercial_node(state: AgentState) -> AgentState:
    """
    상권분석 Agent 메인 노드 — LangGraph에서 호출되는 진입점

    업종밀도 + 폐업률 + 평균매출을 종합하여 state에 결과 추가
    """
    # TODO: 3가지 분석 실행
    # TODO: state.district_data에 상권 데이터 반영
    pass
