from typing import TypedDict, Annotated, Sequence, Any
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class MarketData(TypedDict, total=False):
    """상권분석 데이터 객체 (Track A 제공 데이터 구조)"""

    district: str
    lat: float  # 위도
    lng: float  # 경도
    floating_population: dict[str, Any]
    resident_population: dict[str, Any]
    competition_score: float
    average_rent: int
    business_density: dict[str, int]
    financial_metrics: dict[str, Any]  # 추가: 수익성 분석용 데이터 (임대료, 인건비 등)


class AgentState(TypedDict):
    """LangGraph 워크플로우에서 공유되는 에이전트 상태"""

    # 1. 대화 내역 (add_messages를 통해 순차적으로 축적)
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # 2. 사용자 요청 파라미터
    business_type: str  # 업종 (예: cafe, restaurant)
    brand_name: str  # 브랜드명
    target_district: str  # 분석 대상 행정동 (초기 입력 혹은 최종 승자)
    commercial_radius: int  # 상권 분석 반경 (m)
    monthly_rent_budget: int  # 월 임대료 예산 (원)
    store_area: float  # 점포 면적 (평)
    population_weight: bool  # 인구 가중치 반영 여부
    target_price_range: str  # 목표 객단가 구간
    operating_hours: list[str]  # 주 타겟 시간대
    initial_capital: int  # 초기 자본금 (원)

    # 3. 데이터 슬롯 (Track A 및 RAG 결과물 저장)
    market_data: MarketData  # DB에서 가져올 상권 데이터 객체
    legal_info: list[dict[str, Any]]  # 법률 RAG 결과

    # 4. [NEW] 선형 구조를 위한 추가 필드
    scouting_results: list[dict[str, Any]]  # 마포구 16개동 정량 스코어링 결과
    top_3_candidates: list[str]  # 선별된 상위 3개 행정동 리스트
    winner_district: str  # 최종 선정된 1순위 지역명 (Winner)
    brand_analysis: dict[str, Any]  # 브랜드 전국 평균 vs 지역 분석 결과
    vacancy_spots: list[dict[str, Any]]  # 추천 동들의 실제 공실 좌표 목록
    vacancy_applied: bool  # 공실 DB 반영 여부

    # 5. 분석 결과 및 상태 제어
    analysis_results: dict[str, Any]
    analysis_metrics: dict[str, Any]  # 추가: 시각화 및 정량적 평가를 위한 고도화 데이터 (growth_rate, grade 등)
    overall_legal_risk: str  # 최종 종합 리스크 레벨 (Safe/Caution/Danger)
    current_agent: str  # 현재 작업을 수행 중인 에이전트명
    next_step: str  # Supervisor가 결정한 다음 단계
    errors: list[str]

    # 6. competitor_intel 에이전트 결과 (하이브리드: Python 서비스 + LLM 해석)
    competitor_intel_result: dict[str, Any]  # CompetitorIntelResult 구조 (services 결과 + LLM output)
