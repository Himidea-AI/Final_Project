"""
시뮬레이션 결과 출력 모델 — API에서 클라이언트로 반환하는 결과 스키마
"""

from pydantic import BaseModel, Field


class QuarterlyProjection(BaseModel):
    """분기별 매출 및 수익 예측 (B2 TCN + BEP 결합)"""

    quarter: int
    revenue: int = 0
    cumulative_profit: int = 0
    confidence_lower: int = 0
    confidence_upper: int = 0


# 하위 호환성 유지
MonthlyProjection = QuarterlyProjection


class DistrictComparison(BaseModel):
    """동별 비교 결과"""

    district: str
    score: float = 0.0
    revenue: int = 0
    bep: int = 0
    survival: float = 0.0
    cannibalization: float = 0.0


class LegalRiskArticle(BaseModel):
    article_ref: str
    content: str


class LegalRisk(BaseModel):
    """법률 리스크 항목"""

    type: str
    risk_level: str
    detail: str
    recommendation: str = ""
    articles: list[LegalRiskArticle] = Field(default_factory=list)


class MapCenter(BaseModel):
    lat: float
    lng: float


class MapMarker(BaseModel):
    id: str
    lat: float
    lng: float
    label: str
    type: str


class MapData(BaseModel):
    center: MapCenter
    markers: list[MapMarker] = Field(default_factory=list)


class MarketReport(BaseModel):
    """프론트엔드 차트용 7개 정규화 지표 (0~100)"""

    floating_population: int = 0
    rent_index: int = 50
    competition_intensity: int = 0
    estimated_revenue: int = 60
    survival_rate: int = 30
    growth_potential: int = 0
    accessibility: int = 75


class DistrictRanking(BaseModel):
    """입지 랭킹 엔트리 (district_ranking_node 반환 형식)"""

    rank: int = 0
    district: str
    score: float = 0.0
    sales_growth: float = 0.0
    pop_growth: float = 0.0
    avg_rent: float = 0.0
    sales_score: float = 0.0
    pop_score: float = 0.0
    rent_score: float = 0.0
    vacancy_rate: float = 0.0


class ShapFeatureItem(BaseModel):
    """SHAP 피처별 기여도 항목"""

    rank: int
    feature: str  # 피처 영문명
    feature_ko: str  # 피처 한국어명
    shap_value: float  # SHAP 값 (음수: 매출 감소 기여)
    abs_shap: float  # SHAP 절댓값 (중요도 크기)
    direction: str  # "positive" | "negative" | "neutral"


class ShapResult(BaseModel):
    """TCN 모델 SHAP 분석 결과 — explain_tcn_prediction() 반환값과 동일 구조"""

    feature_importance: list[ShapFeatureItem]  # 중요도 내림차순 정렬
    base_value: float  # SHAP expected_value (기준 예측값)
    predicted_value: float  # 모델 예측 매출액
    predicted_value_unit: str = "원"  # 단위 (생존률 모델과 구별)
    is_mock: bool  # mock 데이터 여부


class SimulationOutput(BaseModel):
    """시뮬레이션 결과 출력 스키마"""

    request_id: str
    target_district: str
    simulation_months: int = 12
    quarterly_projection: list[QuarterlyProjection] = Field(default_factory=list)
    comparison: list[DistrictComparison] = Field(default_factory=list)
    overall_legal_risk: str = "safe"
    legal_risks: list[LegalRisk] = Field(default_factory=list)
    analysis_report: str = ""
    analysis_metrics: dict = Field(default_factory=dict)
    map_data: MapData | None = None
    financial_report: dict = Field(default_factory=dict)
    ai_recommendation: str = ""
    market_report: MarketReport | None = None
    winner_district: str = ""
    top_3_candidates: list[str] = Field(default_factory=list)
    district_rankings: list[DistrictRanking] = Field(default_factory=list)
    # TCN SHAP 분석 결과 (없으면 None)
    shap_result: ShapResult | None = None
    # [customer_revenue P1-C] 타겟 고객 매출 분석 — dict | None (predict.py 반환값 그대로)
    # 키: segment_ratio, segment_sales, identified_sales, total_sales_ref, profile_summary, dimension_ratios
    customer_segment: dict | None = None
