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
 * - SimulationOutput: comparison[], legal_risks[], quarterly_projection[]
 * - AnalysisResult.data.market_report: 7개 항목 (floating_population 등)
 * - 타입 정의는 src/types/index.ts 참고
 */
import axios from 'axios';
import type { SimulationInput, SimulationOutput, JobStatus, AnalysisResult } from '../types';

/**
 * [v11.5 멀티테넌시 사전 준비]
 * ⚠️ 임시 mock workspace ID — 데모 단일 테넌트용
 * 백엔드 RBAC 준비되면 JWT payload에서 workspace_id를 추출하여 교체 예정.
 *
 * 백엔드 합의사항 (팀 회의 결과):
 *   - Type: String (UUID 형식)
 *   - Column name: workspace_id
 *   - Delivery: FastAPI Dependency Injection
 *   - Header: X-Tenant-ID
 *   - JWT workspace_id ↔ X-Tenant-ID 이중 검증 (불일치 시 403)
 */
const MOCK_WORKSPACE_ID = 'spotter-demo-workspace-01';

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 120000,
  headers: { 'Content-Type': 'application/json' },
});

/**
 * 요청 인터셉터: 모든 API 호출에 X-Tenant-ID 헤더 자동 주입
 * Nginx → FastAPI 미들웨어가 이 헤더를 받아 workspace 컨텍스트 결정
 */
apiClient.interceptors.request.use((config) => {
  // TODO: 실제 인증 구현 시 JWT에서 workspace_id 추출하여 교체
  config.headers['X-Tenant-ID'] = MOCK_WORKSPACE_ID;
  return config;
});

/** 서버 상태 확인 */
export async function healthCheck() {
  const response = await apiClient.get('/health');
  return response.data;
}

/** 시뮬레이션 실행 요청 */
export async function runSimulation(
  input: SimulationInput,
  signal?: AbortSignal,
): Promise<SimulationOutput> {
  const response = await apiClient.post('/simulate', input, { signal });
  return response.data;
}

/** 상권 분석 및 지도 데이터 요청 */
export async function analyzeLocation(input: SimulationInput): Promise<AnalysisResult> {
  const response = await apiClient.post('/analyze', input);
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

/** 유동인구 실시간 조회 (서울 열린데이터 API) */
export async function getLivePopulation(dongs?: string[]): Promise<any> {
  const params = dongs ? `?dongs=${encodeURIComponent(dongs.join(','))}` : '';
  const response = await apiClient.get(`/population/live${params}`);
  return response.data;
}

export default apiClient;
