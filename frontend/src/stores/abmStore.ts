/**
 * abmStore — ABM(Agent-Based Model) 행동 시뮬 전용 상태 store
 *
 * 패턴: simulationStore.ts 미러 + job_id 비동기 폴링.
 *
 * 배경:
 *   기존 App.tsx / AbmTab.tsx 의 fetch('/api/simulate-abm') 4곳이 모두
 *   useState 로컬(`abmLoading`/`abmError`/`abmResult`)이라 컴포넌트 unmount 시
 *   진행 중인 시뮬 결과가 사라졌다. AbortController 도 없어 새로고침/탭 이동 시
 *   백엔드는 계속 돌지만 프론트는 결과를 받지 못해 실패만 보였다.
 *
 * 해결:
 *   - zustand + persist(sessionStorage) — 새로고침 후 재진입 시 jobId 살아있으면
 *     polling 자동 재개.
 *   - AbortController — POST 60s, GET 10s 타임아웃 + cancelAbm 시 즉시 abort.
 *   - 백엔드 contract (병렬 작업 중인 backend agent):
 *       POST /api/simulate-abm  body.async_mode=true → { job_id, status:'running' }
 *         (캐시 hit 시 job_id 없이 동기 결과 즉시 반환 — backward compat)
 *       GET  /api/simulate-abm/{job_id}/status → { status, elapsed_seconds, progress?, error? }
 *       GET  /api/simulate-abm/{job_id}/result → 동기 응답 schema 그대로
 */

import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

export type AbmStatus = 'idle' | 'running' | 'done' | 'error';

/** 시뮬 ETA 운영 기준값 — progress fake update 의 기준 시간(초). */
const ABM_ETA_SECONDS = 180;

/** POST /api/simulate-abm 타임아웃 (job_id 즉시 반환되어야 함). */
const POST_TIMEOUT_MS = 60_000;

/** GET status/result 단건 타임아웃. */
const GET_TIMEOUT_MS = 10_000;

/** 폴링 주기. */
const POLL_INTERVAL_MS = 2_000;

export interface AbmRequestPayload {
  target_district: string;
  business_type: string | null | undefined;
  brand_name: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  langgraph_result: any;
  n_agents?: number;
  days?: number;
  spot_lat?: number;
  spot_lon?: number;
  scenario: {
    weather_override: string | null;
    date_override: string | null;
    weekend_force: boolean;
    rent_shock_pct: number;
  };
  enable_llm_thought?: boolean;
  enable_llm_decisions?: boolean;
  store_area?: number;
}

export interface AbmFocusSpot {
  lat: number;
  lon: number;
  label?: string;
}

/** 결과 history entry — 누적 시뮬 결과. AbmFloatingWidget 우선순위 표시 + history 패널용. */
export interface AbmHistoryEntry {
  id: string;
  savedAt: number;
  focusSpot: AbmFocusSpot | null;
  params: AbmRequestPayload | null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  result: any;
}

interface AbmState {
  status: AbmStatus;
  jobId: string | null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  result: any | null;
  error: string | null;
  params: AbmRequestPayload | null;
  focusSpot: AbmFocusSpot | null;
  progress: number;
  stage: string;
  startedAt: number | null;
  history: AbmHistoryEntry[];

  _abortController: AbortController | null;
  _pollTimer: ReturnType<typeof setInterval> | null;

  startAbm: (payload: AbmRequestPayload, focusSpot?: AbmFocusSpot | null) => Promise<void>;
  cancelAbm: () => void;
  dismissResult: () => void;
  setFocusSpot: (spot: AbmFocusSpot | null) => void;
  loadHistory: (id: string) => void;
  clearHistory: () => void;
  /** persist 복원 후 재진입 시 polling 재개. App mount 에서 호출. */
  resumePollingIfNeeded: () => void;
  reset: () => void;

  // 내부 액션 — 외부 호출 비권장 (test 용 export).
  _pollStatus: () => Promise<void>;
  _fetchResult: () => Promise<void>;
}

const INITIAL_STATE: Omit<
  AbmState,
  | 'startAbm'
  | 'cancelAbm'
  | 'dismissResult'
  | 'setFocusSpot'
  | 'loadHistory'
  | 'clearHistory'
  | 'resumePollingIfNeeded'
  | 'reset'
  | '_pollStatus'
  | '_fetchResult'
> = {
  status: 'idle',
  jobId: null,
  result: null,
  error: null,
  params: null,
  focusSpot: null,
  progress: 0,
  stage: '',
  startedAt: null,
  history: [],
  _abortController: null,
  _pollTimer: null,
};

const STAGES: readonly { at: number; text: string }[] = [
  { at: 0, text: 'INITIALIZING ABM ENGINE' },
  { at: 10, text: 'SPAWNING 5000 AGENTS' },
  { at: 25, text: 'COMPUTING DAILY ROUTINES' },
  { at: 45, text: 'TIER A/B DECISIONS' },
  { at: 60, text: 'TIER S LLM REASONING' },
  { at: 80, text: 'AGGREGATING VISITS / REVENUE' },
  { at: 90, text: 'FINALIZING' },
];

function stageFor(progress: number): string {
  let current = STAGES[0].text;
  for (const s of STAGES) {
    if (progress >= s.at) current = s.text;
  }
  return current;
}

/** fetch + AbortSignal + timeout 헬퍼. timeout 초과 시 abort + reject. */
async function fetchWithTimeout(
  url: string,
  init: RequestInit,
  timeoutMs: number,
  externalSignal?: AbortSignal,
): Promise<Response> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  // 외부 abort signal 가 abort 되면 함께 abort.
  const onExternalAbort = () => ctrl.abort();
  if (externalSignal) {
    if (externalSignal.aborted) ctrl.abort();
    else externalSignal.addEventListener('abort', onExternalAbort);
  }
  try {
    return await fetch(url, { ...init, signal: ctrl.signal });
  } finally {
    clearTimeout(timer);
    if (externalSignal) externalSignal.removeEventListener('abort', onExternalAbort);
  }
}

function isAbortError(e: unknown): boolean {
  const name = (e as { name?: string })?.name;
  return name === 'AbortError';
}

export const useAbmStore = create<AbmState>()(
  persist(
    (set, get) => ({
      ...INITIAL_STATE,

      startAbm: async (payload, focusSpot = null) => {
        // Replacement policy: 기존 in-flight 가 있으면 abort.
        const { _abortController: prevAbort, _pollTimer: prevTimer } = get();
        prevAbort?.abort();
        if (prevTimer) clearInterval(prevTimer);

        const abortController = new AbortController();
        const startedAt = Date.now();

        set({
          status: 'running',
          jobId: null,
          result: null,
          error: null,
          params: payload,
          focusSpot,
          progress: 0,
          stage: stageFor(0),
          startedAt,
          _abortController: abortController,
          _pollTimer: null,
        });

        let response: Response;
        try {
          response = await fetchWithTimeout(
            '/api/simulate-abm',
            {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ ...payload, async_mode: true }),
            },
            POST_TIMEOUT_MS,
            abortController.signal,
          );
        } catch (err) {
          // cancelAbm 으로 인한 abort 면 cancelAbm 이 이미 정리. 외부 timeout 만 error 로.
          if (isAbortError(err) && abortController.signal.aborted && get().status !== 'running') {
            return;
          }
          set({
            status: 'error',
            error: isAbortError(err)
              ? 'ABM 시뮬 요청 타임아웃 (60s 초과)'
              : `ABM 시뮬 요청 실패: ${(err as Error).message || '네트워크 오류'}`,
            _abortController: null,
          });
          return;
        }

        // Stale guard — startAbm 가 다시 호출됐다면 중단.
        if (get()._abortController !== abortController) return;

        let data: Record<string, unknown> & {
          job_id?: string;
          status?: string;
          message?: string;
        };
        try {
          data = await response.json();
        } catch {
          set({
            status: 'error',
            error: `ABM 응답 파싱 실패 (HTTP ${response.status})`,
            _abortController: null,
          });
          return;
        }

        if (!response.ok) {
          set({
            status: 'error',
            error: data?.message || `ABM 시뮬 실패 (HTTP ${response.status})`,
            _abortController: null,
          });
          return;
        }

        // backward compat: backend 가 동기로 결과를 즉시 반환 (캐시 hit, async_mode 미지원 등)
        if (!data.job_id) {
          if (data.status === 'unavailable') {
            set({
              status: 'error',
              error: 'ABM 모듈 준비 중입니다. (simulation 브랜치 머지 대기)',
              _abortController: null,
            });
            return;
          }
          if (data.status === 'error') {
            set({
              status: 'error',
              error: data?.message || 'ABM 시뮬레이션 실행 중 오류가 발생했습니다.',
              _abortController: null,
            });
            return;
          }
          // 동기 결과 — 바로 done.
          set({
            status: 'done',
            result: data,
            progress: 100,
            stage: 'COMPLETE',
            _abortController: null,
            _pollTimer: null,
          });
          return;
        }

        // 비동기 — jobId 저장 + 폴링 시작.
        set({ jobId: data.job_id });
        const timer = setInterval(() => {
          // setInterval 콜백에서 동일 store 인스턴스 액션 호출.
          void get()._pollStatus();
        }, POLL_INTERVAL_MS);
        set({ _pollTimer: timer });
        // 첫 즉시 1회.
        void get()._pollStatus();
      },

      _pollStatus: async () => {
        const { jobId, _abortController, startedAt } = get();
        if (!jobId || !_abortController) return;

        // progress fake — elapsed / ETA × 90 (capped at 90).
        if (startedAt) {
          const elapsed = (Date.now() - startedAt) / 1000;
          const fakeProgress = Math.min(90, (elapsed / ABM_ETA_SECONDS) * 90);
          set({ progress: fakeProgress, stage: stageFor(fakeProgress) });
        }

        let res: Response;
        try {
          res = await fetchWithTimeout(
            `/api/simulate-abm/${encodeURIComponent(jobId)}/status`,
            { method: 'GET' },
            GET_TIMEOUT_MS,
            _abortController.signal,
          );
        } catch (err) {
          if (isAbortError(err)) return; // cancelAbm 등 → 무시.
          // 일시적 네트워크 오류는 다음 poll tick 에서 재시도. error 로 전환하지 않음.
          return;
        }

        if (get()._abortController !== _abortController) return;

        if (!res.ok) {
          // 404/5xx — error 로 전환.
          const msg = `ABM status 조회 실패 (HTTP ${res.status})`;
          const { _pollTimer } = get();
          if (_pollTimer) clearInterval(_pollTimer);
          set({
            status: 'error',
            error: msg,
            _abortController: null,
            _pollTimer: null,
          });
          return;
        }

        let body: { status?: string; progress?: number; elapsed_seconds?: number; error?: string };
        try {
          body = await res.json();
        } catch {
          return;
        }

        // backend 가 progress 를 직접 주면 그 값 우선.
        if (typeof body.progress === 'number') {
          const p = Math.min(95, body.progress);
          set({ progress: p, stage: stageFor(p) });
        }

        if (body.status === 'done') {
          await get()._fetchResult();
        } else if (body.status === 'failed') {
          const { _pollTimer } = get();
          if (_pollTimer) clearInterval(_pollTimer);
          set({
            status: 'error',
            error: body.error || 'ABM 시뮬 실패 (backend reported)',
            _abortController: null,
            _pollTimer: null,
          });
        }
        // 'running' — 계속 poll.
      },

      _fetchResult: async () => {
        const { jobId, _abortController, _pollTimer } = get();
        if (!jobId || !_abortController) return;

        let res: Response;
        try {
          res = await fetchWithTimeout(
            `/api/simulate-abm/${encodeURIComponent(jobId)}/result`,
            { method: 'GET' },
            GET_TIMEOUT_MS,
            _abortController.signal,
          );
        } catch (err) {
          if (isAbortError(err)) return;
          // result fetch 실패 — 다음 poll tick 이 status=done 다시 보면 재시도.
          return;
        }

        if (get()._abortController !== _abortController) return;

        if (res.status === 409) {
          // 아직 running — status 가 잘못 보고. 다음 tick 에서 재시도.
          return;
        }

        if (!res.ok) {
          if (_pollTimer) clearInterval(_pollTimer);
          set({
            status: 'error',
            error: `ABM 결과 조회 실패 (HTTP ${res.status})`,
            _abortController: null,
            _pollTimer: null,
          });
          return;
        }

        let data: Record<string, unknown>;
        try {
          data = await res.json();
        } catch {
          if (_pollTimer) clearInterval(_pollTimer);
          set({
            status: 'error',
            error: 'ABM 결과 응답 파싱 실패',
            _abortController: null,
            _pollTimer: null,
          });
          return;
        }

        if (_pollTimer) clearInterval(_pollTimer);
        // history 에 push — 시뮬 결과 누적 (max 10).
        const { history, focusSpot, params } = get();
        const entry: AbmHistoryEntry = {
          id: `h_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
          savedAt: Date.now(),
          focusSpot,
          params,
          result: data,
        };
        const newHistory = [entry, ...history].slice(0, 10);
        set({
          status: 'done',
          result: data,
          progress: 100,
          stage: 'COMPLETE',
          history: newHistory,
          _abortController: null,
          _pollTimer: null,
        });
      },

      cancelAbm: () => {
        const { _abortController, _pollTimer, history } = get();
        _abortController?.abort();
        if (_pollTimer) clearInterval(_pollTimer);
        set({
          ...INITIAL_STATE,
          history, // history 유지
        });
      },

      dismissResult: () => {
        const { status, history } = get();
        if (status !== 'done' && status !== 'error') return;
        set({ ...INITIAL_STATE, history });
      },

      setFocusSpot: (spot) => set({ focusSpot: spot }),

      loadHistory: (id) => {
        const { history } = get();
        const entry = history.find((e) => e.id === id);
        if (!entry) return;
        set({
          status: 'done',
          result: entry.result,
          focusSpot: entry.focusSpot,
          params: entry.params,
          progress: 100,
          stage: 'COMPLETE',
          error: null,
        });
      },

      clearHistory: () => set({ history: [] }),

      resumePollingIfNeeded: () => {
        const { status, jobId, _pollTimer, _abortController } = get();
        // persist 가 status='running' + jobId 를 복원했고, in-memory 타이머가 없으면 재개.
        if (status !== 'running' || !jobId) return;
        if (_pollTimer || _abortController) return; // 이미 진행 중.

        const ctrl = new AbortController();
        // startedAt 이 persist 에서 살아있으면 그대로, 없으면 지금부터.
        const startedAt = get().startedAt ?? Date.now();
        set({ _abortController: ctrl, startedAt });

        const timer = setInterval(() => {
          void get()._pollStatus();
        }, POLL_INTERVAL_MS);
        set({ _pollTimer: timer });
        void get()._pollStatus();
      },

      reset: () => {
        const { _abortController, _pollTimer } = get();
        _abortController?.abort();
        if (_pollTimer) clearInterval(_pollTimer);
        set({ ...INITIAL_STATE });
      },
    }),
    {
      name: 'mapo-abm-store',
      storage: createJSONStorage(() => sessionStorage),
      // running 중 새로고침 시 jobId 보존 → resumePollingIfNeeded 로 재개.
      // done 상태 result 도 보존 (탭 이동/F5 후 결과 유지).
      // error 는 휘발 (재진입 시 idle 로).
      partialize: (state) => {
        if (state.status === 'running' && state.jobId) {
          return {
            status: 'running' as const,
            jobId: state.jobId,
            params: state.params,
            focusSpot: state.focusSpot,
            startedAt: state.startedAt,
            // result/progress/stage 는 polling 재개 시 재계산.
            result: null,
            error: null,
            progress: 0,
            stage: '',
          };
        }
        if (state.status === 'done') {
          return {
            status: 'done' as const,
            jobId: state.jobId,
            result: state.result,
            params: state.params,
            focusSpot: state.focusSpot,
            startedAt: state.startedAt,
            error: null,
            progress: 100,
            stage: 'COMPLETE',
          };
        }
        return {
          status: 'idle' as const,
          jobId: null,
          result: null,
          params: null,
          focusSpot: null,
          startedAt: null,
          error: null,
          progress: 0,
          stage: '',
        };
      },
    },
  ),
);
