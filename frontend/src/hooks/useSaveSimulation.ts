import { useCallback, useState } from 'react';
import axios from 'axios';
import { saveSimulationHistory } from '../api/client';
import type { SaveSimulationPayload, SaveSimulationResponse } from '../types/simulationHistory';

interface UseSaveSimulationState {
  isSaving: boolean;
  error: string | null;
  lastResponse: SaveSimulationResponse | null;
}

export interface UseSaveSimulation extends UseSaveSimulationState {
  save: (payload: SaveSimulationPayload) => Promise<SaveSimulationResponse | null>;
  reset: () => void;
}

// Bearer 미주입(토큰 없음) / 만료 / 권한 부족 메시지를 UI 친화적으로 변환
function parseError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const status = err.response?.status;
    const detail = (err.response?.data as { detail?: string } | undefined)?.detail;
    if (status === 401) return '로그인이 필요합니다. 다시 로그인 후 시도해주세요.';
    if (status === 403) return '저장 권한이 없습니다.';
    if (status === 422) return detail ?? '입력값이 올바르지 않습니다.';
    if (detail) return detail;
    return err.message;
  }
  return err instanceof Error ? err.message : '알 수 없는 오류';
}

export function useSaveSimulation(): UseSaveSimulation {
  const [state, setState] = useState<UseSaveSimulationState>({
    isSaving: false,
    error: null,
    lastResponse: null,
  });

  const save = useCallback(
    async (payload: SaveSimulationPayload): Promise<SaveSimulationResponse | null> => {
      setState({ isSaving: true, error: null, lastResponse: null });
      try {
        const res = await saveSimulationHistory(payload);
        setState({ isSaving: false, error: null, lastResponse: res });
        return res;
      } catch (err) {
        setState({ isSaving: false, error: parseError(err), lastResponse: null });
        return null;
      }
    },
    [],
  );

  const reset = useCallback(() => {
    setState({ isSaving: false, error: null, lastResponse: null });
  }, []);

  return { ...state, save, reset };
}
