"""
시뮬레이션 결과 출력 모델 — API에서 클라이언트로 반환하는 결과 스키마
"""
from pydantic import BaseModel, Field


class MonthlyProjection(BaseModel):
    """월별 매출 및 수익 예측"""
    month: int
    revenue: int = 0
    cumulative_profit: int = 0


class DistrictComparison(BaseModel):
    """동별 비교 결과"""
    district: str
    score: float = 0.0
    revenue: int = 0
    bep: int = 0
    survival: float = 0.0
    cannibalization: float = 0.0


class LegalRisk(BaseModel):
    """법률 리스크 항목"""
    type: str
    risk_level: str
    detail: str


class SimulationOutput(BaseModel):
    """시뮬레이션 결과 출력 스키마"""
    request_id: str
    target_district: str
    simulation_months: int
    monthly_projection: list[MonthlyProjection] = Field(default_factory=list)
    comparison: list[DistrictComparison] = Field(default_factory=list)
    legal_risks: list[LegalRisk] = Field(default_factory=list)
    ai_recommendation: str = ""
