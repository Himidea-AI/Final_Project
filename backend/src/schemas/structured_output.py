from pydantic import BaseModel, Field
from typing import List, Literal


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


class MarketAnalysisOutput(BaseModel):
    """상권 분석 에이전트 구조화 출력"""

    report: str = Field(..., description="상권 분석 리포트 본문 (전략팀 총평, 가장 큰 기회·리스크 포함)")
    grade: Literal["EXCELLENT", "GOOD", "NORMAL", "RISKY"] = Field(..., description="상권 등급")
    growth_rate: float = Field(default=0.0, description="매출 성장률 수치 (예: 3.5)")
    competition_score: float = Field(default=0.0, description="경쟁 강도 점수 0.0~1.0")
    rent_affordability: str = Field(default="중", description="임대료 적정성: 상 / 중 / 하")


class PopulationAnalysisOutput(BaseModel):
    """유동인구 분석 에이전트 구조화 출력"""

    report: str = Field(..., description="유동인구 특성 분석 리포트 본문")
    population_score: int = Field(default=5, description="유동인구 점수 1~10")
    main_target_age: str = Field(default="20~30대", description="주요 타겟 연령대 (예: 20~30대)")
    peak_time: str = Field(default="미확인", description="피크 시간대 (예: 오후 12시~2시)")


class LegalRiskItem(BaseModel):
    """개별 법률 리스크 평가 항목"""

    type: str = Field(..., description="법률 항목 식별자 (예: franchise_law, food_hygiene)")
    level: Literal["safe", "caution", "danger"] = Field(..., description="리스크 레벨")
    summary: str = Field(..., description="검토 요약 (1~2문장)")
    recommendation: str = Field(default="", description="구체적 행동 권고")


class LegalBatchOutput(BaseModel):
    """법률 에이전트 배치 LLM 구조화 출력 — 12개 법률 항목 일괄 평가"""

    items: List[LegalRiskItem] = Field(..., description="12개 법률 항목별 리스크 평가 리스트")


class FinalStrategyResult(BaseModel):
    """최종 종합 리포트 정형 데이터 (JSON)"""

    summary: str = Field(..., description="전체 분석 요약 한 줄")
    is_direct: bool = Field(..., description="직영점 여부")
    brand_category: str = Field(..., description="브랜드 카테고리 (franchise/direct_operation)")
    overall_legal_risk: str = Field(..., description="최종 종합 리스크 레벨 (Safe/Caution/Danger)")
    profit_simulation: ProfitSimulation = Field(..., description="수익 시뮬레이션 결과")
    competitor_analysis: CompetitorAnalysis = Field(..., description="경쟁 점포 분석 결과")
    final_recommendation: str = Field(..., description="최종 전략적 제언 및 결론")
