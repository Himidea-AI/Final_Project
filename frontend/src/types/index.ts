/**
 * TypeScript 타입 정의 — API 요청/응답 타입
 */

/** 시뮬레이션 요청 입력 */
export interface SimulationInput {
  business_type: string; // "cafe" | "restaurant" | "convenience" 등 확장 가능성 고려
  business_subtype?: string;
  brand_name: string;
  target_district: string;
  existing_stores: ExistingStore[];
  initial_investment: number;
  monthly_rent: number;
  simulation_months: number;
  scenarios: string[];
  // New fields (백엔드 SimulationInput 스키마와 필드명 일치)
  store_area?: number;
  target_price_range?: string;
  operating_hours?: string[];
  initial_capital?: number;
  population_weight?: boolean;
  commercial_radius?: number;
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
  is_mock: boolean; // mock 데이터 여부
}

/** 동별 비교 결과 */
export interface DistrictComparison {
  district: string;
  score: number;
  revenue: number;
  bep: number;
  survival: number;
  cannibalization: number;
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
}

/** 폐업 위험도 기여 피처 */
export interface ClosureRiskSignal {
  feature: string;
  contribution: number;
}

/** 폐업 위험도 결과 (B2 수지니) */
export interface ClosureRisk {
  risk_score: number;
  risk_level: 'safe' | 'caution' | 'danger';
  top_signals: ClosureRiskSignal[];
  is_mock: boolean;
}

/** 트렌드 전망 (trend_forecaster 에이전트) */
export interface TrendForecast {
  forecast?: {
    score?: number;
    direction?: string; // growth | stable | decline
    confidence?: string; // high | medium | low
    narrative?: string;
  };
  industry_trend?: { direction?: string }; // up | flat | down
  change_ix?: { change_ix_label?: string }; // 상권확장 | 상권유지 | 상권축소 | 상권쇠퇴
  macro?: Record<string, unknown>;
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
}

/** 시뮬레이션 결과 출력 */
export interface SimulationOutput {
  request_id: string;
  target_district: string;
  analysis_report: string; // 줄글 리포트
  analysis_metrics: AnalysisMetrics; // 차트용 정량 데이터
  simulation_months: number;
  quarterly_projection: QuarterlyProjection[];
  comparison: DistrictComparison[];
  legal_risks: LegalRisk[];
  ai_recommendation?: string; // 기존 호환성 유지
  map_data?: any;
  // /simulate 응답에 포함되는 chartData용 7개 정규화 지표 (0~100)
  market_report?: {
    floating_population: number;
    rent_index: number;
    competition_intensity: number;
    estimated_revenue: number;
    survival_rate: number;
    closure_rate: number | null;
    growth_potential: number;
    accessibility: number;
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
  // [B2 수지니] 폐업 위험도 분석 결과
  closure_risk?: ClosureRisk | null;
  // [PR #72] 경쟁 매장 인텔리전스 (500m 반경 카니발/포화도/차별화)
  competitor_intel?: Record<string, unknown> | null;
  // [PR #71] 트렌드 전망 (trend_forecaster 에이전트)
  trend_forecast?: TrendForecast | null;
  // [PR #75] 인구통계 심층 분석 (demographic_depth 에이전트)
  demographic_report?: DemographicReport | null;
  // [Dashboard 15-section] 에이전트별 판단 근거 집계 (§11 UI 카드용)
  agent_attributions?: AgentAttribution[];
}

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
  bep_months?: number | null;
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
  | 'synthesis'
  | 'demographic_depth'
  | 'trend_forecaster'
  | 'competitor_intel';

export type AgentKind = 'LLM' | 'Python' | 'Hybrid' | 'RAG';

export interface AgentAttribution {
  id: AgentId;
  display_name: string;
  kind: AgentKind;
  sources: string[];
  verdict: string;
  reasoning: string;
  confidence?: number;
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
