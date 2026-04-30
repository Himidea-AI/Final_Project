/**
 * DashboardAnalyzePage — /dashboard/analyze 라우트.
 * ← Hub back + AnalyzeGroup (5 서브탭).
 */

import { ArrowLeft } from 'lucide-react';
import { useNavigate, useOutletContext } from 'react-router-dom';
import type { SimulationOutput } from '../../types';
import type { DetailModalContent } from '../../components/SimulationResult/dashboard/shared/DetailModal';
import { AnalyzeGroup } from '../../components/SimulationResult/dashboard/groups/AnalyzeGroup';

interface OutletCtx {
  simResult: SimulationOutput;
  openModal: (content: DetailModalContent) => void;
}

export default function DashboardAnalyzePage() {
  const { simResult, openModal } = useOutletContext<OutletCtx>();
  const navigate = useNavigate();

  return (
    <div className="mx-auto max-w-[1728px] px-8 pt-28 pb-8">
      <div className="mb-6">
        <button
          type="button"
          onClick={() => navigate('/dashboard')}
          className="inline-flex items-center gap-1.5 rounded-md px-1 py-0.5 text-xs font-bold uppercase tracking-widest text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Hub
        </button>
      </div>
      <AnalyzeGroup simResult={simResult} openModal={openModal} />
    </div>
  );
}
