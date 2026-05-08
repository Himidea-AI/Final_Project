"""
시뮬레이션 결과 출력 모델 — API에서 클라이언트로 반환하는 결과 스키마
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class QuarterlyProjection(BaseModel):
    """분기별 매출 및 수익 예측 (B2 TCN + BEP 결합)"""

    quarter: int
    revenue: int = 0
    cumulative_profit: int = 0
    confidence_lower: int = 0
    confidence_upper: int = 0
    ci_80_lower: int | None = None
    ci_80_upper: int | None = None
    ci_95_lower: int | None = None
    ci_95_upper: int | None = None
    is_mock: bool = False


# 하위 호환성 유지
MonthlyProjection = QuarterlyProjection


class DistrictComparison(BaseModel):
    """동별 비교 결과"""

    district: str
    score: float | None = None
    revenue: int | None = None
    bep: int | None = None
    survival: float | None = None
    cannibalization: float | None = None


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
    checklist: list[dict] = Field(default_factory=list)
    is_fallback: bool = False


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

    floating_population: int | None = None
    rent_index: int | None = None
    competition_intensity: int | None = None
    estimated_revenue: int | None = None
    survival_rate: int | None = None
    closure_rate: float | None = None
    growth_potential: int | None = None
    accessibility: int | None = None


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
    # 2026-05-02: 프론트 "동 검색량 16동 중 N위" 표시용으로 응답에 추가.
    # 기존엔 schema 미정의로 직렬화 시 drop 됨. None 허용 — 데이터 결측 동 대응.
    trend_score: float | None = None
    density_score: float | None = None
    inflow_score: float | None = None
    vacancy_rate: float = 0.0
    zoning_risk: str | None = None
    bep_quarters: int | None = None
    closure_rate: float | None = None


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
    summary: list[str] = Field(default_factory=list)
    is_mock: bool  # mock 데이터 여부


class SimulationOutput(BaseModel):
    """시뮬레이션 결과 출력 스키마"""

    request_id: str
    target_district: str
    target_districts: list[str] = Field(default_factory=list)
    simulation_quarters: int | None = None
    is_excluded_combo: bool = False
    quarterly_projection: list[QuarterlyProjection] = Field(default_factory=list)
    comparison: list[DistrictComparison] = Field(default_factory=list)
    overall_legal_risk: str | None = None
    legal_risks: list[LegalRisk] = Field(default_factory=list)
    analysis_report: str = ""
    analysis_metrics: dict = Field(default_factory=dict)
    map_data: MapData | None = None
    financial_report: dict = Field(default_factory=dict)
    ai_recommendation: str = ""
    market_report: MarketReport | None = None
    winner_district: str | None = None
    top_3_candidates: list[str] = Field(default_factory=list)
    district_rankings: list[DistrictRanking] = Field(default_factory=list)
    vacancy_applied: bool = False
    vacancy_spots: list[dict] = Field(default_factory=list)
    # TCN SHAP 분석 결과 (없으면 None)
    shap_result: ShapResult | None = None
    scenarios: dict | None = None
    # 과거 12개월 폐업률 추이 (예측 아님 — 실측 누적). 키: closure_rate, risk_level, monthly_closure_rates
    closure_rate: dict | None = None
    closure_risk: dict | None = None
    competitor_intel: dict | None = None
    trend_forecast: dict | None = None
    demographic_report: dict | None = None
    agent_attributions: list[dict] = Field(default_factory=list)
    all_competitor_locations: list[dict] = Field(default_factory=list)
    # winner+top3 4동 안 자사 브랜드 매장 좌표 — 지도 자사 매장 마커(로고 아이콘) + 영업구역 반경 원 표시용.
    # 항목 키: id, place_name, brand_name, lat, lng, dong_name, address
    same_brand_locations: list[dict] = Field(default_factory=list)
    # [customer_revenue P1-C] 타겟 고객 매출 분석 — dict | None (predict.py 반환값 그대로)
    # 키: segment_ratio, segment_sales, identified_sales, total_sales_per_store, profile_summary, dimension_ratios
    customer_segment: dict | None = None
    # [D — living_pop_forecast P1-D] 유동인구 피크 시간 예측 (TCN). dict | None
    # 키: dong_code, dong_name, n_quarters, quarters[{quarter_offset, peak_time_zone, peak_pop, all_hours}], is_mock
    living_pop_forecast: dict | None = None
    # [E — emerging_district P1-E] 신흥 상권 조기 감지 (LSTM Autoencoder). dict | None
    # 키: dong_code, industry_code, anomaly_score, signal('emerging'|'declining'|'normal'), consecutive_anomaly_quarters, summary, is_mock
    emerging_signal: dict | None = None
    final_report: dict | None = None


class DistrictPredictionResult(BaseModel):
    """동별 ML 예측 결과 (/predict 엔드포인트 응답 단위)"""

    district: str
    dong_code: str | None = None
    is_excluded_combo: bool = False
    is_mock: bool = False
    quarterly_projection: list[QuarterlyProjection] = Field(default_factory=list)
    scenarios: dict | None = None
    bep: dict | None = None
    closure_rate: dict | None = None
    closure_risk: dict | None = None
    shap_result: ShapResult | None = None
    customer_segment: dict | None = None
    living_pop_forecast: dict | None = None
    emerging_signal: dict | None = None


# ---------------------------------------------------------------------------
# IM3-259 — AI 분석 응답 스키마 (/analyze/llm)
# ---------------------------------------------------------------------------
# /predict (TCN/ML 단발)와 독립적으로 호출되는 LLM 분석 endpoint 응답.
# slow_graph(inflow + ranking + llm_analysis + synthesis) 산출물.
# ml_prediction은 포함하지 않으며, 그 결과는 /predict의 DistrictPredictionResult로 분리.
# ---------------------------------------------------------------------------


class CompetitorIntel(BaseModel):
    """competitor_intel_node 산출 — LLM 합성 + 정량 데이터 혼재.

    핵심 필드만 strict하게 정의하고 nested(brand_benchmark, cannibalization,
    competition_500m, industry_closure_trend)는 일단 dict로 유지.
    extra='allow'로 미정의 필드도 통과시켜 점진적 strict typing 가능.
    """

    model_config = ConfigDict(extra="allow")

    market_entry_signal: Literal["green", "yellow", "red"] | None = None
    differentiation_position: str | None = None
    key_opportunities: list[str] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    narrative: str | None = None
    cannibalization: dict | None = None
    industry_closure_trend: dict | None = None
    competition_500m: dict | None = None
    brand_benchmark: dict | None = None
    adjusted_estimated_revenue: float | None = None
    meta: dict | None = None


class AnalysisOutput(BaseModel):
    """LLM 분석 결과 — POST /analyze/llm 응답.

    inflow + ranking + LLM 6 에이전트 + synthesis 산출물.
    /predict (DistrictPredictionResult list) 와 독립 병렬 호출 가능.
    """

    request_id: str
    target_district: str
    target_districts: list[str] = Field(default_factory=list)
    business_type: str | None = None
    brand_name: str | None = None
    winner_district: str | None = None
    top_3_candidates: list[str] = Field(default_factory=list)
    district_rankings: list[DistrictRanking] = Field(default_factory=list)
    vacancy_applied: bool = False
    vacancy_spots: list[dict] = Field(default_factory=list)
    legal_risks: list[LegalRisk] = Field(default_factory=list)
    overall_legal_risk: str | None = None
    market_report: MarketReport | None = None
    competitor_intel: CompetitorIntel | None = None
    trend_forecast: dict | None = None
    demographic_report: dict | None = None
    agent_attributions: list[dict] = Field(default_factory=list)
    all_competitor_locations: list[dict] = Field(default_factory=list)
    same_brand_locations: list[dict] = Field(default_factory=list)
    analysis_report: str = ""
    ai_recommendation: str = ""
    final_report: dict | None = None
    financial_report: dict = Field(default_factory=dict)
    analysis_metrics: dict = Field(default_factory=dict)
    map_data: MapData | None = None
    # IM3-144 정합 (2026-05-02): SimulationOutput 에는 있지만 AnalysisOutput 누락이던 3 필드.
    # main.py:941 의 schema 필터 (`AnalysisOutput.model_fields.keys()`) 가 이 필드를 응답에서
    # 제거 → frontend 의 CustomerSegmentCard / LivingPopForecast / EmergingSignal 이 placeholder
    # 로 표시되던 회귀 차단.
    customer_segment: dict | None = None
    living_pop_forecast: dict | None = None
    emerging_signal: dict | None = None
