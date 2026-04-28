/**
 * DashboardAbmPage — /dashboard/abm 라우트.
 * ← Hub back + AbmGroup (단일 ABM 시뮬레이터, 서브탭 없음).
 */

import { ArrowLeft } from 'lucide-react';
import { useNavigate, useOutletContext } from 'react-router-dom';
import type { SimulationOutput } from '../../types';
import { AbmGroup } from '../../components/SimulationResult/dashboard/groups/AbmGroup';

interface OutletCtx {
  simResult: SimulationOutput;
  brandName: string;
  businessType?: string | null;
}

export default function DashboardAbmPage() {
  const { simResult, brandName, businessType } = useOutletContext<OutletCtx>();
  const navigate = useNavigate();

  return (
    <div className="mx-auto max-w-[1728px] px-8 pt-28 pb-8">
      <div className="mb-6">
        <button
          type="button"
          onClick={() => navigate('/dashboard')}
          className="inline-flex items-center gap-1.5 rounded-md px-1 py-0.5 text-xs font-bold uppercase tracking-widest text-stone-500 transition-colors hover:text-stone-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-stone-400"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Hub
        </button>
      </div>
      <AbmGroup simResult={simResult} brandName={brandName} businessType={businessType} />
    </div>
  );
}
