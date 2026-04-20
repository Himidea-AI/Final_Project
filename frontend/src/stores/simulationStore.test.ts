import { describe, it, expect, beforeEach } from 'vitest';
import { useSimulationStore } from './simulationStore';

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
