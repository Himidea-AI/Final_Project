import { useEffect, useState } from 'react';
import axios from 'axios';
import { getTokenUsage } from '../api/client';
import type { TokenUsageResponse } from '../types/tokenUsage';

interface State {
  data: TokenUsageResponse | null;
  isLoading: boolean;
  /** 404 — 엔드포인트 미구현 상태 (B1 대기) */
  notImplemented: boolean;
  error: string | null;
}

function parseError(err: unknown): { message: string; notImplemented: boolean } {
  if (axios.isAxiosError(err)) {
    const status = err.response?.status;
    if (status === 404) {
      return {
        message:
          '백엔드 /api/ops/token-usage 엔드포인트가 아직 구현되지 않았습니다 (B1 예진 대기).',
        notImplemented: true,
      };
    }
    const detail = (err.response?.data as { detail?: string } | undefined)?.detail;
    return { message: detail ?? err.message, notImplemented: false };
  }
  return { message: err instanceof Error ? err.message : '알 수 없는 오류', notImplemented: false };
}

export function useTokenUsage(filter: { from?: string; to?: string }): State {
  const [state, setState] = useState<State>({
    data: null,
    isLoading: true,
    notImplemented: false,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;
    setState((s) => ({ ...s, isLoading: true, error: null, notImplemented: false }));
    getTokenUsage(filter)
      .then((data) => {
        if (cancelled) return;
        setState({ data, isLoading: false, error: null, notImplemented: false });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const { message, notImplemented } = parseError(err);
        setState({ data: null, isLoading: false, error: message, notImplemented });
      });
    return () => {
      cancelled = true;
    };
  }, [filter.from, filter.to]);

  return state;
}
