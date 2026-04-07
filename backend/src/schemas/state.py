from typing import TypedDict, Annotated, Sequence, Any, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class MarketData(TypedDict, total=False):
    """상권분석 데이터 객체 (Track A 제공 데이터 구조)"""
    district: str
    lat: float                # 위도
    lng: float                # 경도
    floating_population: dict[str, Any]
    resident_population: dict[str, Any]
    competition_score: float
    average_rent: int
    business_density: dict[str, int]
    financial_metrics: dict[str, Any] # 추가: 수익성 분석용 데이터 (임대료, 인건비 등)

class AgentState(TypedDict):
    """LangGraph 워크플로우에서 공유되는 에이전트 상태"""
    # 1. 대화 내역 (add_messages를 통해 순차적으로 축적)
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # 2. 사용자 요청 파라미터
    business_type: str        # 업종 (예: 카페)
    brand_name: str           # 브랜드명
    target_district: str      # 분석 대상 행정동
    
    # 3. 데이터 슬롯 (Track A 및 RAG 결과물 저장)
    market_data: MarketData   # DB에서 가져올 상권 데이터 객체
    # 수정: 단순 텍스트 리스트가 아닌 상세 정보(content, relevance 등)가 담긴 객체 리스트
    legal_info: list[dict[str, Any]]  
    
    # 4. 분석 결과 및 상태 제어
    analysis_results: dict[str, Any]
    current_agent: str        # 현재 작업을 수행 중인 에이전트명
    next_step: str            # Supervisor가 결정한 다음 단계
    errors: list[str]
