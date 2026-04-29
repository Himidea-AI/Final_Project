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
 * - DistrictPredictionResult: quarterly_projection, closure_risk, shap_result, bep_months, predicted_monthly_revenue, ...
 * - AnalysisOutput: winner_district + market_report 7개 항목 (floating_population 등)
 * - 타입 정의는 src/types/index.ts 참고
 *
 * [IM3-259] /simulate 단일 엔드포인트는 제거됨. 신규 호출은 runPredict + runAnalyzeLlm.
 */
import axios from 'axios';
import type {
  SimulationInput,
  SimulationOutput,
  JobStatus,
  CustomerSegment,
  DistrictPredictionResult,
  AnalysisOutput,
} from '../types';
import type {
  HistoryFilterParams,
  HistoryListResponse,
  SaveSimulationPayload,
  SaveSimulationResponse,
  SimulationHistoryDetail,
} from '../types/simulationHistory';
import type { TokenUsageResponse } from '../types/tokenUsage';

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
 * 응답 인터셉터: 401 시 세션 전체 파기 + /login 강제 이동.
 *
 * 이전에는 token만 drop하고 user/brand는 유지했으나 → UI는 "로그인됨"인데
 * 모든 API가 401로 깨지는 zombie 상태가 발생. 표준 SPA 패턴으로 교체.
 *
 * redirect 쿼리에 원래 가려던 경로를 실어서 로그인 후 복귀시킴.
 * 이미 /login 경로에 있으면 루프 방지.
 */
apiClient.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err?.response?.status === 401) {
      try {
        window.localStorage.removeItem('spotter_auth');
      } catch {
        /* noop */
      }
      try {
        const { pathname, search, hash } = window.location;
        if (pathname !== '/login') {
          const from = `${pathname}${search}${hash}`;
          const redirect = encodeURIComponent(from);
          window.location.assign(`/login?reason=session_expired&redirect=${redirect}`);
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

/**
 * ML 예측 — /predict (선택 동 1~4 병렬). 사용자 입력 그대로.
 *
 * 응답 포맷 (backend 수지니 c8ea31f):
 *   { status: "success" | "error", data: DistrictPredictionResult[], message?: string }
 *
 * timeout 300_000 — 4동 병렬 ML 추론 + ECOS/외부 호출 여유.
 */
export async function runPredict(
  input: SimulationInput,
  signal?: AbortSignal,
): Promise<DistrictPredictionResult[]> {
  const response = await apiClient.post('/predict', input, { signal, timeout: 300_000 });
  const body = response.data;
  if (body && body.status === 'success' && Array.isArray(body.data)) return body.data;
  if (body && body.status === 'error') throw new Error(body.message || 'Predict failed');
  if (Array.isArray(body)) return body; // legacy
  return [];
}

/**
 * AI 분석 — /analyze/llm (winner 산출 + LLM 6 에이전트).
 *
 * timeout 300_000 — LLM 멀티에이전트 파이프라인.
 *
 * 응답 wrapper: backend (찬영 8223bfb contract 보강) 가 `{ status, data: AnalysisOutput }` 형태 반환.
 *   - LLM_AGENTS_DISABLED=1 mock 도 동일 wrapper.
 *   - error 시 `{ status: "error", message }`.
 */
export async function runAnalyzeLlm(
  input: SimulationInput,
  signal?: AbortSignal,
): Promise<AnalysisOutput> {
  const response = await apiClient.post('/analyze/llm', input, { signal, timeout: 300_000 });
  const body = response.data;
  if (body && body.status === 'success' && body.data) return body.data as AnalysisOutput;
  if (body && body.status === 'error') throw new Error(body.message || 'Analyze LLM failed');
  return body as AnalysisOutput; // legacy raw fallback
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
// customer_segment — /simulate와 무관한 독립 호출 (~100ms MLP 미리보기)
// ─────────────────────────────────────────────────────────

export interface CustomerSegmentRequest {
  target_district: string;
  business_type: string;
  target_age_groups: string[];
  target_gender: 'male' | 'female' | null;
  target_time_slots: string[];
  target_day_type: 'weekday' | 'weekend' | null;
  target_monthly_sales: number | null;
  quarter_num?: number;
}

/** customer_revenue MLP 직접 호출 — /simulate와 무관, ~100ms */
export async function fetchCustomerSegment(
  req: CustomerSegmentRequest,
  signal?: AbortSignal,
): Promise<CustomerSegment> {
  const response = await apiClient.post('/customer-segment', req, { signal });
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

// ─────────────────────────────────────────────────────────
// ops (운영 메트릭) — 백엔드 미구현 시 404. B1 예진 구현 대기.
// 계약: frontend/src/types/tokenUsage.ts 주석 참조.
// ─────────────────────────────────────────────────────────

export async function getTokenUsage(params: {
  from?: string;
  to?: string;
}): Promise<TokenUsageResponse> {
  const response = await apiClient.get('/ops/token-usage', { params });
  return response.data;
}

export default apiClient;
