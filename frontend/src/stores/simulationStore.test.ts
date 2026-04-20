import { describe, it, expect, beforeEach, vi } from 'vitest';
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
