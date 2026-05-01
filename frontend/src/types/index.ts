/**
 * TypeScript 타입 정의 — API 요청/응답 타입
 */

/** 시뮬레이션 요청 입력 */
export interface SimulationInput {
  business_type: string; // "cafe" | "restaurant" | "convenience" 등 확장 가능성 고려
  business_subtype?: string;
  brand_name: string;
  target_district: string;
  target_districts?: string[];
  existing_stores: ExistingStore[];
  monthly_rent: number;
  scenarios: string[];
  // New fields (백엔드 SimulationInput 스키마와 필드명 일치)
  store_area?: number;
  target_price_range?: string;
  operating_hours?: string[];
  initial_capital?: number;
  population_weight?: boolean;
  commercial_radius?: number;
  industry_filter?: string | null;
  // [customer_revenue] 타겟 고객 프로필 (A1 찬영 P1-C 연동)
  // 값은 SegmentProfile 스펙 그대로 한글/내부키 혼용 (age: "30대", time: "time_11_14", day: "weekday|weekend")
  target_age_groups?: string[];
  target_gender?: 'male' | 'female' | null;
  target_time_slots?: string[];
  target_day_type?: 'weekday' | 'weekend' | null;
  target_monthly_sales?: number | null;
}

/** [customer_revenue] 타겟 고객 매출 분석 결과 */
export interface CustomerSegment {
  segment_ratio: number;
  segment_sales: number | null;
  identified_sales: number | null;
  total_sales_ref: number | null;
  profile_summary: string;
  dimension_ratios: Record<string, number>;
}

/** 기존 매장 정보 */
export interface ExistingStore {
  district: string;
  address: string;
  monthly_revenue: number;
}

/** 분기별 매출 예측 */
export interface QuarterlyProjection {
  quarter: number;
  revenue: number;
  cumulative_profit: number;
  confidence_lower: number;
  confidence_upper: number;
  // Track B #107 — 백엔드 2단계 CI 밴드 구현 시 자동 활성화
  ci_80_lower?: number | null;
  ci_80_upper?: number | null;
  ci_95_lower?: number | null;
  ci_95_upper?: number | null;
  is_mock?: boolean;
}

/** @deprecated monthly→quarterly 전환됨. QuarterlyProjection 사용 */
export type MonthlyProjection = QuarterlyProjection;

/** SHAP 피처 기여도 항목 */
export interface ShapFeatureItem {
  rank: number;
  feature: string; // 피처 영문명
  feature_ko: string; // 피처 한국어명
  shap_value: number; // SHAP 값 (음수: 매출 감소 기여)
  abs_shap: number; // SHAP 절댓값 (중요도 크기)
  direction: 'positive' | 'negative' | 'neutral'; // 기여 방향
}

/** SHAP 분석 결과 */
export interface ShapResult {
  feature_importance: ShapFeatureItem[]; // 중요도 내림차순 정렬
  base_value: number; // SHAP 기준 예측값
  predicted_value: number; // 모델 예측 매출액
  predicted_value_unit: string; // 단위 (예: "원")
  summary?: string[]; // 자연어 요약 문장 목록
  is_mock: boolean; // mock 데이터 여부
}

/** 동별 비교 결과 */
export interface DistrictComparison {
  district: string;
  // 2026-04-27: scouting_results 미실행 시 backend가 score/revenue/bep/survival/cannibalization
  // 모두 None으로 보냄 (거짓 양성 회피). 5필드 전부 nullable.
  score: number | null;
  revenue: number | null;
  bep: number | null;
  survival: number | null;
  cannibalization: number | null;
}

/** 법률 리스크 — 근거 조항 (가맹사업법 등) */
export interface LegalRiskArticle {
  article_ref: string;
  content: string;
}

/** 법률 리스크 */
export interface LegalRisk {
  type: string;
  risk_level: string;
  detail: string;
  recommendation?: string;
  articles?: LegalRiskArticle[];
  checklist?: LegalChecklistItem[];
  is_fallback?: boolean;
}

/** 폐업 위험도 기여 피처 (LightGBM·TCN 공통 구조) */
export interface ClosureRiskSignal {
  feature: string;
  feature_key?: string;
  contribution: number;
}

/**
 * 과거 폐업률 추이 (B2 수지니, models/revenue_predictor)
 * 예측이 아닌 실측 누적 — closure_risk(LightGBM+TCN 예측)와 명확히 구분.
 */
export interface ClosureRate {
  closure_rate: number | null; // 최근 4분기 평균 (0~1)
  risk_level: 'safe' | 'caution' | 'danger' | 'unknown';
  monthly_closure_rates: number[]; // 12개월 월별 누적 폐업률 (실패 시 빈 배열)
}

/**
 * 폐업 위험도 결과 (B2 수지니)
 * 2026-04-27 변경: top_signals/summary → top_signals_lgbm/summary_lgbm 으로 분리되고
 * top_signals_tcn/summary_tcn 신설. UI에서 LightGBM(과거 패턴)과 TCN(시계열 흐름)
 * 두 관점을 별도 노출.
 */
export interface ClosureRisk {
  risk_score: number;
  risk_level: 'safe' | 'caution' | 'danger';
  top_signals_lgbm: ClosureRiskSignal[];
  summary_lgbm?: string[];
  top_signals_tcn: ClosureRiskSignal[]; // TCN SHAP 실패 시 빈 배열
  summary_tcn?: string[];
  is_mock: boolean;
}

/** 트렌드 전망 (trend_forecaster 에이전트) */
export interface TrendForecast {
  forecast?: {
    score?: number;
    direction?: string; // growth | stable | decline
    confidence?: string; // high | medium | low
    narrative?: string;
    key_drivers?: string[];
    risks?: string[];
    horizon_months?: number;
  };
  industry_trend?: {
    industry?: string;
    direction?: string;
    current_ratio?: number | null;
    yoy_change_pct?: number | null;
    samples?: number[]; // 월별 0~100 (최대 12)
  };
  dong_trend?: {
    dong_name?: string;
    recent_score?: number | null;
    slope_pct?: number | null;
    samples?: number[]; // 분기별 점수
    data_staleness_note?: string;
  };
  change_ix?: { change_ix_label?: string };
  macro?: {
    current_base_rate?: number | null;
    base_rate_trend?: string;
    samples?: number[]; // 12개월
    [k: string]: unknown;
  };
}

/**
 * 경쟁 매장 인텔리전스 (competitor_intel 에이전트)
 *
 * 2026-04-27: code-reviewer Medium #5 — `Record<string, unknown>` → 강타입화.
 * MarketTab/사이드바 등 사용처에서 dot access로 안전하게 접근 가능.
 * 백엔드가 추가 필드를 보내도 인터페이스 미정의 필드는 단순히 무시되므로 호환 유지.
 */
export interface CompetitorIntel {
  competition_500m?: {
    count?: number;
    /** 백엔드 v2: count의 별칭(레거시). main.py에서 둘 다 채울 수 있음. */
    total_competitors?: number;
    franchise_count?: number;
    independent_count?: number;
    saturation_level?: 'low' | 'medium' | 'high' | string;
    saturation_score?: number;
    brand_distribution?: Record<string, number>;
    samples?: Array<{
      place_name?: string | null;
      brand_name?: string | null;
      distance_m?: number | null;
      category?: string | null;
    }>;
  };
  cannibalization?: {
    estimated_revenue_impact_pct?: number | null;
    distance_bins?: Record<string, number> | null;
    closest_distance_m?: number | null;
  };
  market_entry_signal?: 'green' | 'yellow' | 'red' | string;
  differentiation_position?: string | null;
  industry_closure_trend?: {
    trend?: string;
    samples?: Array<{
      quarter?: string | number;
      closure_rate?: number | null;
      [k: string]: unknown;
    }>;
    current_closure_rate?: number | null;
    historical_avg?: number | null;
    [k: string]: unknown;
  } | null;
  key_opportunities?: string[];
  key_risks?: string[];
  recommended_actions?: string[];
  narrative?: string;
}

/** 인구통계 심층 분석 (demographic_depth 에이전트) */
export interface DemographicReport {
  core_demographic: { age: string; gender: string; share: number };
  top_3_age_groups: { age_group: string; share: number }[];
  peak_consumption_hours: string[];
  weekday_weekend_ratio: number;
  resident_visitor_ratio: number | null;
  area_income_level: string; // high | mid | low | unknown
  population_trend: string; // growing | stable | declining | unknown
  elderly_ratio: number | null;
  brand_target_match_score: number | null;
  match_rationale: string | null;
  narrative: string;
  // Track B #106 — 백엔드 peak_hour_matrix [7][24] 제공 시 자동 활성화
  peak_hour_matrix?: number[][] | null;
}

/**
 * [D — living_pop_forecast] 유동인구 피크 시간 예측 (TCN)
 *
 * predict_peak(dong_name, n_quarters=4) 반환을 backend models/interface.py가
 * dict로 한번 더 감싼 형태:
 *   { dong_code, dong_name, n_quarters, quarters: [...], is_mock }
 *
 * quarters[i].all_hours[j] — 24시간대 모두 반환 (학습 데이터에 누락 시간이
 * 있을 경우 일부 시간대가 빠질 수 있음).
 */
export interface LivingPopHourPrediction {
  time_zone: number; // 0~23
  predicted_pop: number;
  confidence_lower: number;
  confidence_upper: number;
}

export interface LivingPopQuarterPrediction {
  quarter_offset: number; // 1~n
  peak_time_zone: number; // 0~23
  peak_pop: number;
  all_hours: LivingPopHourPrediction[];
}

export interface LivingPopForecast {
  dong_code: string;
  dong_name: string;
  n_quarters: number;
  quarters: LivingPopQuarterPrediction[];
  is_mock?: boolean;
}

/**
 * [E — emerging_district] 신흥 상권 조기 감지 (LSTM Autoencoder)
 *
 * predict(dong_code, industry_code) 반환 EmergingResult dict.
 * threshold p95 = 0.041380 기준 anomaly_score 0~1 정규화.
 */
export interface EmergingSignal {
  dong_code: string;
  industry_code: string;
  anomaly_score: number; // 0~1 (1에 가까울수록 이상)
  signal: 'emerging' | 'declining' | 'normal';
  consecutive_anomaly_quarters: number;
  summary: string;
  is_mock?: boolean;
}

/** 시뮬레이션 결과 출력 */
export interface SimulationOutput {
  request_id: string;
  target_district: string;
  target_districts?: string[];
  analysis_report: string; // 줄글 리포트
  analysis_metrics: AnalysisMetrics; // 차트용 정량 데이터
  simulation_quarters?: number | null;
  is_excluded_combo?: boolean;
  quarterly_projection: QuarterlyProjection[];
  comparison: DistrictComparison[];
  legal_risks: LegalRisk[];
  ai_recommendation?: string; // 기존 호환성 유지
  map_data?: any;
  // /simulate 응답에 포함되는 chartData용 7개 정규화 지표 (0~100)
  // 2026-04-27: scouting_results 미실행 시 LLM 등급 임의 매핑(SAFE:80, GOOD:75 등)으로
  //   거짓 양성을 만들던 backend fallback을 제거 — null 또는 필드 omit으로 합의 (api-contract-frontend-input.md §3.7).
  //   프론트는 이미 null → '—' 표시 처리되어 있어 그대로 안전.
  market_report?: {
    floating_population: number | null;
    rent_index: number | null;
    competition_intensity: number | null;
    estimated_revenue: number | null;
    survival_rate: number | null;
    closure_rate: number | null;
    growth_potential: number | null;
    accessibility: number | null;
  };
  // [B1 입지 랭킹] backend main.py:301 response_data 4필드 반영
  winner_district?: string;
  top_3_candidates?: string[];
  district_rankings?: DistrictRanking[];
  overall_legal_risk?: 'safe' | 'caution' | 'danger' | string;
  // 공실 DB 로드 성공 여부 — false면 랭킹에 공실 페널티 미반영 (프론트 배지 표시용)
  vacancy_applied?: boolean;
  // [A1 재무] backend main.py:337 — 선택 필드
  financial_report?: Record<string, unknown>;
  // [B2 SHAP] TCN 피처 기여도 분석 결과
  shap_result?: ShapResult | null;
  // [B2 시나리오] 낙관/기본/비관 분기 매출 시나리오
  scenarios?: {
    optimistic: { quarter: number; revenue: number }[];
    base: { quarter: number; revenue: number }[];
    pessimistic: { quarter: number; revenue: number }[];
  } | null;
  // [B2 수지니] 과거 12개월 폐업률 추이 (실측, 예측 아님)
  closure_rate?: ClosureRate | null;
  // [B2 수지니] 폐업 위험도 분석 결과 (LightGBM + TCN 앙상블 예측)
  closure_risk?: ClosureRisk | null;
  // [PR #72] 경쟁 매장 인텔리전스 (500m 반경 카니발/포화도/차별화)
  competitor_intel?: CompetitorIntel | null;
  // [PR #71] 트렌드 전망 (trend_forecaster 에이전트)
  trend_forecast?: TrendForecast | null;
  // [PR #75] 인구통계 심층 분석 (demographic_depth 에이전트)
  demographic_report?: DemographicReport | null;
  // [Dashboard 15-section] 에이전트별 판단 근거 집계 (§11 UI 카드용)
  agent_attributions?: AgentAttribution[];
  // winner + top3 전체 동 경쟁업체 좌표 목록 (멀티동 핀용)
  all_competitor_locations?: Array<{
    id: string;
    place_name: string;
    brand_name?: string;
    lat: number;
    lng: number;
    distance_m?: number;
    is_franchise?: boolean;
    source_dong?: string;
  }>;
  // [customer_revenue] 타겟 고객 매출 분석 (스펙: dict | None)
  customer_segment?: CustomerSegment | null;
  // [D — living_pop_forecast] 유동인구 피크 시간 예측 (TCN)
  living_pop_forecast?: LivingPopForecast | null;
  // [E — emerging_district] 신흥 상권 조기 감지 (LSTM Autoencoder)
  emerging_signal?: EmergingSignal | null;
  // [synthesis.FinalStrategyResult] 종합 전략 리포트 — profit_simulation 포함
  final_report?: {
    summary?: string;
    is_direct?: boolean;
    brand_category?: string;
    overall_legal_risk?: string;
    final_recommendation?: string;
    profit_simulation?: {
      monthly_revenue?: number;
      monthly_cost?: number;
      net_profit?: number;
      margin_rate?: number;
      bep_months?: number;
    };
    competitor_analysis?: {
      count?: number;
      density?: string;
    };
  } | null;
  // [/predict 분리 호출] 동별 예측 entry 배열 — /predict 응답 합성 시 사용
  district_predictions?: DistrictPredictionResult[];
  // [/predict 분리 호출] BEP 도달까지 개월수
  bep_months?: number | null;
  // [/predict 분리 호출] 예측 월매출
  predicted_monthly_revenue?: number | null;
}

/** /predict 응답의 동별 예측 entry. spec §3 + B1 schemas/simulation_output.py 의 DistrictPredictionResult 매칭.
 * 2026-04-29 multi-district cycle: 11 필드 명세 적용 (수지니 c8ea31f 기준).
 * backend 8 필드 구현, customer_segment / living_pop_forecast / emerging_signal 3 필드 미구현 → null 가능.
 */
export interface DistrictPredictionResult {
  district: string;
  dong_code: string | null;
  is_excluded_combo: boolean;
  is_mock: boolean;
  quarterly_projection: QuarterlyProjection[];
  scenarios: {
    optimistic: { quarter: number; revenue: number }[];
    base: { quarter: number; revenue: number }[];
    pessimistic: { quarter: number; revenue: number }[];
  } | null;
  bep: Record<string, unknown> | null;
  closure_rate: Record<string, unknown> | null;
  closure_risk: Record<string, unknown> | null;
  shap_result: ShapResult | null;
  customer_segment: Record<string, unknown> | null;
  living_pop_forecast: Record<string, unknown> | null;
  emerging_signal: Record<string, unknown> | null;
}

/** /analyze/llm 응답. SimulationOutput 의 ML 필드 빠진 subset. spec §3. */
export type AnalysisOutput = Omit<
  SimulationOutput,
  | 'quarterly_projection'
  | 'closure_risk'
  | 'shap_result'
  | 'bep_months'
  | 'predicted_monthly_revenue'
  | 'district_predictions'
>;

/** 입지 랭킹 엔트리 (district_ranking_node 반환 형식) */
export interface DistrictRanking {
  rank: number;
  district: string;
  score: number;
  sales_growth: number;
  sales_score: number;
  pop_growth: number;
  pop_score: number;
  avg_rent: number;
  rent_score: number;
  vacancy_rate: number;
  zoning_risk: 'safe' | 'caution' | 'danger';
  /** 2026-04-27 변경: bep_months → bep_quarters (분기 단위) */
  bep_quarters?: number | null;
  closure_rate?: number | null;
  [key: string]: unknown;
}

export interface AnalysisMetrics {
  district_grade: 'EXCELLENT' | 'GOOD' | 'NORMAL' | 'RISKY';
  growth_rate: number;
  competition_score: number;
  rent_affordability: string;
  main_target_age?: string;
  peak_time?: string;
}

/** Job 상태 */
export interface JobStatus {
  job_id: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  progress: number;
}

/** [B1-C1 연동] 분석 결과 (지도 마커 포함) */
export interface AnalysisResult {
  status: string;
  data: {
    summary: string;
    map_data: {
      center: { lat: number; lng: number };
      markers: Array<{
        id: string;
        lat: number;
        lng: number;
        label: string;
        type: string;
      }>;
    };
    market_report: any;
    legal_report: any[];
    full_analysis: any;
  };
}

// ──────────────────────────────────────────────────────────
// Dashboard 15 섹션 통합 리포트 타입 (2026-04-21 스펙)
// ──────────────────────────────────────────────────────────

export type AgentId =
  | 'market_analyst'
  | 'population_analyst'
  | 'legal'
  | 'district_ranking'
  | 'inflow'
  | 'synthesis'
  | 'demographic_depth'
  | 'trend_forecaster'
  | 'competitor_intel';

export type AgentKind = 'LLM' | 'Python' | 'Hybrid' | 'RAG';
export type AgentStatus = 'success' | 'partial' | 'pending' | 'error' | 'skipped';

export interface AgentAttribution {
  id: AgentId;
  display_name: string;
  kind: AgentKind;
  sources: string[];
  verdict: string;
  reasoning: string;
  confidence?: number;
  status?: AgentStatus;
}

export interface ReportSection {
  id: string;
  label: string;
  number: string;
}

export interface TimelineEvent {
  monthOffset: number;
  label: string;
  type: 'milestone' | 'risk' | 'opportunity';
}

export interface LegalChecklistItem {
  text: string;
  isRequired?: boolean;
}

// ──────────────────────────────────────────────────────────
// Dashboard 3그룹 IA (2026-04-28) — 출처별 재구조
// ──────────────────────────────────────────────────────────

export type MainTab = 'predict' | 'analyze' | 'abm';

export type PredictSubTab =
  | 'sales_forecast'
  | 'financial_sim'
  | 'customer_flow'
  | 'emerging_district';

export type AnalyzeSubTab = 'ai_summary' | 'market' | 'demographic' | 'legal' | 'agent_insight';
