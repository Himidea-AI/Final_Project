/**
 * Axios 기반 API 클라이언트 — FastAPI 백엔드와 통신
 */
import axios from "axios";
import type { SimulationInput, SimulationOutput, JobStatus } from "../types";

const USE_MOCK = false; // 프론트엔드 테스트를 위해 강제 Mock 모드 (해제 완료)

const apiClient = axios.create({
  baseURL: "http://localhost:8000",
  timeout: 120000, // 시뮬레이션 최대 120초 (Ollama 추론 고려)
  headers: {
    "Content-Type": "application/json",
  },
});

/** 서버 상태 확인 */
export async function healthCheck() {
  const response = await apiClient.get("/health");
  return response.data;
}

/** 시뮬레이션 실행 요청 */
export async function runSimulation(input: SimulationInput): Promise<SimulationOutput> {
  if (USE_MOCK) {
    console.log("[Mock API] runSimulation called with:", input);
    return new Promise((resolve) => setTimeout(() => resolve({
      request_id: "mock-12345",
      target_district: input.target_district,
      simulation_months: input.simulation_months,
      monthly_projection: [],
      comparison: [],
      legal_risks: [],
      ai_recommendation: "모의 테스트 응답 결과: 이 지역은 유동인구가 많아 카페 입점에 유리합니다."
    }), 1000));
  }

  const response = await apiClient.post("/simulate", input);
  return response.data;
}

/** 시뮬레이션 리포트 조회 */
export async function getReport(requestId: string): Promise<SimulationOutput> {
  const response = await apiClient.get(`/report/${requestId}`);
  return response.data;
}

/** 시뮬레이션 진행 상태 조회 */
export async function getStatus(jobId: string): Promise<JobStatus> {
  const response = await apiClient.get(`/status/${jobId}`);
  return response.data;
}

export default apiClient;
