/**
 * Axios 기반 API 클라이언트 — FastAPI 백엔드와 통신
 */
import axios from "axios";
import type { SimulationInput, SimulationOutput, JobStatus } from "../types";

const apiClient = axios.create({
  baseURL: "/api",
  timeout: 60000, // 시뮬레이션 최대 60초
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
