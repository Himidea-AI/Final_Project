import axios from 'axios';
import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import { runAnalyzeLlmPolling, runPredictPolling } from '../api/client';
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
  /** done/error 로 전환된 시점 (Date.now()). running 중에는 null. UI 의 elapsed 카운터 계산용. */
  finishedAt: number | null;
  /** 실측 진행률 0~1 — backend polling 에서 받은 값. running 중 단계적으로 climb, done 시 1.0. */
  progress: number;
  /** 현재 진행 중인 stage 라벨 (backend 전달, 예: "서교동 분석 완료 (1/4)"). */
  stage: string | null;
}

export interface AnalysisSlice {
  status: SliceStatus;
  data: AnalysisOutput | null;
  error: string | null;
  finishedAt: number | null;
  progress: number;
  stage: string | null;
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
  /** 매니저가 [저장] 버튼으로 저장한 이력 ID (SPTR-000142). null이면 DRAFT. R1: store = Single Source of Truth.
   *  legacy 단일 ID — 호환용. 신규 분기 코드는 savedForeseeId / savedAIId 사용.
   */
  savedHistoryId: number | null;
  /** ML 예측 (DashboardPredictPage) 저장 이력 ID. /simulation-foresee row. */
  savedForeseeId: number | null;
  /** AI 분석 (DashboardAnalyzePage) 저장 이력 ID. /simulation-ai row. */
  savedAIId: number | null;

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
  setSavedForeseeId: (id: number | null) => void;
  setSavedAIId: (id: number | null) => void;
  reset: () => void;
}

const initialPrediction: PredictionSlice = {
  status: 'idle',
  data: null,
  error: null,
  finishedAt: null,
  progress: 0,
  stage: null,
};
const initialAnalysis: AnalysisSlice = {
  status: 'idle',
  data: null,
  error: null,
  finishedAt: null,
  progress: 0,
  stage: null,
};

const INITIAL_STATE = {
  status: 'idle' as SimulationStatus,
  progress: 0,
  stage: '',
  result: null,
  error: null,
  params: null,
  startedAt: null,
  savedHistoryId: null,
  savedForeseeId: null,
  savedAIId: null,
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

// localStorage persist — F5/탭 닫기/직접 URL 진입(/dashboard/predict 북마크 등) 시도 result 복원.
//   2026-05-02: sessionStorage → localStorage 전환. /dashboard 직접 URL 진입 시 simulator 로
//   redirect 되던 UX 문제 해결 (DashboardOutlet null guard + sessionStorage 휘발 조합).
//   status='done' 일 때만 partialize 라 outdated 위험 낮음 — dismiss/새 시뮬로 자연 cleanup.
//   running/error 상태는 idle로 강제 복원 (in-memory timer/abortController 라 진행률 가짜 stuck 방지).
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
          // Real-progress 전환: 가짜 fake-progress timer 제거. 글로벌 progress 는
          // prediction/analysis slice progress 의 평균으로 derive (slice 갱신 시 함께 갱신).
          progress: 0,
          stage: 'INITIALIZING',
          result: null,
          error: null,
          params,
          startedAt,
          savedHistoryId: null, // 새 시뮬 시작 시 이전 저장 이력 ID 초기화 (Document ID = DRAFT)
          savedForeseeId: null,
          savedAIId: null,
          prediction: { ...initialPrediction, status: 'running' },
          analysis: { ...initialAnalysis, status: 'running' },
          _abortController: abortController,
          _progressTimer: null,
        });

        const isAbortError = (e: unknown): boolean => {
          const name = (e as { name?: string })?.name;
          return name === 'CanceledError' || name === 'AbortError' || axios.isCancel(e);
        };

        // 글로벌 progress = (prediction.progress + analysis.progress) / 2 — 양 슬라이스
        // 평균치. 단일 SimulationFloatingWidget 의 0~100 표시용 (legacy 호환).
        const recalcGlobal = () => {
          const { prediction, analysis } = get();
          const avg = (prediction.progress + analysis.progress) / 2;
          set({ progress: Math.round(avg * 100), stage: stageFor(avg * 100) });
        };

        // /predict polling — 동별 완료마다 backend progress 갱신, 250ms 폴링.
        const predictPromise = runPredictPolling(
          params,
          (ratio, stage) => {
            if (get().startedAt !== startedAt) return; // stale guard
            const cur = get().prediction;
            set({ prediction: { ...cur, progress: ratio, stage } });
            recalcGlobal();
          },
          abortController.signal,
        )
          .then((data) => {
            if (get().startedAt !== startedAt) return;
            set({
              prediction: {
                status: 'done',
                data,
                error: null,
                finishedAt: Date.now(),
                progress: 1,
                stage: 'done',
              },
            });
            recalcGlobal();
          })
          .catch((err) => {
            if (get().startedAt !== startedAt) return;
            if (isAbortError(err)) return;
            const msg = (err as { message?: string })?.message ?? '예측(/predict) 실패';
            const cur = get().prediction;
            set({
              prediction: {
                status: 'error',
                data: null,
                error: msg,
                finishedAt: Date.now(),
                progress: cur.progress,
                stage: cur.stage,
              },
            });
          });

        // /analyze/llm polling — LangGraph 노드 완료마다 progress (25%/50%/75%/100%).
        const analyzePromise = runAnalyzeLlmPolling(
          params,
          (ratio, stage) => {
            if (get().startedAt !== startedAt) return;
            const cur = get().analysis;
            set({ analysis: { ...cur, progress: ratio, stage } });
            recalcGlobal();
          },
          abortController.signal,
        )
          .then((data) => {
            if (get().startedAt !== startedAt) return;
            set({
              analysis: {
                status: 'done',
                data,
                error: null,
                finishedAt: Date.now(),
                progress: 1,
                stage: 'done',
              },
            });
            recalcGlobal();
          })
          .catch((err) => {
            if (get().startedAt !== startedAt) return;
            if (isAbortError(err)) return;
            const msg = (err as { message?: string })?.message ?? '분석(/analyze/llm) 실패';
            const cur = get().analysis;
            set({
              analysis: {
                status: 'error',
                data: null,
                error: msg,
                finishedAt: Date.now(),
                progress: cur.progress,
                stage: cur.stage,
              },
            });
          });

        // 양쪽 settle 후 글로벌 status 결정 — 하나라도 done 이면 done, 둘 다 error 면 error.
        await Promise.allSettled([predictPromise, analyzePromise]);
        if (get().startedAt !== startedAt) return;
        const { prediction: p, analysis: a } = get();
        const anyDone = p.status === 'done' || a.status === 'done';
        if (anyDone) {
          set({ status: 'done', progress: 100, stage: 'COMPLETE' });
        } else {
          set({ status: 'error', stage: '시뮬 실패', error: p.error || a.error });
        }
      },

      retryPrediction: async () => {
        const params = get().params;
        if (!params) return;
        set({ prediction: { ...initialPrediction, status: 'running' } });
        try {
          const data = await runPredictPolling(params, (ratio, stage) => {
            const cur = get().prediction;
            set({ prediction: { ...cur, progress: ratio, stage } });
          });
          set({
            prediction: {
              status: 'done',
              data,
              error: null,
              finishedAt: Date.now(),
              progress: 1,
              stage: 'done',
            },
          });
        } catch (e) {
          const msg = e instanceof Error ? e.message : '예측 재시도 실패';
          const cur = get().prediction;
          set({
            prediction: {
              status: 'error',
              data: null,
              error: msg,
              finishedAt: Date.now(),
              progress: cur.progress,
              stage: cur.stage,
            },
          });
        }
      },

      retryAnalysis: async () => {
        const params = get().params;
        if (!params) return;
        set({ analysis: { ...initialAnalysis, status: 'running' } });
        try {
          const data = await runAnalyzeLlmPolling(params, (ratio, stage) => {
            const cur = get().analysis;
            set({ analysis: { ...cur, progress: ratio, stage } });
          });
          set({
            analysis: {
              status: 'done',
              data,
              error: null,
              finishedAt: Date.now(),
              progress: 1,
              stage: 'done',
            },
          });
        } catch (e) {
          const msg = e instanceof Error ? e.message : '분석 재시도 실패';
          const cur = get().analysis;
          set({
            analysis: {
              status: 'error',
              data: null,
              error: msg,
              finishedAt: Date.now(),
              progress: cur.progress,
              stage: cur.stage,
            },
          });
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
          savedForeseeId: null,
          savedAIId: null,
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
          savedForeseeId: null,
          savedAIId: null,
          prediction: initialPrediction,
          analysis: initialAnalysis,
        });
      },
      setSavedHistoryId: (id) => set({ savedHistoryId: id }),
      setSavedForeseeId: (id) => set({ savedForeseeId: id }),
      setSavedAIId: (id) => set({ savedAIId: id }),
      reset: () => {
        const { _abortController, _progressTimer } = get();
        _abortController?.abort();
        if (_progressTimer) clearInterval(_progressTimer);
        set(INITIAL_STATE);
      },
    }),
    {
      name: 'mapo-simulation-store',
      storage: createJSONStorage(() => localStorage),
      // 'done' 상태에서 result/params/savedHistoryId만 직렬화. running/error는 idle로 강제.
      // _abortController, _progressTimer는 비-직렬화 (반환에서 자동 제외).
      partialize: (state) => ({
        status: state.status === 'done' ? ('done' as const) : ('idle' as const),
        result: state.status === 'done' ? state.result : null,
        params: state.status === 'done' ? state.params : null,
        savedHistoryId: state.status === 'done' ? state.savedHistoryId : null,
        savedForeseeId: state.status === 'done' ? state.savedForeseeId : null,
        savedAIId: state.status === 'done' ? state.savedAIId : null,
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
