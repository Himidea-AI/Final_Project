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

    # 사용자 입력 확장 파라미터
    store_area: float = Field(default=15.0, description="점포 면적 (평)")
    target_price_range: str = Field(default="5to10k", description="목표 객단가 구간 (예: 5to10k, 10to15k)")
    operating_hours: list[str] = Field(default_factory=lambda: ["점심", "저녁"], description="주 타겟 영업 시간대")
    initial_capital: int = Field(default=50_000_000, description="초기 자본금 (원)")
    commercial_radius: int = Field(default=500, description="상권 분석 반경 (m)")
    population_weight: bool = Field(default=True, description="인구 가중치 반영 여부")
