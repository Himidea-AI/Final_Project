/**
 * PredictSummaryTab — 예측 그룹 요약 (ML 숫자 카드만)
 * 2026-04-28 IA 재구조 — SummaryTab 의 ProfitSimulationPanelFull 의 일부 분해.
 * computeDecision 등 LLM 의존은 AnalyzeAiSummaryTab 에 이관.
 *
 * H5 (2026-04-28): 3 KPI → 5 KPI 확장
 *   + 유동인구 점수 (emerald)  ← market_report.floating_population (0~100)
 *   + 경쟁 강도 등급 (amber)   ← competitor_intel.competition_500m.saturation_level
 *     (sparse/low/medium/high/saturated → SATURATION_MAP)
 *   ※ 스펙의 demographic_depth.flpop_score / competitor_intel.competitor_intensity
 *     필드는 실제 백엔드 타입(SimulationOutput / CompetitorIntel / DemographicReport)
 *     에 존재하지 않아, 가장 가까운 채워지는 필드로 대체.
 */

import { Activity, Gauge, AlertTriangle, Users, Swords } from 'lucide-react';
import type { SimulationOutput } from '../../../../../types';
import { formatKrw } from '../../utils/formatters';
import { SATURATION_MAP, safeMap } from '../../utils/mappings';

interface Props {
  simResult: SimulationOutput;
}

type KpiColor = 'indigo' | 'cyan' | 'rose' | 'emerald' | 'amber';

export function PredictSummaryTab({ simResult }: Props) {
  const ps = simResult.final_report?.profit_simulation ?? null;
  const monthlyRev = ps?.monthly_revenue ?? null;
  const bepMonths = ps?.bep_months ?? null;
  const riskScore = simResult.closure_risk?.risk_score ?? null;
  const riskPct =
    riskScore == null ? null : riskScore <= 1 ? Math.round(riskScore * 100) : Math.round(riskScore);

  // 유동인구 점수 (0~100) — market_report.floating_population
  const flpopScore = simResult.market_report?.floating_population ?? null;

  // 경쟁 강도 등급 — competitor_intel.competition_500m.saturation_level
  // (sparse/low/medium/high/saturated). 라벨은 SATURATION_MAP 으로 한글화.
  const saturationRaw = simResult.competitor_intel?.competition_500m?.saturation_level ?? null;
  const competitorGradeLabel = saturationRaw
    ? safeMap(SATURATION_MAP, saturationRaw, SATURATION_MAP.medium)
    : null;

  return (
    <div className="grid grid-cols-2 gap-6 md:grid-cols-3 lg:grid-cols-5">
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
      <Kpi
        icon={<Users size={16} className="text-emerald-400" />}
        label="유동인구 점수"
        value={flpopScore != null ? `${Math.round(flpopScore)}` : '—'}
        color="emerald"
      />
      <Kpi
        icon={<Swords size={16} className="text-amber-400" />}
        label="경쟁 강도"
        value={competitorGradeLabel ?? '—'}
        color="amber"
      />
    </div>
  );
}

interface KpiProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  color: KpiColor;
}

const VALUE_CLASS: Record<KpiColor, string> = {
  indigo: 'text-indigo-400',
  cyan: 'text-cyan-400',
  rose: 'text-rose-400',
  emerald: 'text-emerald-400',
  amber: 'text-amber-400',
};

function Kpi({ icon, label, value, color }: KpiProps) {
  const valueClass = VALUE_CLASS[color];
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
