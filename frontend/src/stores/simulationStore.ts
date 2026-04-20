import axios from 'axios';
import { create } from 'zustand';
import { runSimulation } from '../api/client';
import type { SimulationInput, SimulationOutput } from '../types';

export type SimulationStatus = 'idle' | 'running' | 'done' | 'error';

interface SimulationState {
  status: SimulationStatus;
  progress: number;
  stage: string;
  result: SimulationOutput | null;
  error: string | null;
  params: SimulationInput | null;
  startedAt: number | null;

  _abortController: AbortController | null;
  _progressTimer: ReturnType<typeof setInterval> | null;

  startSimulation: (params: SimulationInput) => Promise<void>;
  cancelSimulation: () => void;
  dismissResult: () => void;
  reset: () => void;
}

const INITIAL_STATE = {
  status: 'idle' as SimulationStatus,
  progress: 0,
  stage: '',
  result: null,
  error: null,
  params: null,
  startedAt: null,
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

export const useSimulationStore = create<SimulationState>((set, get) => ({
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

    try {
      const result = await runSimulation(params, abortController.signal);

      // Stale response guard — if a newer start has replaced us, abandon.
      if (get().startedAt !== startedAt) return;

      const { _progressTimer } = get();
      if (_progressTimer) clearInterval(_progressTimer);

      set({
        status: 'done',
        progress: 100,
        stage: 'COMPLETE',
        result,
        _abortController: null,
        _progressTimer: null,
      });
    } catch (err: unknown) {
      // Stale check — if replaced, don't touch state
      if (get().startedAt !== startedAt) return;

      const isAbort =
        (err as { name?: string })?.name === 'CanceledError' ||
        (err as { name?: string })?.name === 'AbortError' ||
        axios.isCancel?.(err);

      if (isAbort) {
        // cancelSimulation already cleaned state; nothing to do here
        return;
      }

      const { _progressTimer } = get();
      if (_progressTimer) clearInterval(_progressTimer);

      const message =
        err instanceof Error ? err.message : typeof err === 'string' ? err : '알 수 없는 오류';
      set({
        status: 'error',
        error: message,
        _abortController: null,
        _progressTimer: null,
      });
    }
  },
  cancelSimulation: () => {
    const { _abortController, _progressTimer } = get();
    _abortController?.abort();
    if (_progressTimer) clearInterval(_progressTimer);
    set({
      status: 'idle',
      progress: 0,
      stage: '',
      _abortController: null,
      _progressTimer: null,
      startedAt: null,
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
    });
  },
  reset: () => {
    const { _abortController, _progressTimer } = get();
    _abortController?.abort();
    if (_progressTimer) clearInterval(_progressTimer);
    set(INITIAL_STATE);
  },
}));
