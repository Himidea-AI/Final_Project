"""
시뮬레이션 요청 입력 모델 — 클라이언트에서 API로 보내는 요청 스키마
"""
from pydantic import BaseModel, Field


class ExistingStoreInput(BaseModel):
    """기존 매장 정보 입력"""
    district: str
    address: str
    monthly_revenue: int = 0


class SimulationInput(BaseModel):
    """시뮬레이션 요청 입력 스키마"""
    business_type: str = Field(..., description="업종 코드 (cafe, restaurant, convenience)")
    brand_name: str = Field(..., description="브랜드명")
    target_district: str = Field(..., description="출점 후보 행정동")
    existing_stores: list[ExistingStoreInput] = Field(default_factory=list, description="기존 매장 목록")
    initial_investment: int = Field(default=150_000_000, description="초기 투자금 (원)")
    monthly_rent: int = Field(default=0, description="월 임대료 (원, 0이면 자동 추정)")
    simulation_months: int = Field(default=12, description="시뮬레이션 기간 (개월)")
    scenarios: list[str] = Field(default_factory=lambda: ["base"], description="시나리오 목록")
