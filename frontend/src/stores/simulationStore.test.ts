import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import axios from 'axios';
import { useSimulationStore } from './simulationStore';
import * as api from '../api/client';
import type { SimulationInput, SimulationOutput } from '../types';

const MOCK_INPUT: SimulationInput = {
  business_type: 'cafe',
  brand_name: 'Test',
  target_district: '서교동',
  existing_stores: [],
  initial_investment: 0,
  monthly_rent: 1000000,
  simulation_months: 12,
  scenarios: [],
};

const MOCK_OUTPUT = {
  request_id: 'r1',
  target_district: '서교동',
  analysis_report: 'ok',
  analysis_metrics: {
    district_grade: 'NORMAL',
    growth_rate: 0,
    competition_score: 0,
    rent_affordability: 'SAFE',
  },
  simulation_months: 12,
  quarterly_projection: [],
  comparison: [],
  legal_risks: [],
} as unknown as SimulationOutput;

describe('simulationStore — 초기 상태', () => {
  beforeEach(() => {
    useSimulationStore.getState().reset();
  });

  it('초기에는 idle', () => {
    const s = useSimulationStore.getState();
    expect(s.status).toBe('idle');
    expect(s.progress).toBe(0);
    expect(s.result).toBeNull();
    expect(s.error).toBeNull();
    expect(s.params).toBeNull();
  });
});

describe('simulationStore — startSimulation 성공', () => {
  beforeEach(() => {
    useSimulationStore.getState().reset();
    vi.restoreAllMocks();
  });

  it('running으로 전이하고 params·startedAt을 저장한다', async () => {
    vi.spyOn(api, 'runSimulation').mockResolvedValue(MOCK_OUTPUT);
    const p = useSimulationStore.getState().startSimulation(MOCK_INPUT);

    const mid = useSimulationStore.getState();
    expect(mid.status).toBe('running');
    expect(mid.params).toEqual(MOCK_INPUT);
    expect(mid.startedAt).toBeGreaterThan(0);
    expect(mid._abortController).not.toBeNull();

    await p;
    const final = useSimulationStore.getState();
    expect(final.status).toBe('done');
    expect(final.progress).toBe(100);
    expect(final.result).toEqual(MOCK_OUTPUT);
  });
});

describe('simulationStore — 에러', () => {
  beforeEach(() => {
    useSimulationStore.getState().reset();
    vi.restoreAllMocks();
  });

  it('fetch 실패 시 error 상태로 전이한다', async () => {
    vi.spyOn(api, 'runSimulation').mockRejectedValue(new Error('network down'));
    await useSimulationStore.getState().startSimulation(MOCK_INPUT);
    const s = useSimulationStore.getState();
    expect(s.status).toBe('error');
    expect(s.error).toContain('network down');
  });

  it('AbortError는 error로 기록하지 않는다', async () => {
    const abortErr = new axios.Cancel('canceled');
    vi.spyOn(api, 'runSimulation').mockRejectedValue(abortErr);
    await useSimulationStore.getState().startSimulation(MOCK_INPUT);
    const s = useSimulationStore.getState();
    expect(s.status).not.toBe('error');
  });
});

describe('simulationStore — cancelSimulation', () => {
  beforeEach(() => {
    useSimulationStore.getState().reset();
    vi.restoreAllMocks();
  });

  it('running을 idle로 되돌리고 abort를 호출한다', async () => {
    let capturedSignal: AbortSignal | undefined;
    vi.spyOn(api, 'runSimulation').mockImplementation(async (_p, signal) => {
      capturedSignal = signal;
      return new Promise<SimulationOutput>(() => {});
    });

    useSimulationStore.getState().startSimulation(MOCK_INPUT);
    expect(useSimulationStore.getState().status).toBe('running');

    useSimulationStore.getState().cancelSimulation();
    expect(useSimulationStore.getState().status).toBe('idle');
    expect(capturedSignal?.aborted).toBe(true);
  });
});

describe('simulationStore — 교체 실행', () => {
  beforeEach(() => {
    useSimulationStore.getState().reset();
    vi.restoreAllMocks();
  });

  it('실행 중 startSimulation 재호출 시 이전 AbortController가 abort된다', async () => {
    const signals: AbortSignal[] = [];
    vi.spyOn(api, 'runSimulation').mockImplementation(async (_p, signal) => {
      signals.push(signal!);
      return new Promise<SimulationOutput>(() => {});
    });

    useSimulationStore.getState().startSimulation(MOCK_INPUT);
    useSimulationStore.getState().startSimulation({ ...MOCK_INPUT, brand_name: 'Other' });

    expect(signals[0].aborted).toBe(true);
    expect(signals[1].aborted).toBe(false);
    expect(useSimulationStore.getState().params?.brand_name).toBe('Other');
    expect(useSimulationStore.getState().progress).toBe(0);
  });

  it('교체 후 이전 fetch가 뒤늦게 resolve되어도 무시된다 (stale guard)', async () => {
    let resolveFirst!: (v: SimulationOutput) => void;
    const firstPromise = new Promise<SimulationOutput>((res) => {
      resolveFirst = res;
    });
    vi.spyOn(api, 'runSimulation')
      .mockImplementationOnce(() => firstPromise)
      .mockResolvedValueOnce(MOCK_OUTPUT);

    useSimulationStore.getState().startSimulation(MOCK_INPUT);
    await useSimulationStore.getState().startSimulation({ ...MOCK_INPUT, brand_name: 'B' });

    expect(useSimulationStore.getState().status).toBe('done');

    resolveFirst({ ...MOCK_OUTPUT, request_id: 'STALE' } as SimulationOutput);
    await Promise.resolve();

    expect(useSimulationStore.getState().result?.request_id).toBe('r1');
  });
});

describe('simulationStore — 진행률 타이머', () => {
  beforeEach(() => {
    useSimulationStore.getState().reset();
    vi.restoreAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('startSimulation 호출 후 시간에 따라 progress가 증가한다', async () => {
    vi.spyOn(api, 'runSimulation').mockImplementation(
      async () => new Promise<SimulationOutput>(() => {}),
    );

    useSimulationStore.getState().startSimulation(MOCK_INPUT);
    expect(useSimulationStore.getState().progress).toBe(0);

    vi.advanceTimersByTime(10_000);
    const p = useSimulationStore.getState().progress;
    expect(p).toBeGreaterThanOrEqual(8);
    expect(p).toBeLessThanOrEqual(10);
  });

  it('progress는 90%를 초과하지 않는다', async () => {
    vi.spyOn(api, 'runSimulation').mockImplementation(
      async () => new Promise<SimulationOutput>(() => {}),
    );

    useSimulationStore.getState().startSimulation(MOCK_INPUT);
    vi.advanceTimersByTime(200_000);
    expect(useSimulationStore.getState().progress).toBeLessThanOrEqual(90);
  });
});

describe('simulationStore — dismissResult', () => {
  beforeEach(() => {
    useSimulationStore.getState().reset();
    vi.restoreAllMocks();
  });

  it('done 상태를 idle로 되돌리고 result를 null로 만든다', async () => {
    vi.spyOn(api, 'runSimulation').mockResolvedValue(MOCK_OUTPUT);
    await useSimulationStore.getState().startSimulation(MOCK_INPUT);
    expect(useSimulationStore.getState().status).toBe('done');

    useSimulationStore.getState().dismissResult();
    const s = useSimulationStore.getState();
    expect(s.status).toBe('idle');
    expect(s.result).toBeNull();
  });
});
