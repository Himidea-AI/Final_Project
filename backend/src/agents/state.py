"""
AgentState — 모든 Agent가 공유하는 상태 객체.
LangGraph의 StateGraph에서 사용.
"""
from typing import Any, Optional
from pydantic import BaseModel, Field


class ExistingStore(BaseModel):
    """기존 매장 정보"""
    district: str
    address: str
    monthly_revenue: int = 0


class DistrictData(BaseModel):
    """행정동 분석 데이터"""
    floating_population: dict = Field(default_factory=dict)
    resident_population: dict = Field(default_factory=dict)
    competition: dict = Field(default_factory=dict)
    rent_avg: int = 0
    closure_rate: float = 0.0


class AnalysisResults(BaseModel):
    """분석 결과"""
    location_score: float = 0.0
    estimated_monthly_revenue: int = 0
    bep_months: int = 0
    survival_probability_12m: float = 0.0
    cannibalization_impact: dict = Field(default_factory=dict)
    legal_risks: list = Field(default_factory=list)


class AgentState(BaseModel):
    """
    LangGraph 전체 워크플로우에서 공유되는 상태.
    모든 Agent는 이 상태를 읽고 자기 결과를 추가.
    """
    request_id: str = ""
    business_type: str = ""
    brand_name: str = ""
    target_district: str = ""
    existing_stores: list[ExistingStore] = Field(default_factory=list)
    district_data: Optional[DistrictData] = None
    analysis_results: Optional[AnalysisResults] = None
    report: Optional[str] = None
    iteration_count: int = 0
    status: str = "pending"
    errors: list[str] = Field(default_factory=list)
