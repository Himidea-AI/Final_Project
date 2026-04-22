import { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { deleteSimulationHistory, listSimulationHistory } from '../api/client';
import type {
  HistoryFilterParams,
  HistoryListResponse,
  SimulationHistoryItem,
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
  remove: (id: number) => Promise<boolean>;
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
      const res: HistoryListResponse = await listSimulationHistory(filter);
      setState({
        items: res.items,
        total: res.total,
        page: res.page,
        size: res.size,
        isLoading: false,
        error: null,
      });
    } catch (err) {
      setState((s) => ({ ...s, isLoading: false, error: parseError(err) }));
    }
  }, [
    filter.client_name,
    filter.from_date,
    filter.to_date,
    filter.page,
    filter.size,
    filter.sort,
    // eslint-disable-next-line react-hooks/exhaustive-deps
  ]);

  useEffect(() => {
    void fetchList();
  }, [fetchList]);

  const remove = useCallback(async (id: number): Promise<boolean> => {
    try {
      await deleteSimulationHistory(id);
      // optimistic — 목록에서 즉시 제거. 서버 실패 시 refetch로 복구됨.
      setState((s) => ({
        ...s,
        items: s.items.filter((it) => it.id !== id),
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
