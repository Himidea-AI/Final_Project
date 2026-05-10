/**
 * useSimulationDetail — kind 별 detail fetch.
 *
 * 2026-05-02 DB 분리 후 시그니처: (id, kind).
 * - kind='foresee' → GET /simulation-foresee/{id} (mapForeseeDetailToHistoryDetail)
 * - kind='ai'      → GET /simulation-ai/{id}      (mapAIDetailToHistoryDetail)
 * - kind='abm'     → GET /history/abm/{id}        (raw row → ABM-shaped HistoryDetail)
 * - kind=null      → legacy /simulation-history/{id} fallback (마이그레이션 미진행 row)
 */
import { useEffect, useState } from 'react';
import axios from 'axios';
import {
  getAIDetail,
  getAbmDetail,
  getForeseeDetail,
  getSimulationHistoryDetail,
} from '../api/client';
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

    // ABM detail 은 raw row (Record<string, unknown>) 반환 → SimulationHistoryDetail shape 으로 wrap.
    // ABM `result` JSONB 가 곧 simulation_result (ABM 응답 schema 그대로). HistoryDashboardView 는
    // ABM 케이스에서는 PDF 다운로드 + 메타 헤더만 노출 — 별도 ABM 전용 view 는 추후 작업.
    // ABM result JSONB 안에 density_grid (28×24×시간 격자) + trajectory (300 sample × 시간) +
    // thoughts + langgraph_result 거대 키 포함 → JSON.parse 후 React render hang ("응답없음").
    // 화면 표시에 불필요 → fetch 단계에서 strip (2026-05-10).
    const HEAVY_KEYS = ['density_grid', 'trajectory', 'thoughts', 'langgraph_result'];
    const stripHeavy = (result: unknown): unknown => {
      if (!result || typeof result !== 'object' || Array.isArray(result)) return result;
      const out: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(result as Record<string, unknown>)) {
        if (HEAVY_KEYS.includes(k)) continue;
        out[k] = v;
      }
      return out;
    };

    const abmFetcher = (): Promise<SimulationHistoryDetail> =>
      getAbmDetail(id).then((row) => {
        const r = row as Record<string, unknown>;
        return {
          id: Number(r.id),
          client_name: String(r.client_name ?? ''),
          brand_name: String(r.brand_name ?? ''),
          district: String(r.target_district ?? '—'),
          business_type: (r.business_type as string | null) ?? null,
          created_at: String(r.created_at ?? new Date().toISOString()),
          simulation_result: stripHeavy(r.result) as SimulationHistoryDetail['simulation_result'],
          scenario: (r.scenario as SimulationHistoryDetail['scenario']) ?? null,
        } as SimulationHistoryDetail;
      });

    const fetcher: Promise<SimulationHistoryDetail> =
      kind === 'foresee'
        ? getForeseeDetail(id)
        : kind === 'ai'
          ? getAIDetail(id)
          : kind === 'abm'
            ? abmFetcher()
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
