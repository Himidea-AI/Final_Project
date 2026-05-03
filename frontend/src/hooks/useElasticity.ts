/**
 * useElasticity — TCN 시나리오 탄성치 조회 훅.
 *
 * dong_code 또는 industry_code 가 null 이면 호출 안 함.
 * AbortController 로 이전 요청 자동 cancel (dependency 변경 시).
 */

import { useEffect, useState } from 'react';
import axios from 'axios';
import { fetchElasticity, ElasticityNotFoundError } from '../api/elasticity';
import type { ElasticityResponse } from '../types/elasticity';

interface State {
  data: ElasticityResponse | null;
  error: Error | null;
  loading: boolean;
}

export function useElasticity(
  dongCode: string | null | undefined,
  industryCode: string | null | undefined,
): State {
  const [state, setState] = useState<State>({ data: null, error: null, loading: false });

  useEffect(() => {
    if (!dongCode || !industryCode) {
      setState({ data: null, error: null, loading: false });
      return;
    }
    const controller = new AbortController();
    setState((s) => ({ ...s, loading: true, error: null }));
    fetchElasticity(dongCode, industryCode, controller.signal)
      .then((res) => {
        if (!controller.signal.aborted) {
          setState({ data: res, error: null, loading: false });
        }
      })
      .catch((err) => {
        if (axios.isCancel(err) || controller.signal.aborted) return;
        if (err instanceof ElasticityNotFoundError) {
          setState({ data: null, error: err, loading: false });
          return;
        }
        const wrapped = err instanceof Error ? err : new Error('elasticity 조회 실패');
        setState({ data: null, error: wrapped, loading: false });
      });
    return () => {
      controller.abort();
    };
  }, [dongCode, industryCode]);

  return state;
}
