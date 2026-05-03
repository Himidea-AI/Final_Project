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
  DistrictPredictionResult,
  AnalysisOutput,
} from '../types';
import type {
  HistoryFilterParams,
  HistoryListResponse,
  SaveAIPayload,
  SaveForeseePayload,
  SaveSimulationPayload,
  SaveSimulationResponse,
  SimulationHistoryDetail,
  SimulationHistoryItem,
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
 * timeout 300_000 — /analyze/llm 동시 호출 시 cold start + SGIS sleep 누적으로
 * 실측 120s+ 발생 → 5분 buffer (근본 해결: SGIS 토큰 싱글톤 + uvicorn worker 2개).
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
 * timeout 600_000 — LLM 멀티에이전트 파이프라인 (~80~140s 실측, retry 여유 포함, 명세 일치).
 *
 * 응답 wrapper: backend (찬영 8223bfb contract 보강) 가 `{ status, data: AnalysisOutput }` 형태 반환.
 *   - LLM_AGENTS_DISABLED=1 mock 도 동일 wrapper.
 *   - error 시 `{ status: "error", message }`.
 */
export async function runAnalyzeLlm(
  input: SimulationInput,
  signal?: AbortSignal,
): Promise<AnalysisOutput> {
  const response = await apiClient.post('/analyze/llm', input, { signal, timeout: 600_000 });
  const body = response.data;
  if (body && body.status === 'success' && body.data) return body.data as AnalysisOutput;
  if (body && body.status === 'error') throw new Error(body.message || 'Analyze LLM failed');
  return body as AnalysisOutput; // legacy raw fallback
}

/**
 * Real-time progress 폴링 — /predict/async + /predict/{job_id}/status.
 * onProgress(ratio: 0~1) 가 매 250ms 마다 호출됨. 완료 시 final data resolve.
 *
 * 백엔드가 동별 _predict_single_district 완료마다 progress 갱신 → 4동 시 25%/50%/75%/100%.
 * 가짜 시간 추정 없음 — 실측 슬라이스 완료 비율 그대로.
 */
export async function runPredictPolling(
  input: SimulationInput,
  onProgress: (ratio: number, stage: string | null) => void,
  signal?: AbortSignal,
): Promise<DistrictPredictionResult[]> {
  const startResp = await apiClient.post('/predict/async', input, { signal, timeout: 30_000 });
  const jobId = startResp.data?.job_id;
  if (!jobId) throw new Error(startResp.data?.message || 'Predict async start failed');

  return pollJobUntilDone<DistrictPredictionResult[]>(
    `/predict/${jobId}/status`,
    onProgress,
    signal,
  );
}

/**
 * Real-time progress 폴링 — /analyze/llm/async + /analyze/llm/{job_id}/status.
 * 백엔드가 LangGraph 4 노드 완료마다 progress 갱신 → 25%/50%/75%/100%.
 */
export async function runAnalyzeLlmPolling(
  input: SimulationInput,
  onProgress: (ratio: number, stage: string | null) => void,
  signal?: AbortSignal,
): Promise<AnalysisOutput> {
  const startResp = await apiClient.post('/analyze/llm/async', input, { signal, timeout: 30_000 });
  const jobId = startResp.data?.job_id;
  if (!jobId) throw new Error(startResp.data?.message || 'Analyze async start failed');

  return pollJobUntilDone<AnalysisOutput>(`/analyze/llm/${jobId}/status`, onProgress, signal);
}

/**
 * 공통 polling 루프 — 250ms 간격으로 status endpoint 조회.
 * status='done' → data resolve, 'error' → reject, 'running' → onProgress 호출 후 계속.
 * AbortSignal 가 abort 되면 polling 중단 + reject (axios cancellation 과 동일 시맨틱).
 */
async function pollJobUntilDone<T>(
  statusUrl: string,
  onProgress: (ratio: number, stage: string | null) => void,
  signal?: AbortSignal,
): Promise<T> {
  const POLL_MS = 250;
  // 600초 (10분) 안전 cap — 백엔드 timeout 보다 길어 무한 hang 방지.
  const MAX_POLLS = (600 * 1000) / POLL_MS;

  for (let i = 0; i < MAX_POLLS; i++) {
    if (signal?.aborted) {
      const e = new Error('aborted');
      e.name = 'AbortError';
      throw e;
    }
    let resp;
    try {
      resp = await apiClient.get(statusUrl, { signal, timeout: 10_000 });
    } catch (err) {
      // 일시적 네트워크 오류는 재시도. 단 abort 는 즉시 propagate.
      if (signal?.aborted) throw err;
      await new Promise((r) => setTimeout(r, POLL_MS));
      continue;
    }
    const body = resp.data;
    const ratio = typeof body?.progress === 'number' ? body.progress : 0;
    const stage = typeof body?.stage === 'string' ? body.stage : null;
    onProgress(ratio, stage);

    if (body?.status === 'done') return body.data as T;
    if (body?.status === 'error') throw new Error(body.error || 'Job failed');

    await new Promise((r) => setTimeout(r, POLL_MS));
  }
  throw new Error('Polling timeout — job 이 600초 안에 완료되지 않음');
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
  // legacy row → kind 'ai' 기본 (legacy simulation_history 가 통합이므로 두 슬라이스 다 들어있음).
  const data = response.data ?? { items: [], total: 0, page: 1, size: 20 };
  if (Array.isArray(data.items)) {
    data.items = data.items.map((it: Record<string, unknown>) => ({
      ...it,
      kind: it.kind ?? 'ai',
    }));
  }
  return data as HistoryListResponse;
}

export async function getSimulationHistoryDetail(id: number): Promise<SimulationHistoryDetail> {
  const response = await apiClient.get(`/simulation-history/${id}`);
  // legacy row 는 kind 컬럼이 없음 — 'ai' 기본값 (legacy simulation_history 가 통합 result 였으나
  // 대시보드 hub 진입 시 기존 3-card 그대로 — kind 분기는 신규 라우트만 적용).
  // SimulationHistoryDetail 의 kind 필수성을 만족시키기 위해 주입.
  const data = response.data ?? {};
  if (!data.kind) data.kind = 'ai';
  return data as SimulationHistoryDetail;
}

export async function deleteSimulationHistory(id: number): Promise<void> {
  await apiClient.delete(`/simulation-history/${id}`);
}

// ─────────────────────────────────────────────────────────
// 신규 분리 endpoint (2026-05-02) — /simulation-foresee + /simulation-ai
// ML 예측과 LLM 분석을 별개 row 로 저장. 통합 list 는 useSimulationHistory 가 양쪽 머지.
// ─────────────────────────────────────────────────────────

/** POST /simulation-foresee — ML 예측 슬라이스 저장 */
export async function saveForeseeHistory(
  payload: SaveForeseePayload,
): Promise<SaveSimulationResponse> {
  const response = await apiClient.post('/simulation-foresee', payload);
  return response.data;
}

/** POST /simulation-ai — LLM 분석 슬라이스 저장 */
export async function saveAIHistory(payload: SaveAIPayload): Promise<SaveSimulationResponse> {
  const response = await apiClient.post('/simulation-ai', payload);
  return response.data;
}

/** GET /simulation-foresee — 예측 이력 목록 */
export async function listForeseeHistory(
  filter: HistoryFilterParams = {},
): Promise<HistoryListResponse> {
  const response = await apiClient.get('/simulation-foresee', { params: filter });
  return response.data;
}

/** GET /simulation-ai — AI 분석 이력 목록 */
export async function listAIHistory(
  filter: HistoryFilterParams = {},
): Promise<HistoryListResponse> {
  const response = await apiClient.get('/simulation-ai', { params: filter });
  return response.data;
}

/**
 * GET /simulation-foresee/{id} — 예측 row 상세.
 * Raw row(컬럼 그대로) 를 SimulationHistoryDetail (SimulationOutput 컨테이너) 로 매핑.
 * SimulationOutput 의 LLM 슬라이스 필드는 null/undefined 채움 (HistoryDashboardView kind='foresee' 분기에서 미사용).
 */
export async function getForeseeDetail(id: number): Promise<SimulationHistoryDetail> {
  const response = await apiClient.get(`/simulation-foresee/${id}`);
  return mapForeseeDetailToHistoryDetail(response.data);
}

/** GET /simulation-ai/{id} — AI 분석 row 상세 */
export async function getAIDetail(id: number): Promise<SimulationHistoryDetail> {
  const response = await apiClient.get(`/simulation-ai/${id}`);
  return mapAIDetailToHistoryDetail(response.data);
}

/** DELETE /simulation-foresee/{id} */
export async function deleteForeseeHistory(id: number): Promise<void> {
  await apiClient.delete(`/simulation-foresee/${id}`);
}

/** DELETE /simulation-ai/{id} */
export async function deleteAIHistory(id: number): Promise<void> {
  await apiClient.delete(`/simulation-ai/${id}`);
}

/**
 * Raw simulation_foresee row → SimulationHistoryDetail (SimulationOutput 컨테이너).
 * Backend 컬럼 분산 (district_predictions, quarterly_projection, ...) 을 SimulationOutput 형태로 합성.
 * 빠진 LLM 슬라이스 필드는 undefined/null 로 채움.
 */
export function mapForeseeDetailToHistoryDetail(row: Record<string, any>): SimulationHistoryDetail {
  const districts: string[] = Array.isArray(row.districts)
    ? row.districts
    : row.target_district
      ? [row.target_district]
      : [];
  const simulationResult: SimulationOutput = {
    request_id: String(row.id ?? ''),
    target_district: row.target_district ?? row.winner_district ?? districts[0] ?? '',
    target_districts: districts,
    analysis_report: '',
    analysis_metrics: {
      district_grade: 'NORMAL',
      growth_rate: 0,
      competition_score: 0,
      rent_affordability: '',
    },
    quarterly_projection: row.quarterly_projection ?? [],
    comparison: [],
    legal_risks: [],
    winner_district: row.winner_district ?? undefined,
    market_report: row.market_report ?? undefined,
    shap_result: row.shap_result ?? null,
    scenarios: row.scenarios ?? null,
    closure_rate: row.closure_rate ?? null,
    closure_risk: row.closure_risk ?? null,
    customer_segment: row.customer_segment ?? null,
    living_pop_forecast: row.living_pop_forecast ?? null,
    final_report: row.final_report ?? null,
    district_predictions: row.district_predictions ?? undefined,
    bep_months: row.bep_months ?? null,
    predicted_monthly_revenue: row.predicted_monthly_revenue ?? null,
  };
  return {
    id: Number(row.id),
    manager_id: String(row.manager_id ?? ''),
    manager_name: row.manager_name ?? null,
    client_name: row.client_name ?? '',
    district: row.target_district ?? row.winner_district ?? districts[0] ?? '',
    brand_name: row.brand_name ?? '',
    business_type: row.business_type ?? null,
    ai_verdict_summary: null,
    market_entry_signal: null,
    created_at: row.created_at ?? '',
    updated_at: row.updated_at ?? null,
    kind: 'foresee',
    scenario: row.scenario ?? null,
    simulation_result: simulationResult,
  };
}

/**
 * Raw simulation_ai row → SimulationHistoryDetail.
 * 빠진 ML 슬라이스(quarterly_projection 등) 는 빈 배열/null 로 채움.
 */
export function mapAIDetailToHistoryDetail(row: Record<string, any>): SimulationHistoryDetail {
  const simulationResult: SimulationOutput = {
    request_id: String(row.id ?? ''),
    target_district: row.target_district ?? row.winner_district ?? '',
    target_districts: row.target_district ? [row.target_district] : [],
    analysis_report: row.analysis_report ?? '',
    analysis_metrics: {
      district_grade: 'NORMAL',
      growth_rate: 0,
      competition_score: 0,
      rent_affordability: '',
    },
    quarterly_projection: [],
    comparison: [],
    legal_risks: row.legal_risks ?? [],
    ai_recommendation: row.ai_recommendation ?? undefined,
    winner_district: row.winner_district ?? undefined,
    top_3_candidates: row.top_3_candidates ?? undefined,
    district_rankings: row.district_rankings ?? undefined,
    overall_legal_risk: row.overall_legal_risk ?? undefined,
    vacancy_applied: row.vacancy_applied ?? undefined,
    market_report: row.market_report ?? undefined,
    trend_forecast: row.trend_forecast ?? null,
    competitor_intel: row.competitor_intel ?? null,
    demographic_report: row.demographic_report ?? null,
    agent_attributions: row.agent_attributions ?? undefined,
    all_competitor_locations: row.all_competitor_locations ?? undefined,
  };
  return {
    id: Number(row.id),
    manager_id: String(row.manager_id ?? ''),
    manager_name: row.manager_name ?? null,
    client_name: row.client_name ?? '',
    district: row.target_district ?? row.winner_district ?? '',
    brand_name: row.brand_name ?? '',
    business_type: row.business_type ?? null,
    ai_verdict_summary: row.ai_verdict_summary ?? null,
    market_entry_signal: (row.market_entry_signal as 'green' | 'yellow' | 'red' | null) ?? null,
    created_at: row.created_at ?? '',
    updated_at: row.updated_at ?? null,
    kind: 'ai',
    scenario: row.scenario ?? null,
    simulation_result: simulationResult,
  };
}

/**
 * List 응답 row → SimulationHistoryItem (kind 주입).
 * Backend list_foresee/list_ai 는 row 컬럼 일부만 select → 누락 필드는 빈 값/null 로.
 */
export function mapForeseeListItem(row: Record<string, any>): SimulationHistoryItem {
  return {
    id: Number(row.id),
    manager_id: String(row.manager_id ?? ''),
    manager_name: row.manager_name ?? null,
    client_name: row.client_name ?? '',
    district: row.target_district ?? row.winner_district ?? '',
    brand_name: row.brand_name ?? '',
    business_type: row.business_type ?? null,
    ai_verdict_summary: null, // foresee row 엔 LLM verdict 컬럼 없음
    market_entry_signal: null,
    created_at: row.created_at ?? '',
    kind: 'foresee',
  };
}

export function mapAIListItem(row: Record<string, any>): SimulationHistoryItem {
  return {
    id: Number(row.id),
    manager_id: String(row.manager_id ?? ''),
    manager_name: row.manager_name ?? null,
    client_name: row.client_name ?? '',
    district: row.target_district ?? row.winner_district ?? '',
    brand_name: row.brand_name ?? '',
    business_type: row.business_type ?? null,
    ai_verdict_summary: row.ai_verdict_summary ?? null,
    market_entry_signal: (row.market_entry_signal as 'green' | 'yellow' | 'red' | null) ?? null,
    created_at: row.created_at ?? '',
    kind: 'ai',
  };
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
