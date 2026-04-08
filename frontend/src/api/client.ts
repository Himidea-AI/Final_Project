/**
 * Axios 기반 API 클라이언트 — FastAPI 백엔드와 통신
 *
 * ⚠️ [팀원 필독] ⚠️
 * USE_MOCK = true  → 백엔드 없이 프론트 독립 동작 (현실적 Mock 데이터)
 * USE_MOCK = false → 실제 FastAPI /api/* 엔드포인트 호출
 *
 * 백엔드 준비되면 USE_MOCK만 false로 바꾸면 연동 완료.
 *
 * [B1/A1 담당자 참고]
 * - Mock 응답의 구조 = 실제 API 응답 구조와 동일해야 함
 * - SimulationOutput: comparison[], legal_risks[], monthly_projection[]
 * - AnalysisResult.data.market_report: 7개 항목 (floating_population 등)
 * - 타입 정의는 src/types/index.ts 참고
 */
import axios from "axios";
import type {
  SimulationInput,
  SimulationOutput,
  JobStatus,
  AnalysisResult,
} from "../types";

const USE_MOCK = true;

const apiClient = axios.create({
  baseURL: "/api",
  timeout: 120000,
  headers: { "Content-Type": "application/json" },
});

/** 서버 상태 확인 */
export async function healthCheck() {
  if (USE_MOCK) return { status: "ok", mock: true };
  const response = await apiClient.get("/health");
  return response.data;
}

/** 시뮬레이션 실행 요청 */
export async function runSimulation(
  input: SimulationInput
): Promise<SimulationOutput> {
  if (USE_MOCK) {
    // 현실적 Mock — 백엔드 응답 형태와 동일
    return new Promise((resolve) =>
      setTimeout(
        () =>
          resolve({
            request_id: `mock-${Date.now()}`,
            target_district: input.target_district,
            simulation_months: input.simulation_months,
            monthly_projection: Array.from({ length: 12 }, (_, i) => ({
              month: i + 1,
              revenue: Math.round(2800 + Math.random() * 1200),
              cumulative_profit: Math.round((i + 1) * 400 - 3000 + Math.random() * 500),
            })),
            comparison: [
              { district: "서교동", score: 87, revenue: 3240, bep: 8, survival: 78, cannibalization: 0.32 },
              { district: "합정동", score: 82, revenue: 2980, bep: 9, survival: 74, cannibalization: 0.18 },
              { district: "망원1동", score: 79, revenue: 2760, bep: 10, survival: 71, cannibalization: 0.12 },
              { district: "연남동", score: 85, revenue: 3120, bep: 7, survival: 80, cannibalization: 0.25 },
              { district: "상암동", score: 73, revenue: 2450, bep: 12, survival: 65, cannibalization: 0.05 },
            ],
            legal_risks: [
              {
                type: "가맹사업법 영업지역 보호",
                risk_level: "HIGH",
                detail: "반경 500m 내 동일 브랜드 매장 존재. 가맹사업법 제12조의4에 따른 영업지역 침해 가능성.",
              },
              {
                type: "상가임대차보호법",
                risk_level: "MEDIUM",
                detail: "해당 상가 보증금이 환산보증금 기준 초과. 상가임대차보호법 적용 범위 확인 필요.",
              },
            ],
            ai_recommendation:
              "서교동은 유동인구 밀도와 카페 수요 지표가 높아 입점에 유리하지만, 반경 500m 내 동일 브랜드 매장(1호점)이 존재하여 카니발리제이션 위험이 32%로 산출됩니다. 합정동 또는 연남동을 대안으로 검토하시기 바랍니다.",
          }),
        2500
      )
    );
  }

  const response = await apiClient.post("/simulate", input);
  return response.data;
}

/** 상권 분석 및 지도 데이터 요청 */
export async function analyzeLocation(
  input: SimulationInput
): Promise<AnalysisResult> {
  if (USE_MOCK) {
    return new Promise((resolve) =>
      setTimeout(
        () =>
          resolve({
            status: "success",
            data: {
              summary: `${input.target_district} 분석 완료: 유동인구 상위 20%, 임대료 중간, 경쟁 강도 보통`,
              map_data: {
                center: { lat: 37.5565, lng: 126.9239 },
                markers: [
                  { id: "1", lat: 37.5565, lng: 126.9239, label: input.target_district, type: "candidate" },
                  { id: "2", lat: 37.5545, lng: 126.9219, label: "기존 1호점", type: "existing" },
                ],
              },
              market_report: {
                floating_population: 82,
                rent_index: 45,
                competition_intensity: 68,
                estimated_revenue: 74,
                survival_rate: 91,
                growth_potential: 56,
                accessibility: 78,
              },
              legal_report: [
                {
                  type: "가맹사업법 영업지역 보호",
                  risk_level: "HIGH",
                  detail: "영업지역 중첩 가능성 감지",
                },
              ],
              full_analysis: null,
            },
          }),
        2000
      )
    );
  }

  const response = await apiClient.post("/analyze", input);
  return response.data;
}

/** 시뮬레이션 리포트 조회 */
export async function getReport(
  requestId: string
): Promise<SimulationOutput> {
  const response = await apiClient.get(`/report/${requestId}`);
  return response.data;
}

/** 시뮬레이션 진행 상태 조회 */
export async function getStatus(jobId: string): Promise<JobStatus> {
  if (USE_MOCK) {
    return { job_id: jobId, status: "completed", progress: 100 };
  }
  const response = await apiClient.get(`/status/${jobId}`);
  return response.data;
}

export default apiClient;
