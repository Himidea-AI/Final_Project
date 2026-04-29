import axios from 'axios';
import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import { fetchAnalyzeLlm, fetchPredict } from '../api/client';
import type {
  AnalysisOutput,
  DistrictPredictionResult,
  SimulationInput,
  SimulationOutput,
} from '../types';

export type SimulationStatus = 'idle' | 'running' | 'done' | 'error';

/** 슬라이스(예측/분석)별 상태 — startSimulation 의 Promise.allSettled 부분 성공 표현용. */
export type SliceStatus = 'idle' | 'running' | 'done' | 'error';

export interface PredictionSlice {
  status: SliceStatus;
  data: DistrictPredictionResult[] | null;
  error: string | null;
}

export interface AnalysisSlice {
  status: SliceStatus;
  data: AnalysisOutput | null;
  error: string | null;
}

interface SimulationState {
  status: SimulationStatus;
  progress: number;
  stage: string;
  /** @deprecated useCombinedSimResult() hook 으로 prediction + analysis 합성. legacy /simulate 응답 또는 history 복원 경로용. */
  result: SimulationOutput | null;
  error: string | null;
  params: SimulationInput | null;
  startedAt: number | null;
  /** 매니저가 [저장] 버튼으로 저장한 이력 ID (SPTR-000142). null이면 DRAFT. R1: store = Single Source of Truth. */
  savedHistoryId: number | null;

  /** /predict 응답 슬라이스 (IM3-259 분리 호출). */
  prediction: PredictionSlice;
  /** /analyze/llm 응답 슬라이스 (IM3-259 분리 호출). */
  analysis: AnalysisSlice;

  _abortController: AbortController | null;
  _progressTimer: ReturnType<typeof setInterval> | null;

  startSimulation: (params: SimulationInput) => Promise<void>;
  retryPrediction: () => Promise<void>;
  retryAnalysis: () => Promise<void>;
  cancelSimulation: () => void;
  dismissResult: () => void;
  setSavedHistoryId: (id: number | null) => void;
  reset: () => void;
}

const initialPrediction: PredictionSlice = { status: 'idle', data: null, error: null };
const initialAnalysis: AnalysisSlice = { status: 'idle', data: null, error: null };

const INITIAL_STATE = {
  status: 'idle' as SimulationStatus,
  progress: 0,
  stage: '',
  result: null,
  error: null,
  params: null,
  startedAt: null,
  savedHistoryId: null,
  prediction: initialPrediction,
  analysis: initialAnalysis,
  _abortController: null,
  _progressTimer: null,
};

// Monotonic timestamp generator — guarantees uniqueness even when
// startSimulation is invoked twice within the same millisecond.
// Used as the stale-response guard key; see the two `startedAt !== get().startedAt`
// checks inside startSimulation.
let _lastStartedAt = 0;
function nextStartedAt(): number {
  const now = Date.now();
  _lastStartedAt = now > _lastStartedAt ? now : _lastStartedAt + 1;
  return _lastStartedAt;
}

// Stage text shown next to the progress bar. Each entry's `at` is the
// progress % threshold at which the stage label becomes active.
const STAGES: readonly { at: number; text: string }[] = [
  { at: 0, text: 'INITIALIZING AI ENGINE' },
  { at: 5, text: 'CONNECTING TO DATABASE' },
  { at: 10, text: 'FETCHING KT TELECOM DATA' },
  { at: 20, text: 'ANALYZING COMPETITION DENSITY' },
  { at: 30, text: 'QUERYING POPULATION TRENDS' },
  { at: 40, text: 'CALCULATING RENT-TO-REVENUE RATIO' },
  { at: 50, text: 'ANALYZING CANNIBALIZATION RATE' },
  { at: 60, text: 'CROSS-CHECKING LEGAL RISKS' },
  { at: 70, text: 'RUNNING WHAT-IF SCENARIOS' },
  { at: 80, text: 'GENERATING 12-MONTH FORECAST' },
  { at: 88, text: 'SYNTHESIZING MULTI-AGENT RESULTS' },
];

function stageFor(progress: number): string {
  let current = STAGES[0].text;
  for (const s of STAGES) {
    if (progress >= s.at) current = s.text;
  }
  return current;
}

// sessionStorage persist — F5 새로고침 시 result 복원, 탭 닫으면 자연 휘발(DRAFT 의도 유지).
// status='running'/'error' 상태는 idle로 강제 복원 — 진행 중이던 timer/abortController는
// in-memory 전용이라 복원 시 가짜 진행률에 멈춤. result만 살아있는 'done' 케이스만 복원 의미가 있다.
export const useSimulationStore = create<SimulationState>()(
  persist(
    (set, get) => ({
      ...INITIAL_STATE,

      startSimulation: async (params) => {
        // Replacement policy: if running, cancel first.
        const { _abortController: prevAbort, _progressTimer: prevTimer } = get();
        prevAbort?.abort();
        if (prevTimer) clearInterval(prevTimer);

        const abortController = new AbortController();
        const startedAt = nextStartedAt();

        set({
          status: 'running',
          progress: 0,
          stage: 'INITIALIZING AI ENGINE',
          result: null,
          error: null,
          params,
          startedAt,
          savedHistoryId: null, // 새 시뮬 시작 시 이전 저장 이력 ID 초기화 (Document ID = DRAFT)
          prediction: { status: 'running', data: null, error: null },
          analysis: { status: 'running', data: null, error: null },
          _abortController: abortController,
          _progressTimer: null,
        });

        // Fake-progress ticker: climbs to 90% over ~100s so the user feels motion
        // while the real request is in flight. Capped at 90 so the jump to 100
        // on success remains perceptible.
        const timer = setInterval(() => {
          const elapsed = (Date.now() - startedAt) / 1000;
          const p = Math.min(90, elapsed * 0.9);
          set({ progress: p, stage: stageFor(p) });
        }, 500);
        set({ _progressTimer: timer });

        // Promise.allSettled — /predict 와 /analyze/llm 부분 성공 허용.
        // 한쪽 실패해도 다른 쪽 결과를 그대로 노출 → 사용자는 retry* 액션으로 슬라이스 재시도 가능.
        const [predResult, analysisResult] = await Promise.allSettled([
          fetchPredict(params),
          fetchAnalyzeLlm(params),
        ]);

        // Stale response guard — 더 새로운 startSimulation 호출이 우리를 교체했다면 작업 중단.
        if (get().startedAt !== startedAt) return;

        // Abort 도 취소된 상태라면 cancelSimulation 이 이미 정리했으므로 손대지 않음.
        const isAbortError = (e: unknown): boolean => {
          const name = (e as { name?: string })?.name;
          return name === 'CanceledError' || name === 'AbortError' || axios.isCancel(e);
        };
        const predAborted = predResult.status === 'rejected' && isAbortError(predResult.reason);
        const analysisAborted =
          analysisResult.status === 'rejected' && isAbortError(analysisResult.reason);
        if (predAborted && analysisAborted) {
          // 양쪽 모두 abort → cancelSimulation 이 처리. 여기서 더 set 안 함.
          return;
        }

        const predSlice: PredictionSlice =
          predResult.status === 'fulfilled'
            ? { status: 'done', data: predResult.value, error: null }
            : {
                status: 'error',
                data: null,
                error:
                  (predResult.reason as { message?: string })?.message ?? '예측(/predict) 실패',
              };

        const analysisSlice: AnalysisSlice =
          analysisResult.status === 'fulfilled'
            ? { status: 'done', data: analysisResult.value, error: null }
            : {
                status: 'error',
                data: null,
                error:
                  (analysisResult.reason as { message?: string })?.message ??
                  '분석(/analyze/llm) 실패',
              };

        const allFailed = predSlice.status === 'error' && analysisSlice.status === 'error';

        const { _progressTimer } = get();
        if (_progressTimer) clearInterval(_progressTimer);

        set({
          prediction: predSlice,
          analysis: analysisSlice,
          status: allFailed ? 'error' : 'done',
          progress: 100,
          stage: allFailed ? '시뮬 실패' : 'COMPLETE',
          error: allFailed
            ? `예측/분석 모두 실패: ${predSlice.error} | ${analysisSlice.error}`
            : null,
          _abortController: null,
          _progressTimer: null,
        });
      },

      retryPrediction: async () => {
        const params = get().params;
        if (!params) return;
        set({ prediction: { status: 'running', data: null, error: null } });
        try {
          const data = await fetchPredict(params);
          set({ prediction: { status: 'done', data, error: null } });
        } catch (e) {
          const msg = e instanceof Error ? e.message : '예측 재시도 실패';
          set({ prediction: { status: 'error', data: null, error: msg } });
        }
      },

      retryAnalysis: async () => {
        const params = get().params;
        if (!params) return;
        set({ analysis: { status: 'running', data: null, error: null } });
        try {
          const data = await fetchAnalyzeLlm(params);
          set({ analysis: { status: 'done', data, error: null } });
        } catch (e) {
          const msg = e instanceof Error ? e.message : '분석 재시도 실패';
          set({ analysis: { status: 'error', data: null, error: msg } });
        }
      },

      cancelSimulation: () => {
        const { status, _abortController, _progressTimer } = get();
        if (status !== 'running') return;
        _abortController?.abort();
        if (_progressTimer) clearInterval(_progressTimer);
        set({
          status: 'idle',
          progress: 0,
          stage: '',
          result: null,
          error: null,
          params: null,
          startedAt: null,
          savedHistoryId: null,
          prediction: initialPrediction,
          analysis: initialAnalysis,
          _abortController: null,
          _progressTimer: null,
        });
      },
      dismissResult: () => {
        const { status } = get();
        if (status !== 'done' && status !== 'error') return;
        set({
          status: 'idle',
          progress: 0,
          stage: '',
          result: null,
          error: null,
          params: null,
          startedAt: null,
          savedHistoryId: null,
          prediction: initialPrediction,
          analysis: initialAnalysis,
        });
      },
      setSavedHistoryId: (id) => set({ savedHistoryId: id }),
      reset: () => {
        const { _abortController, _progressTimer } = get();
        _abortController?.abort();
        if (_progressTimer) clearInterval(_progressTimer);
        set(INITIAL_STATE);
      },
    }),
    {
      name: 'mapo-simulation-store',
      storage: createJSONStorage(() => sessionStorage),
      // 'done' 상태에서 result/params/savedHistoryId만 직렬화. running/error는 idle로 강제.
      // _abortController, _progressTimer는 비-직렬화 (반환에서 자동 제외).
      partialize: (state) => ({
        status: state.status === 'done' ? ('done' as const) : ('idle' as const),
        result: state.status === 'done' ? state.result : null,
        params: state.status === 'done' ? state.params : null,
        savedHistoryId: state.status === 'done' ? state.savedHistoryId : null,
        startedAt: state.status === 'done' ? state.startedAt : null,
        stage: state.status === 'done' ? state.stage : '',
        progress: state.status === 'done' ? 100 : 0,
        error: null,
        prediction: state.status === 'done' ? state.prediction : initialPrediction,
        analysis: state.status === 'done' ? state.analysis : initialAnalysis,
      }),
    },
  ),
);
