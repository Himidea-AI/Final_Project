/**
 * 시뮬 이력 저장 hooks — 2026-05-02 DB 분리 후 ML(foresee) / AI(ai) 별 분리.
 *
 * - useSaveForeseeHistory : POST /simulation-foresee
 * - useSaveAIHistory      : POST /simulation-ai
 * - useSaveSimulation     : @deprecated legacy /simulation-history. 다른 곳에서 import 중일 가능성으로 유지.
 */
import { useCallback, useState } from 'react';
import axios from 'axios';
import { saveAIHistory, saveForeseeHistory, saveSimulationHistory } from '../api/client';
import type {
  SaveAIPayload,
  SaveForeseePayload,
  SaveSimulationPayload,
  SaveSimulationResponse,
} from '../types/simulationHistory';

interface UseSaveSimulationState {
  isSaving: boolean;
  error: string | null;
  lastResponse: SaveSimulationResponse | null;
}

export interface UseSaveHistoryHandle<TPayload> extends UseSaveSimulationState {
  save: (payload: TPayload) => Promise<SaveSimulationResponse | null>;
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

function makeSaveHook<TPayload>(
  saveFn: (payload: TPayload) => Promise<SaveSimulationResponse>,
): () => UseSaveHistoryHandle<TPayload> {
  return function useSaveHook(): UseSaveHistoryHandle<TPayload> {
    const [state, setState] = useState<UseSaveSimulationState>({
      isSaving: false,
      error: null,
      lastResponse: null,
    });

    const save = useCallback(async (payload: TPayload): Promise<SaveSimulationResponse | null> => {
      setState({ isSaving: true, error: null, lastResponse: null });
      try {
        const res = await saveFn(payload);
        setState({ isSaving: false, error: null, lastResponse: res });
        return res;
      } catch (err) {
        setState({ isSaving: false, error: parseError(err), lastResponse: null });
        return null;
      }
    }, []);

    const reset = useCallback(() => {
      setState({ isSaving: false, error: null, lastResponse: null });
    }, []);

    return { ...state, save, reset };
  };
}

/** ML 예측 (Predict 탭) 저장 hook */
export const useSaveForeseeHistory = makeSaveHook<SaveForeseePayload>(saveForeseeHistory);

/** AI 분석 (Analyze 탭) 저장 hook */
export const useSaveAIHistory = makeSaveHook<SaveAIPayload>(saveAIHistory);

/** @deprecated legacy /simulation-history. 신규 코드는 useSaveForeseeHistory / useSaveAIHistory 사용. */
export const useSaveSimulation = makeSaveHook<SaveSimulationPayload>(saveSimulationHistory);

/** legacy alias type — 기존 import 경로 호환 */
export type UseSaveSimulation = UseSaveHistoryHandle<SaveSimulationPayload>;
