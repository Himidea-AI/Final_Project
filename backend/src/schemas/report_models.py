"""
리포트 출력 모델 — 최종 보고서 구조
"""
from pydantic import BaseModel, Field


class RiskItem(BaseModel):
    """리스크 항목 — interface_spec.md의 legal_risks 스키마와 필드명 일치"""
    type: str
    risk_level: str
    detail: str
    mitigation: str = ""


class RecommendationItem(BaseModel):
    """추천 항목"""
    district: str
    rank: int
    reason: str
    score: float = 0.0


class SimulationReport(BaseModel):
    """최종 시뮬레이션 보고서"""
    request_id: str
    executive_summary: str = ""
    recommendations: list[RecommendationItem] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)
    detailed_analysis: str = ""
    generated_at: str = ""
