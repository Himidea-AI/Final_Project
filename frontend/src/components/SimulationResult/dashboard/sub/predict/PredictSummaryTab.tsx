/**
 * PredictSummaryTab — 예측 그룹 요약 (ML 숫자 카드만)
 * 2026-04-28 IA 재구조 — SummaryTab 의 ProfitSimulationPanelFull 의 일부 분해.
 * computeDecision 등 LLM 의존은 AnalyzeAiSummaryTab 에 이관.
 */

import { Activity, Gauge, AlertTriangle } from 'lucide-react';
import type { SimulationOutput } from '../../../../../types';
import { formatKrw } from '../../utils/formatters';

interface Props {
  simResult: SimulationOutput;
}

export function PredictSummaryTab({ simResult }: Props) {
  const ps = simResult.final_report?.profit_simulation ?? null;
  const monthlyRev = ps?.monthly_revenue ?? null;
  const bepMonths = ps?.bep_months ?? null;
  const riskScore = simResult.closure_risk?.risk_score ?? null;
  const riskPct =
    riskScore == null ? null : riskScore <= 1 ? Math.round(riskScore * 100) : Math.round(riskScore);

  return (
    <div className="grid grid-cols-3 gap-6">
      <Kpi
        icon={<Activity size={16} className="text-indigo-400" />}
        label="추정 월매출"
        value={monthlyRev != null ? `₩${formatKrw(monthlyRev)}` : '—'}
        color="indigo"
      />
      <Kpi
        icon={<Gauge size={16} className="text-cyan-400" />}
        label="BEP (개월)"
        value={bepMonths != null ? `${bepMonths.toFixed(1)}` : '—'}
        color="cyan"
      />
      <Kpi
        icon={<AlertTriangle size={16} className="text-rose-400" />}
        label="폐업위험도"
        value={riskPct != null ? `${riskPct}%` : '—'}
        color="rose"
      />
    </div>
  );
}

interface KpiProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  color: 'indigo' | 'cyan' | 'rose';
}

function Kpi({ icon, label, value, color }: KpiProps) {
  const valueClass =
    color === 'indigo' ? 'text-indigo-400' : color === 'cyan' ? 'text-cyan-400' : 'text-rose-400';
  return (
    <div className="rounded-3xl border border-stone-800/60 bg-stone-900/40 p-6">
      <div className="mb-3 flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-stone-500">
        {icon}
        <span>{label}</span>
      </div>
      <div className={`text-3xl font-black tabular-nums tracking-tighter ${valueClass}`}>
        {value}
      </div>
    </div>
  );
}
