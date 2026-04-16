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
  feature: string;       // 피처 영문명
  feature_ko: string;    // 피처 한국어명
  shap_value: number;    // SHAP 값 (음수: 매출 감소 기여)
  abs_shap: number;      // SHAP 절댓값 (중요도 크기)
  direction: 'positive' | 'negative' | 'neutral';  // 기여 방향
}

/** SHAP 분석 결과 */
export interface ShapResult {
  feature_importance: ShapFeatureItem[];  // 중요도 내림차순 정렬
  base_value: number;                     // SHAP 기준 예측값
  predicted_value: number;               // 모델 예측 매출액
  predicted_value_unit: string;          // 단위 (예: "원")
  is_mock: boolean;                      // mock 데이터 여부
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

/** 법률 리스크 */
export interface LegalRisk {
  type: string;
  risk_level: string;
  detail: string;
}

/** 시뮬레이션 결과 출력 */
export interface SimulationOutput {
  request_id: string;
  target_district: string;
  analysis_report: string;    // 줄글 리포트
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
    growth_potential: number;
    accessibility: number;
  };
  // [B1 입지 랭킹] backend main.py:301 response_data 4필드 반영
  winner_district?: string;
  top_3_candidates?: string[];
  district_rankings?: DistrictRanking[];
  overall_legal_risk?: 'safe' | 'caution' | 'danger' | string;
  // [A1 재무] backend main.py:337 — 선택 필드
  financial_report?: Record<string, unknown>;
  // [B2 SHAP] TCN 피처 기여도 분석 결과
  shap_result?: ShapResult | null;
}

/** 입지 랭킹 엔트리 (district_ranking_node 반환 형식) */
export interface DistrictRanking {
  district: string;
  score: number;
  [key: string]: unknown; // 노드별 확장 필드 허용
}

export interface AnalysisMetrics {
  district_grade: 'EXCELLENT' | 'GOOD' | 'NORMAL' | 'RISKY';
  growth_rate: number;
  competition_score: number;
  rent_affordability: string;
}

/** Job 상태 */
export interface JobStatus {
  job_id: string;
  status: "pending" | "in_progress" | "completed" | "failed";
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
