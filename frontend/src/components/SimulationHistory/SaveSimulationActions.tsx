/**
 * SaveSimulationActions — 시뮬 이력 저장 SaveButton + SaveDialog 통합 컴포넌트.
 *
 * IM3-259 분리 호출 (/predict + /analyze/llm 독립 백그라운드) 환경에서
 * "내가 보던 결과 화면" 의 헤더에 저장 버튼이 있어야 UX 자연스러움.
 * DashboardPredictPage / DashboardAnalyzePage / 등 어느 페이지에서든 마운트 가능.
 *
 * saveSim.save 는 simulation_result 통째 저장 — 두 슬라이스 (예측 + 분석) 다 포함.
 * 어느 페이지에서 누르든 동일 결과. 한 번 저장 후엔 isSaved 분기로 비활성.
 *
 * scenario: store.params 그대로 — chip 입력 (target_age_groups 등) 정상 저장 → backend customer_segment 산출.
 */

import { useState } from 'react';
import { useAuth } from '../../auth/AuthContext';
import { useSimulationStore } from '../../stores/simulationStore';
import { useSaveSimulation } from '../../hooks/useSaveSimulation';
import { useToast } from '../Toast';
import { formatDocumentId } from '../../types/simulationHistory';
import type { SimulationOutput } from '../../types';
import { SaveButton } from './SaveButton';
import { SaveDialog } from './SaveDialog';

interface Props {
  simResult: SimulationOutput;
  brandName: string;
  /** 저장된 history ID (있으면 isSaved 분기). DashboardOutlet context 또는 store 에서 전달. */
  savedHistoryId?: number | null;
}

export function SaveSimulationActions({ simResult, brandName, savedHistoryId }: Props) {
  const { user, brand } = useAuth();
  const { showToast } = useToast();
  const saveSim = useSaveSimulation();
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const params = useSimulationStore((s) => s.params);
  const isSaved = savedHistoryId != null;

  // 저장에 사용될 동/업종 — store.params 우선, simResult fallback
  const targetDistrict =
    params?.target_districts?.[0] ?? params?.target_district ?? simResult.target_district ?? '';
  const bizKey = params?.business_type ?? '';

  const handleConfirmSave = async (clientName: string) => {
    const compIntel = simResult.competitor_intel as Record<string, unknown> | null | undefined;
    const signalRaw = compIntel?.['market_entry_signal'];
    const signal =
      signalRaw === 'green' || signalRaw === 'yellow' || signalRaw === 'red' ? signalRaw : null;
    const verdictSummary =
      simResult.ai_recommendation?.split(/[.!?。]/)[0]?.slice(0, 200) ??
      simResult.analysis_report?.slice(0, 200) ??
      null;
    const res = await saveSim.save({
      client_name: clientName,
      district: targetDistrict,
      brand_name: brand?.brand_name || user?.company_name || brandName || '브랜드 미지정',
      business_type: bizKey || null,
      scenario: params ? (params as unknown as Record<string, unknown>) : null,
      simulation_result: simResult,
      ai_verdict_summary: verdictSummary,
      market_entry_signal: signal,
    });
    if (res) {
      useSimulationStore.getState().setSavedHistoryId(res.id);
      setSaveDialogOpen(false);
      showToast(
        'success',
        `${clientName} 고객님 시뮬 이력이 저장되었습니다. (${formatDocumentId(res.id)})`,
      );
    }
  };

  return (
    <>
      <SaveButton
        onClick={() => setSaveDialogOpen(true)}
        saved={isSaved}
        label={isSaved ? `저장됨 · ${formatDocumentId(savedHistoryId ?? null)}` : undefined}
      />
      <SaveDialog
        open={saveDialogOpen}
        onClose={() => {
          setSaveDialogOpen(false);
          saveSim.reset();
        }}
        meta={{
          brandName: brand?.brand_name || user?.company_name || brandName || '브랜드',
          district: targetDistrict,
          managerName: user?.contact_name || user?.email || '매니저',
        }}
        isSaving={saveSim.isSaving}
        errorMessage={saveSim.error}
        onConfirm={handleConfirmSave}
      />
    </>
  );
}
