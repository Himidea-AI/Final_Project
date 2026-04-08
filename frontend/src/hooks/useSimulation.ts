import { useState, useCallback } from 'react';
import { SimulationInput, SimulationOutput } from '../types';
import { runSimulation } from '../api/client';

export const useSimulation = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SimulationOutput | null>(null);

  const execute = useCallback(async (input: SimulationInput) => {
    setLoading(true);
    setError(null);

    try {
      const data = await runSimulation(input);

      setResult(data);
      return data;
    } catch (err: any) {
      const message = err.message || '분석 중 예상치 못한 오류가 발생했습니다.';
      setError(message);
      console.error('[Simulation Hook Error]:', err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = () => {
    setResult(null);
    setError(null);
  };

  return { execute, loading, error, result, reset };
};
