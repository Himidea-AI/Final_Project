/**
 * useSimulationDetail — kind 별 detail fetch.
 *
 * 2026-05-02 DB 분리 후 시그니처: (id, kind).
 * - kind='foresee' → GET /simulation-foresee/{id} (mapForeseeDetailToHistoryDetail)
 * - kind='ai'      → GET /simulation-ai/{id}      (mapAIDetailToHistoryDetail)
 * - kind=null      → legacy /simulation-history/{id} fallback (마이그레이션 미진행 row)
 */
import { useEffect, useState } from 'react';
import axios from 'axios';
import { getAIDetail, getForeseeDetail, getSimulationHistoryDetail } from '../api/client';
import type { SimulationHistoryDetail, SimulationKind } from '../types/simulationHistory';

interface UseSimulationDetailState {
  data: SimulationHistoryDetail | null;
  isLoading: boolean;
  error: string | null;
  /** true면 서버가 404 — 존재하지 않거나 권한 없음 */
  notFound: boolean;
}

function parseError(err: unknown): { message: string; notFound: boolean } {
  if (axios.isAxiosError(err)) {
    const status = err.response?.status;
    if (status === 404)
      return { message: '이력을 찾을 수 없거나 접근 권한이 없습니다', notFound: true };
    if (status === 401) return { message: '로그인이 필요합니다.', notFound: false };
    const detail = (err.response?.data as { detail?: string } | undefined)?.detail;
    return { message: detail ?? err.message, notFound: false };
  }
  return { message: err instanceof Error ? err.message : '알 수 없는 오류', notFound: false };
}

export function useSimulationDetail(
  id: number | null,
  kind: SimulationKind | null,
): UseSimulationDetailState {
  const [state, setState] = useState<UseSimulationDetailState>({
    data: null,
    isLoading: id != null,
    error: null,
    notFound: false,
  });

  useEffect(() => {
    if (id == null) {
      setState({ data: null, isLoading: false, error: null, notFound: false });
      return;
    }
    let cancelled = false;
    setState({ data: null, isLoading: true, error: null, notFound: false });

    const fetcher: Promise<SimulationHistoryDetail> =
      kind === 'foresee'
        ? getForeseeDetail(id)
        : kind === 'ai'
          ? getAIDetail(id)
          : getSimulationHistoryDetail(id);

    fetcher
      .then((data) => {
        if (cancelled) return;
        setState({ data, isLoading: false, error: null, notFound: false });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const { message, notFound } = parseError(err);
        setState({ data: null, isLoading: false, error: message, notFound });
      });
    return () => {
      cancelled = true;
    };
  }, [id, kind]);

  return state;
}
