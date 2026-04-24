from pydantic import BaseModel, Field
from typing import List, Literal, Optional


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
    bep_months: Optional[int] = Field(default=None, description="손익분기점 도달 개월 수 (TCN 예측값)")


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
    summary: str = Field(..., description="법률 개요 — 해당 법률의 목적과 핵심 의무 (1~2문장)")
    recommendation: str = Field(
        default="",
        description="업종·지역 맞춤 창업 체크리스트 (bullet point '•' 사용, 위반 시 제재 포함)",
    )


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


class CompetitorIntelOutput(BaseModel):
    """경쟁 지형·카니발·차별화 전략 LLM 구조화 출력."""

    market_entry_signal: Literal["green", "yellow", "red"] = Field(
        ..., description="시장 진입 신호등 (green=진입 권장, yellow=조건부, red=비권장)"
    )
    differentiation_position: str = Field(..., description="경쟁 지형 내 브랜드의 차별화 포지셔닝 한 줄 요약")
    key_opportunities: List[str] = Field(default_factory=list, description="포착해야 할 기회 요소 2~4개")
    key_risks: List[str] = Field(default_factory=list, description="주의해야 할 리스크 요소 2~4개")
    recommended_actions: List[str] = Field(default_factory=list, description="본사 영업팀 추천 액션 2~4개")
    narrative: str = Field(..., description="3~5줄 본사 보고용 경쟁 상황·카니발·권고 종합 서술")


# ──────────────────────────────────────────────────────────
# Dashboard 15 섹션 통합 리포트 — AgentAttribution (2026-04-21 스펙)
# ──────────────────────────────────────────────────────────

AgentIdLiteral = Literal[
    "market_analyst",
    "population_analyst",
    "legal",
    "district_ranking",
    "operational_fit",
    "synthesis",
    "demographic_depth",
    "trend_forecaster",
    "competitor_intel",
]

AgentKindLiteral = Literal["LLM", "Python", "Hybrid", "RAG"]


class AgentAttribution(BaseModel):
    """각 에이전트의 판단 근거 — §11 UI 카드 + 섹션별 compact 카드 공통 데이터.

    각 노드가 반환 시 agent_attribution 필드에 dict로 넣고,
    synthesis가 agent_attributions[] 배열로 집계하여 API response에 포함.
    """

    id: AgentIdLiteral
    display_name: str = Field(description="사람이 읽는 에이전트 이름 (예: '경쟁 인텔')")
    kind: AgentKindLiteral
    sources: list[str] = Field(description="사용한 DB 테이블·모델명 (chip으로 표시)")
    verdict: str = Field(description="한 줄 판단 (80자 내)")
    reasoning: str = Field(description="2-3 문장 설명")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
