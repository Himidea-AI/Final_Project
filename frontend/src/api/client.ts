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
import type {
  HistoryFilterParams,
  HistoryListResponse,
  SaveSimulationPayload,
  SaveSimulationResponse,
  SimulationHistoryDetail,
} from '../types/simulationHistory';

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
 * 요청 인터셉터: 모든 API 호출에 X-Tenant-ID 헤더 + JWT Bearer 자동 주입
 * Nginx → FastAPI 미들웨어가 이 헤더를 받아 workspace 컨텍스트 결정
 */
apiClient.interceptors.request.use((config) => {
  // 현재 JWT에는 workspace_id claim이 없어 mock 워크스페이스 사용. 멀티테넌트 본격 도입 시
  // 토큰 payload에 workspace_id 추가 후 여기서 jwt_decode로 추출.
  config.headers['X-Tenant-ID'] = MOCK_WORKSPACE_ID;

  // JWT: AuthContext가 localStorage.spotter_auth에 저장한 token이 있으면 Bearer로 주입
  try {
    const raw = window.localStorage.getItem('spotter_auth');
    if (raw) {
      const parsed = JSON.parse(raw);
      const token = parsed?.token;
      if (typeof token === 'string' && token.length > 0) {
        config.headers['Authorization'] = `Bearer ${token}`;
      }
    }
  } catch {
    // localStorage 접근 실패는 무시 — 기존 엔드포인트는 Bearer 미요구
  }

  return config;
});

/**
 * 응답 인터셉터: 401 시 토큰 제거 → 다음 렌더에서 AuthContext가 로그아웃 상태로 복구.
 * 강제 리다이렉트는 ProtectedRoute가 담당 (중복 방지).
 */
apiClient.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err?.response?.status === 401) {
      try {
        const raw = window.localStorage.getItem('spotter_auth');
        if (raw) {
          const parsed = JSON.parse(raw);
          // 토큰만 드롭 — user/brand는 유지해서 재로그인 화면 UX 부드럽게
          delete parsed.token;
          window.localStorage.setItem('spotter_auth', JSON.stringify(parsed));
        }
      } catch {
        /* noop */
      }
    }
    return Promise.reject(err);
  },
);

/** 서버 상태 확인 */
export async function healthCheck() {
  const response = await apiClient.get('/health');
  return response.data;
}

/** 시뮬레이션 실행 요청 — LLM 파이프라인이라 10분까지 대기 (전역 2분으로는 캐시 miss 시 timeout) */
export async function runSimulation(
  input: SimulationInput,
  signal?: AbortSignal,
): Promise<SimulationOutput> {
  const response = await apiClient.post('/simulate', input, {
    signal,
    timeout: 600_000,
  });
  // 백엔드 응답 포맷 변화 대응:
  //   신규 (dev): {status: 'success', data: {...실제 결과...}}
  //   구형:       {...실제 결과...}
  // 양쪽 모두 호환되도록 언래핑. status=error이면 throw.
  const body = response.data;
  if (body && typeof body === 'object' && 'status' in body) {
    if (body.status === 'success' && body.data) return body.data as SimulationOutput;
    if (body.status === 'error') throw new Error(body.message || 'Simulation failed');
  }
  return body as SimulationOutput;
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

// ─────────────────────────────────────────────────────────
// simulation_history (JWT Bearer 필수 — interceptor가 자동 주입)
// ─────────────────────────────────────────────────────────

export async function saveSimulationHistory(
  payload: SaveSimulationPayload,
): Promise<SaveSimulationResponse> {
  const response = await apiClient.post('/simulation-history', payload);
  return response.data;
}

export async function listSimulationHistory(
  filter: HistoryFilterParams = {},
): Promise<HistoryListResponse> {
  const response = await apiClient.get('/simulation-history', { params: filter });
  return response.data;
}

export async function getSimulationHistoryDetail(id: number): Promise<SimulationHistoryDetail> {
  const response = await apiClient.get(`/simulation-history/${id}`);
  return response.data;
}

export async function deleteSimulationHistory(id: number): Promise<void> {
  await apiClient.delete(`/simulation-history/${id}`);
}

export default apiClient;
