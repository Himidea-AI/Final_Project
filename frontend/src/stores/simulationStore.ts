import { create } from 'zustand';
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

export const useSimulationStore = create<SimulationState>((set, get) => ({
  ...INITIAL_STATE,

  startSimulation: async (params) => {
    const abortController = new AbortController();
    const startedAt = Date.now();

    set({
      status: 'running',
      progress: 0,
      stage: 'INITIALIZING AI ENGINE',
      result: null,
      error: null,
      params,
      startedAt,
      _abortController: abortController,
    });

    try {
      const { runSimulation } = await import('../api/client');
      const result = await runSimulation(params, abortController.signal);

      // Stale response guard — if a newer start has replaced us, abandon.
      if (get().startedAt !== startedAt) return;

      set({
        status: 'done',
        progress: 100,
        stage: 'COMPLETE',
        result,
        _abortController: null,
      });
    } catch (err: unknown) {
      // Error handling added in Plan Task 5
      throw err;
    }
  },
  cancelSimulation: () => {
    // Implemented in Plan Task 6
  },
  dismissResult: () => {
    // Implemented in Plan Task 9
  },
  reset: () => {
    const { _abortController, _progressTimer } = get();
    _abortController?.abort();
    if (_progressTimer) clearInterval(_progressTimer);
    set(INITIAL_STATE);
  },
}));
