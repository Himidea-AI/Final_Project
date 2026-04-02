from typing import Optional
from sqlmodel import SQLModel, Field

class SimulationRequest(SQLModel):
    """프론트엔드로부터 전달받는 시뮬레이션 요청 조건"""
    target_dong: str = Field(..., description="마포구 행정동 이름 (예: 망원1동)")
    business_type: str = Field(..., description="원하는 업종 코드 또는 이름")
    budget: int = Field(..., description="가용 예산 (만 원 단위)")
    persona: Optional[str] = Field(default=None, description="페르소나 (예: 창업자, 프랜차이즈, 소상공인 컨설턴트)")

class SimulationResult(SQLModel):
    """시뮬레이션이 최종적으로 프론트엔드로 반환하는 결과"""
    market_score: float = Field(0.0, description="상권 매력도 점수 (1~100)")
    expected_monthly_revenue: int = Field(0, description="예상 월 매출액")
    bep_months: int = Field(0, description="흑자 전환 시점 (개월 수)")
    survival_rate_12m: float = Field(0.0, description="12개월 생존 확률 (%)")
    strategy_recommendation: str = Field("", description="AI의 핵심 조언 및 전략 추천")
