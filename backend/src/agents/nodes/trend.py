"""
트렌드 Agent — 키워드 검색량 기반 힙지수, 소비 패턴 변화 분석

주요 데이터 소스:
  - Naver DataLab 트렌드 API (크롤링 아님, 키워드 검색량 추이)
  - 서울 상권분석서비스(golmok) 추정매출 데이터
"""
from src.agents.state import AgentState


def analyze_search_trend(state: AgentState) -> dict:
    """
    검색 트렌드 기반 힙지수 분석 — Naver DataLab API 활용

    "망원동 카페", "연남동 맛집" 등 키워드 검색량 추이로
    핫플레이스 여부를 데이터로 판단

    Returns:
        dict: 키워드별 검색량 추이, 전월 대비 증감률, 힙지수(0~100)
    """
    # TODO: NaverTrendClient로 동+업종 키워드 트렌드 조회
    # TODO: 최근 12개월 검색량 추이
    # TODO: 전월 대비 증감률 계산
    # TODO: 힙지수 산출 (검색량 절대값 + 증가율 가중 합산)
    pass


def analyze_consumption_pattern(state: AgentState) -> dict:
    """
    소비 패턴 분석 — golmok 추정매출 기반 카테고리 변화

    카드사 빅데이터 직접 접근 불가 → golmok API 추정매출 활용

    Returns:
        dict: 카테고리별 매출 증감, 신규 업종 진출 현황
    """
    # TODO: GolmokAPIClient에서 추정매출 조회
    # TODO: 업종별 매출 비중 변화 분석
    # TODO: 업종 전환 트렌드 (예: 카페 → 디저트 전문)
    pass


def analyze_gentrification_risk(state: AgentState) -> dict:
    """
    젠트리피케이션 리스크 분석 — 임대료 급등 및 기존 상권 이탈 위험

    Returns:
        dict: 임대료 상승률, 점포 전환율, 젠트리피케이션 단계
    """
    # TODO: 최근 3년 임대료 상승률 조회
    # TODO: 기존 매장 이탈률 (폐업 + 이전)
    # TODO: 젠트리피케이션 단계 판정 (초기/진행/안정/쇠퇴)
    pass


def trend_node(state: AgentState) -> AgentState:
    """
    트렌드 Agent 메인 노드 — LangGraph에서 호출되는 진입점

    검색 트렌드 + 소비 패턴 + 젠트리피케이션을 종합하여 state에 결과 추가
    """
    # TODO: 3가지 분석 실행
    # TODO: state.district_data에 트렌드 데이터 반영
    pass
