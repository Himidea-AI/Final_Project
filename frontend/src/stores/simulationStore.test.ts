import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import axios from 'axios';
import { useSimulationStore } from './simulationStore';
import * as api from '../api/client';
import type {
  AnalysisOutput,
  DistrictPredictionResult,
  SimulationInput,
  SimulationOutput,
} from '../types';

const MOCK_INPUT: SimulationInput = {
  business_type: 'cafe',
  brand_name: 'Test',
  target_district: '서교동',
  existing_stores: [],
  monthly_rent: 1000000,
  scenarios: [],
};

const MOCK_PRED: DistrictPredictionResult[] = [
  { district: '서교동', is_excluded_combo: false } as unknown as DistrictPredictionResult,
];

const MOCK_ANALYSIS: AnalysisOutput = {
  winner_district: '서교동',
} as unknown as AnalysisOutput;

// Legacy MOCK_OUTPUT — used only for tests that exercise the deprecated `result` field
// (e.g., persisted history restore). Not produced by the new startSimulation flow.
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
  quarterly_projection: [],
  comparison: [],
  legal_risks: [],
} as unknown as SimulationOutput;
void MOCK_OUTPUT;

/** Common helper — happy-path mocks for both endpoints. */
function mockHappyPath() {
  vi.spyOn(api, 'fetchPredict').mockResolvedValue(MOCK_PRED);
  vi.spyOn(api, 'fetchAnalyzeLlm').mockResolvedValue(MOCK_ANALYSIS);
}

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
    expect(s.prediction.status).toBe('idle');
    expect(s.analysis.status).toBe('idle');
  });
});

describe('simulationStore — startSimulation 성공', () => {
  beforeEach(() => {
    useSimulationStore.getState().reset();
    vi.restoreAllMocks();
  });

  it('running으로 전이하고 params·startedAt을 저장한다', async () => {
    mockHappyPath();
    const p = useSimulationStore.getState().startSimulation(MOCK_INPUT);

    const mid = useSimulationStore.getState();
    expect(mid.status).toBe('running');
    expect(mid.params).toEqual(MOCK_INPUT);
    expect(mid.startedAt).toBeGreaterThan(0);
    expect(mid._abortController).not.toBeNull();
    expect(mid.prediction.status).toBe('running');
    expect(mid.analysis.status).toBe('running');

    await p;
    const final = useSimulationStore.getState();
    expect(final.status).toBe('done');
    expect(final.progress).toBe(100);
    expect(final.prediction.status).toBe('done');
    expect(final.analysis.status).toBe('done');
  });
});

describe('simulationStore — 에러', () => {
  beforeEach(() => {
    useSimulationStore.getState().reset();
    vi.restoreAllMocks();
  });

  it('두 API 모두 실패 시 status=error', async () => {
    vi.spyOn(api, 'fetchPredict').mockRejectedValue(new Error('network down'));
    vi.spyOn(api, 'fetchAnalyzeLlm').mockRejectedValue(new Error('llm down'));
    await useSimulationStore.getState().startSimulation(MOCK_INPUT);
    const s = useSimulationStore.getState();
    expect(s.status).toBe('error');
    expect(s.error).toContain('network down');
    expect(s.error).toContain('llm down');
  });

  it('AbortError(양쪽) 는 error로 기록하지 않는다', async () => {
    const abortErr = new axios.Cancel('canceled');
    vi.spyOn(api, 'fetchPredict').mockRejectedValue(abortErr);
    vi.spyOn(api, 'fetchAnalyzeLlm').mockRejectedValue(abortErr);
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

  it('running을 idle로 되돌린다', async () => {
    // 양쪽 다 영원히 pending → cancelSimulation 으로 abort
    vi.spyOn(api, 'fetchPredict').mockImplementation(
      () => new Promise<DistrictPredictionResult[]>(() => {}),
    );
    vi.spyOn(api, 'fetchAnalyzeLlm').mockImplementation(
      () => new Promise<AnalysisOutput>(() => {}),
    );

    useSimulationStore.getState().startSimulation(MOCK_INPUT);
    expect(useSimulationStore.getState().status).toBe('running');

    useSimulationStore.getState().cancelSimulation();
    expect(useSimulationStore.getState().status).toBe('idle');
    expect(useSimulationStore.getState().prediction.status).toBe('idle');
    expect(useSimulationStore.getState().analysis.status).toBe('idle');
  });
});

describe('simulationStore — 교체 실행', () => {
  beforeEach(() => {
    useSimulationStore.getState().reset();
    vi.restoreAllMocks();
  });

  it('실행 중 startSimulation 재호출 시 이전 AbortController가 abort된다', async () => {
    const controllers: AbortController[] = [];
    // capture controllers via the global controller after startSimulation set
    vi.spyOn(api, 'fetchPredict').mockImplementation(
      () => new Promise<DistrictPredictionResult[]>(() => {}),
    );
    vi.spyOn(api, 'fetchAnalyzeLlm').mockImplementation(
      () => new Promise<AnalysisOutput>(() => {}),
    );

    useSimulationStore.getState().startSimulation(MOCK_INPUT);
    controllers.push(useSimulationStore.getState()._abortController!);
    useSimulationStore.getState().startSimulation({ ...MOCK_INPUT, brand_name: 'Other' });
    controllers.push(useSimulationStore.getState()._abortController!);

    expect(controllers[0].signal.aborted).toBe(true);
    expect(controllers[1].signal.aborted).toBe(false);
    expect(useSimulationStore.getState().params?.brand_name).toBe('Other');
    expect(useSimulationStore.getState().progress).toBe(0);
  });

  it('교체 후 이전 fetch가 뒤늦게 resolve되어도 무시된다 (stale guard)', async () => {
    let resolveFirstPred!: (v: DistrictPredictionResult[]) => void;
    let resolveFirstAnalysis!: (v: AnalysisOutput) => void;
    const firstPred = new Promise<DistrictPredictionResult[]>((res) => {
      resolveFirstPred = res;
    });
    const firstAnalysis = new Promise<AnalysisOutput>((res) => {
      resolveFirstAnalysis = res;
    });
    vi.spyOn(api, 'fetchPredict')
      .mockImplementationOnce(() => firstPred)
      .mockResolvedValueOnce(MOCK_PRED);
    vi.spyOn(api, 'fetchAnalyzeLlm')
      .mockImplementationOnce(() => firstAnalysis)
      .mockResolvedValueOnce(MOCK_ANALYSIS);

    useSimulationStore.getState().startSimulation(MOCK_INPUT);
    await useSimulationStore.getState().startSimulation({ ...MOCK_INPUT, brand_name: 'B' });

    expect(useSimulationStore.getState().status).toBe('done');
    const winnerAfterSecond = useSimulationStore.getState().analysis.data?.winner_district;
    expect(winnerAfterSecond).toBe('서교동');

    // late resolve of first run — should be ignored by stale guard
    resolveFirstPred([
      { district: 'STALE', is_excluded_combo: false } as unknown as DistrictPredictionResult,
    ]);
    resolveFirstAnalysis({ winner_district: 'STALE' } as unknown as AnalysisOutput);
    await Promise.resolve();
    await Promise.resolve();

    expect(useSimulationStore.getState().analysis.data?.winner_district).toBe('서교동');
    expect(useSimulationStore.getState().prediction.data?.[0].district).toBe('서교동');
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
    vi.spyOn(api, 'fetchPredict').mockImplementation(
      () => new Promise<DistrictPredictionResult[]>(() => {}),
    );
    vi.spyOn(api, 'fetchAnalyzeLlm').mockImplementation(
      () => new Promise<AnalysisOutput>(() => {}),
    );

    useSimulationStore.getState().startSimulation(MOCK_INPUT);
    expect(useSimulationStore.getState().progress).toBe(0);

    vi.advanceTimersByTime(10_000);
    const p = useSimulationStore.getState().progress;
    expect(p).toBeGreaterThanOrEqual(8);
    expect(p).toBeLessThanOrEqual(10);
  });

  it('progress는 90%를 초과하지 않는다', async () => {
    vi.spyOn(api, 'fetchPredict').mockImplementation(
      () => new Promise<DistrictPredictionResult[]>(() => {}),
    );
    vi.spyOn(api, 'fetchAnalyzeLlm').mockImplementation(
      () => new Promise<AnalysisOutput>(() => {}),
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

  it('done 상태를 idle로 되돌리고 슬라이스를 초기화한다', async () => {
    mockHappyPath();
    await useSimulationStore.getState().startSimulation(MOCK_INPUT);
    expect(useSimulationStore.getState().status).toBe('done');

    useSimulationStore.getState().dismissResult();
    const s = useSimulationStore.getState();
    expect(s.status).toBe('idle');
    expect(s.result).toBeNull();
    expect(s.prediction.status).toBe('idle');
    expect(s.analysis.status).toBe('idle');
  });
});

// ─────────────────────────────────────────────────────────────
// IM3-259 슬라이스 분리 + Promise.allSettled — 신규 단위 테스트 (A3)
// ─────────────────────────────────────────────────────────────

describe('simulationStore — Promise.allSettled', () => {
  beforeEach(() => {
    useSimulationStore.getState().reset();
    useSimulationStore.setState({
      status: 'idle',
      prediction: { status: 'idle', data: null, error: null },
      analysis: { status: 'idle', data: null, error: null },
      params: null,
    });
    vi.restoreAllMocks();
  });

  it('둘 다 성공 → status=done, 두 슬라이스 done', async () => {
    vi.spyOn(api, 'fetchPredict').mockResolvedValue([
      { district: '공덕동', is_excluded_combo: false } as unknown as DistrictPredictionResult,
    ]);
    vi.spyOn(api, 'fetchAnalyzeLlm').mockResolvedValue({
      winner_district: '공덕동',
    } as unknown as AnalysisOutput);

    await useSimulationStore
      .getState()
      .startSimulation({ districts: ['공덕동'] } as unknown as SimulationInput);

    const s = useSimulationStore.getState();
    expect(s.status).toBe('done');
    expect(s.prediction.status).toBe('done');
    expect(s.analysis.status).toBe('done');
    expect(s.prediction.data).toHaveLength(1);
    expect(s.analysis.data?.winner_district).toBe('공덕동');
  });

  it('predict 만 실패 → status=done (부분 성공), prediction.status=error', async () => {
    vi.spyOn(api, 'fetchPredict').mockRejectedValue(new Error('predict 5xx'));
    vi.spyOn(api, 'fetchAnalyzeLlm').mockResolvedValue({
      winner_district: '공덕동',
    } as unknown as AnalysisOutput);

    await useSimulationStore
      .getState()
      .startSimulation({ districts: ['공덕동'] } as unknown as SimulationInput);

    const s = useSimulationStore.getState();
    expect(s.status).toBe('done');
    expect(s.prediction.status).toBe('error');
    expect(s.prediction.error).toContain('predict 5xx');
    expect(s.analysis.status).toBe('done');
  });

  it('둘 다 실패 → status=error', async () => {
    vi.spyOn(api, 'fetchPredict').mockRejectedValue(new Error('p fail'));
    vi.spyOn(api, 'fetchAnalyzeLlm').mockRejectedValue(new Error('a fail'));

    await useSimulationStore
      .getState()
      .startSimulation({ districts: ['공덕동'] } as unknown as SimulationInput);

    const s = useSimulationStore.getState();
    expect(s.status).toBe('error');
    expect(s.error).toContain('p fail');
    expect(s.error).toContain('a fail');
  });

  it('retryPrediction 만 재호출 → analysis 슬라이스 보존', async () => {
    useSimulationStore.setState({
      params: { districts: ['공덕동'] } as unknown as SimulationInput,
      prediction: { status: 'error', data: null, error: 'previous fail' },
      analysis: {
        status: 'done',
        data: { winner_district: '공덕동' } as unknown as AnalysisOutput,
        error: null,
      },
      status: 'done',
    });
    vi.spyOn(api, 'fetchPredict').mockResolvedValue([
      { district: '공덕동', is_excluded_combo: false } as unknown as DistrictPredictionResult,
    ]);

    await useSimulationStore.getState().retryPrediction();

    const s = useSimulationStore.getState();
    expect(s.prediction.status).toBe('done');
    expect(s.analysis.status).toBe('done'); // 보존
    expect(s.analysis.data?.winner_district).toBe('공덕동');
  });
});
