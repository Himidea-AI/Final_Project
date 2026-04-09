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



const apiClient = axios.create({
  baseURL: "/api",
  timeout: 120000,
  headers: { "Content-Type": "application/json" },
});

/** 서버 상태 확인 */
export async function healthCheck() {
  const response = await apiClient.get("/health");
  return response.data;
}

/** 시뮬레이션 실행 요청 */
export async function runSimulation(
  input: SimulationInput
): Promise<SimulationOutput> {
  const response = await apiClient.post("/simulate", input);
  return response.data;
}

/** 상권 분석 및 지도 데이터 요청 */
export async function analyzeLocation(
  input: SimulationInput
): Promise<AnalysisResult> {
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
  const response = await apiClient.get(`/status/${jobId}`);
  return response.data;
}

export default apiClient;
