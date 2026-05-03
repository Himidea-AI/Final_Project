/**
 * DashboardPredictPage — /dashboard/predict 라우트.
 * ← Hub back + PredictGroup (5 서브탭).
 */

import { ArrowLeft, ListChecks } from 'lucide-react';
import { useNavigate, useOutletContext } from 'react-router-dom';
import type { SimulationOutput } from '../../types';
import type { DetailModalContent } from '../../components/SimulationResult/dashboard/shared/DetailModal';
import { PredictGroup } from '../../components/SimulationResult/dashboard/groups/PredictGroup';
import { SaveSimulationActions } from '../../components/SimulationHistory/SaveSimulationActions';

interface OutletCtx {
  simResult: SimulationOutput;
  brandName: string;
  savedHistoryId?: number | null;
  openModal: (content: DetailModalContent) => void;
  openConditionDrawer?: () => void;
}

export default function DashboardPredictPage() {
  const { simResult, brandName, savedHistoryId, openModal, openConditionDrawer } =
    useOutletContext<OutletCtx>();
  const navigate = useNavigate();

  return (
    <div className="mx-auto max-w-[1728px] px-8 pt-28 pb-8">
      <div className="mb-6 flex items-center justify-between gap-4">
        <button
          type="button"
          onClick={() => navigate('/dashboard')}
          className="inline-flex items-center gap-1.5 rounded-md px-1 py-0.5 text-xs font-bold uppercase tracking-widest text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Hub
        </button>
        {/* IM3-259 분리 호출 — 예측 결과 화면 헤더에 분석 조건 + 저장 버튼 (slice 별 위치). */}
        <div className="flex items-center gap-3">
          {openConditionDrawer && (
            <button
              type="button"
              onClick={openConditionDrawer}
              className="inline-flex items-center gap-2 rounded-xl border border-border bg-card px-5 py-2.5 text-sm font-bold tracking-wider text-foreground transition-all duration-200 hover:border-primary/40 hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              <ListChecks className="h-4 w-4" strokeWidth={2.5} />
              분석 조건
            </button>
          )}
          <SaveSimulationActions
            simResult={simResult}
            brandName={brandName}
            savedHistoryId={savedHistoryId}
          />
        </div>
      </div>
      <PredictGroup simResult={simResult} openModal={openModal} />
    </div>
  );
}
