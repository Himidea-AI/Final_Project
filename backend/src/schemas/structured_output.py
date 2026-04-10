from pydantic import BaseModel, Field
from typing import List, Optional

class CandidateAnalysis(BaseModel):
    """개별 후보 지역 분석 결과"""
    district_name: str = Field(..., description="행정동 명칭")
    scouting_score: float = Field(..., description="정량적 스카우팅 점수")
    pros: List[str] = Field(..., description="장점 및 기회 요인")
    cons: List[str] = Field(..., description="단점 및 리스크 요인")
    strategic_fit: str = Field(..., description="브랜드와의 전략적 적합성 요약")

class Top3ComparisonReport(BaseModel):
    """Top 3 지역 비교 및 우승자 선정 결과"""
    comparison_summary: str = Field(..., description="전체적인 후보군 대조 분석 요약")
    candidates: List[CandidateAnalysis] = Field(..., description="상위 3개 지역별 세부 분석")
    winner_district: str = Field(..., description="최종 1순위로 선정된 지역 (Winner)")
    winner_reason: str = Field(..., description="1순위 선정의 결정적 사유")

class ProfitSimulation(BaseModel):
    """수익 시뮬레이션 지표"""
    monthly_revenue: int = Field(..., description="월 예상 매출액")
    net_profit: int = Field(..., description="월 예상 순이익")
    margin_rate: float = Field(..., description="수익률 (%)")

class CompetitorAnalysis(BaseModel):
    """경쟁사 분석 요약"""
    count: int = Field(..., description="경쟁 점포 수")
    density: str = Field(..., description="경쟁 밀집도 (LOW/NORMAL/HIGH)")

class FinalStrategyResult(BaseModel):
    """최종 종합 리포트 정형 데이터 (JSON)"""
    summary: str = Field(..., description="전체 분석 요약 한 줄")
    is_direct: bool = Field(..., description="직영점 여부")
    brand_category: str = Field(..., description="브랜드 카테고리 (franchise/direct_operation)")
    overall_legal_risk: str = Field(..., description="최종 종합 리스크 레벨 (Safe/Caution/Danger)")
    profit_simulation: ProfitSimulation = Field(..., description="수익 시뮬레이션 결과")
    competitor_analysis: CompetitorAnalysis = Field(..., description="경쟁 점포 분석 결과")
    final_recommendation: str = Field(..., description="최종 전략적 제언 및 결론")
