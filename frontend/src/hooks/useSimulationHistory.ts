/**
 * useSimulationHistory — 통합 history list (foresee + ai).
 *
 * 2026-05-02 DB 분리 후: GET /simulation-foresee + GET /simulation-ai 두 endpoint 동시 호출 →
 * client-side merge + created_at desc 정렬. 페이지네이션은 단순화 (양쪽 size=N 호출 후 머지).
 * 정확한 server-side cross-table pagination 은 별 cycle.
 *
 * remove(id, kind) — kind 따라 적절한 endpoint 호출.
 */
import { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import {
  deleteAIHistory,
  deleteForeseeHistory,
  listAIHistory,
  listForeseeHistory,
  mapAIListItem,
  mapForeseeListItem,
} from '../api/client';
import type {
  HistoryFilterParams,
  HistoryListResponse,
  SimulationHistoryItem,
  SimulationKind,
} from '../types/simulationHistory';

interface UseSimulationHistoryState {
  items: SimulationHistoryItem[];
  total: number;
  page: number;
  size: number;
  isLoading: boolean;
  error: string | null;
}

export interface UseSimulationHistory extends UseSimulationHistoryState {
  refetch: () => Promise<void>;
  remove: (id: number, kind: SimulationKind) => Promise<boolean>;
}

function parseError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    if (err.response?.status === 401) return '로그인이 필요합니다.';
    const detail = (err.response?.data as { detail?: string } | undefined)?.detail;
    return detail ?? err.message;
  }
  return err instanceof Error ? err.message : '알 수 없는 오류';
}

export function useSimulationHistory(filter: HistoryFilterParams): UseSimulationHistory {
  const [state, setState] = useState<UseSimulationHistoryState>({
    items: [],
    total: 0,
    page: filter.page ?? 1,
    size: filter.size ?? 20,
    isLoading: false,
    error: null,
  });

  const fetchList = useCallback(async () => {
    setState((s) => ({ ...s, isLoading: true, error: null }));
    try {
      // 양쪽 endpoint 동시 호출 — 한 쪽 401/500 이어도 부분 결과 표시 위해 allSettled.
      const [foreseeRes, aiRes] = await Promise.allSettled([
        listForeseeHistory(filter),
        listAIHistory(filter),
      ]);

      const foreseeBody: HistoryListResponse | null =
        foreseeRes.status === 'fulfilled' ? foreseeRes.value : null;
      const aiBody: HistoryListResponse | null = aiRes.status === 'fulfilled' ? aiRes.value : null;

      const foreseeItems: SimulationHistoryItem[] = (foreseeBody?.items ?? []).map((row) =>
        mapForeseeListItem(row as unknown as Record<string, any>),
      );
      const aiItems: SimulationHistoryItem[] = (aiBody?.items ?? []).map((row) =>
        mapAIListItem(row as unknown as Record<string, any>),
      );

      const merged = [...foreseeItems, ...aiItems].sort((a, b) => {
        // created_at desc (string ISO 비교 — UTC 동일 timezone 가정)
        if (a.created_at === b.created_at) return 0;
        return a.created_at < b.created_at ? 1 : -1;
      });

      const total = (foreseeBody?.total ?? 0) + (aiBody?.total ?? 0);

      // 한 쪽이 실패한 경우 에러 메시지 노출 (다른 쪽 결과는 그대로 표시).
      const errMsg =
        foreseeRes.status === 'rejected'
          ? `예측 이력 로드 실패: ${parseError(foreseeRes.reason)}`
          : aiRes.status === 'rejected'
            ? `AI 분석 이력 로드 실패: ${parseError(aiRes.reason)}`
            : null;

      setState({
        items: merged,
        total,
        page: filter.page ?? 1,
        size: filter.size ?? 20,
        isLoading: false,
        error: errMsg,
      });
    } catch (err) {
      setState((s) => ({ ...s, isLoading: false, error: parseError(err) }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter.client_name, filter.from_date, filter.to_date, filter.page, filter.size, filter.sort]);

  useEffect(() => {
    void fetchList();
  }, [fetchList]);

  const remove = useCallback(async (id: number, kind: SimulationKind): Promise<boolean> => {
    try {
      if (kind === 'foresee') {
        await deleteForeseeHistory(id);
      } else {
        await deleteAIHistory(id);
      }
      // optimistic — 목록에서 즉시 제거. 서버 실패 시 refetch로 복구됨.
      setState((s) => ({
        ...s,
        items: s.items.filter((it) => !(it.id === id && it.kind === kind)),
        total: Math.max(0, s.total - 1),
      }));
      return true;
    } catch (err) {
      setState((s) => ({ ...s, error: parseError(err) }));
      return false;
    }
  }, []);

  return { ...state, refetch: fetchList, remove };
}
