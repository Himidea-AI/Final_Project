/**
 * TypeScript 타입 정의 — API 요청/응답 타입
 */

/** 시뮬레이션 요청 입력 */
export interface SimulationInput {
  business_type: "cafe" | "restaurant" | "convenience";
  brand_name: string;
  target_district: string;
  existing_stores: ExistingStore[];
  initial_investment: number;
  monthly_rent: number;
  simulation_months: number;
  scenarios: string[];
}

/** 기존 매장 정보 */
export interface ExistingStore {
  district: string;
  address: string;
  monthly_revenue: number;
}

/** 월별 매출 예측 */
export interface MonthlyProjection {
  month: number;
  revenue: number;
  cumulative_profit: number;
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
  simulation_months: number;
  monthly_projection: MonthlyProjection[];
  comparison: DistrictComparison[];
  legal_risks: LegalRisk[];
  ai_recommendation: string;
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
