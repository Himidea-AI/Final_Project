import axios from 'axios';
import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import { runAnalyzeLlm, runPredict } from '../api/client';
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
  /** @deprecated useCombinedSimResult() hook 으로 prediction + analysis 합성. history 복원 경로용 (legacy 단일 SimulationOutput 호환). */
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

        const isAbortError = (e: unknown): boolean => {
          const name = (e as { name?: string })?.name;
          return name === 'CanceledError' || name === 'AbortError' || axios.isCancel(e);
        };

        // /analyze/llm — 백그라운드 실행. /predict 완료 후 대시보드 진입, 분석 완료 시 자동 갱신.
        runAnalyzeLlm(params, abortController.signal)
          .then((data) => {
            if (get().startedAt !== startedAt) return;
            const { _progressTimer: t } = get();
            if (t) clearInterval(t);
            set({
              analysis: { status: 'done', data, error: null },
              status: 'done',
              progress: 100,
              stage: 'COMPLETE',
              _progressTimer: null,
            });
          })
          .catch((err) => {
            if (get().startedAt !== startedAt) return;
            if (isAbortError(err)) return;
            const { _progressTimer: t } = get();
            if (t) clearInterval(t);
            const msg = (err as { message?: string })?.message ?? '분석(/analyze/llm) 실패';
            // prediction 이 이미 done 이면 status 도 done 유지 (부분 성공).
            const predDone = get().prediction.status === 'done';
            set({
              analysis: { status: 'error', data: null, error: msg },
              ...(predDone
                ? { status: 'done', progress: 100, stage: 'COMPLETE' }
                : { status: 'error', stage: '시뮬 실패', error: msg }),
              _progressTimer: null,
            });
          });

        // /predict — await 후 즉시 prediction 슬라이스 확정 → App.tsx 게이트 통과 → 대시보드 진입 (≈15s).
        // analyze 는 백그라운드에서 계속 실행 중이므로 status 는 아직 'running' 유지.
        // (analyze .then()/.catch() 에서 'done'/'error' 로 전환 + 타이머 정리)
        try {
          const data = await runPredict(params, abortController.signal);
          if (get().startedAt !== startedAt) return; // stale guard
          set({ prediction: { status: 'done', data, error: null } });
        } catch (err) {
          if (get().startedAt !== startedAt) return;
          if (isAbortError(err)) return;
          const msg = (err as { message?: string })?.message ?? '예측(/predict) 실패';
          set({ prediction: { status: 'error', data: null, error: msg } });
        }
      },

      retryPrediction: async () => {
        const params = get().params;
        if (!params) return;
        set({ prediction: { status: 'running', data: null, error: null } });
        try {
          const data = await runPredict(params);
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
          const data = await runAnalyzeLlm(params);
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
