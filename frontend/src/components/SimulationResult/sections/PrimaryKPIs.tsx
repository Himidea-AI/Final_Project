import type { SimulationOutput } from '../../../types';
import { SectionLabel } from '../shared/SectionLabel';

interface Props {
  simResult: SimulationOutput;
}

const RENT_COLOR: Record<string, string> = {
  SAFE: 'text-emerald-400',
  CAUTION: 'text-yellow-400',
  DANGER: 'text-rose-400',
};

const GRADE_LABEL: Record<string, string> = {
  EXCELLENT: '최우수',
  GOOD: '우수',
  NORMAL: '보통',
  RISKY: '주의',
};

const DIRECTION_LABEL: Record<string, string> = {
  growth: '성장',
  stable: '유지',
  decline: '하락',
};

export function PrimaryKPIs({ simResult }: Props) {
  const firstQ = simResult.quarterly_projection?.[0]?.revenue ?? 0;
  const monthlyRevenue = Math.round(firstQ / 3);
  const grade = simResult.analysis_metrics?.district_grade ?? '—';

  const rent = simResult.analysis_metrics?.rent_affordability ?? '—';

  const competitionScore = simResult.analysis_metrics?.competition_score ?? 0;
  const competitionIntensity = simResult.market_report?.competition_intensity ?? competitionScore;
  const compIntel = simResult.competitor_intel as Record<string, any> | null | undefined;
  const saturationRaw = compIntel?.competition_500m?.saturation_level;
  const saturation = typeof saturationRaw === 'string' ? saturationRaw : '';

  const risks = simResult.legal_risks ?? [];
  const levelCounts = { safe: 0, caution: 0, danger: 0 };
  for (const r of risks) {
    const lvl = r.risk_level?.toUpperCase();
    if (lvl === 'LOW') levelCounts.safe++;
    else if (lvl === 'HIGH' || lvl === 'DANGER') levelCounts.danger++;
    else levelCounts.caution++;
  }

  const forecastScore = simResult.trend_forecast?.forecast?.score ?? 0;
  const forecastDir = simResult.trend_forecast?.forecast?.direction ?? 'unknown';

  return (
    <section>
      <SectionLabel label="PRIMARY KPIs" subtitle="5 대 핵심 지표 요약" />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <KpiCard
          label="예상 월매출"
          value={`${(monthlyRevenue / 10000).toLocaleString('ko-KR', { maximumFractionDigits: 0 })}만`}
          unit="원"
          badge={GRADE_LABEL[grade] ?? grade}
          badgeColor="text-amber-400"
        />
        <KpiCard
          label="임대료 적정성"
          value={rent}
          badge={rent === '—' ? '' : rent}
          badgeColor={RENT_COLOR[rent] ?? 'text-zinc-400'}
        />
        <KpiCard
          label="경쟁강도"
          value={`${Math.round(competitionIntensity)}/100`}
          badge={saturation}
          badgeColor="text-rose-400"
        />
        <LegalKpiCard levelCounts={levelCounts} />
        <KpiCard
          label="12개월 전망"
          value={`${Math.round(forecastScore)}/100`}
          badge={DIRECTION_LABEL[forecastDir] ?? ''}
          badgeColor="text-cyan-400"
        />
      </div>
    </section>
  );
}

interface KpiCardProps {
  label: string;
  value: string | number;
  unit?: string;
  badge?: string;
  badgeColor: string;
}

function KpiCard({ label, value, unit, badge, badgeColor }: KpiCardProps) {
  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-800 p-4">
      <div className="text-xs text-zinc-400">{label}</div>
      <div className="mt-2 flex items-baseline gap-1">
        <span className="text-2xl font-bold text-zinc-100">{value}</span>
        {unit && <span className="text-xs text-zinc-400">{unit}</span>}
      </div>
      {badge && <div className={`mt-2 text-xs font-semibold ${badgeColor}`}>{badge}</div>}
    </div>
  );
}

function LegalKpiCard({
  levelCounts,
}: {
  levelCounts: { safe: number; caution: number; danger: number };
}) {
  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-800 p-4">
      <div className="text-xs text-zinc-400">법률안전도</div>
      <div className="mt-3 flex items-center justify-between gap-2">
        <div className="flex flex-col items-center">
          <span className="text-2xl font-bold text-rose-400">{levelCounts.danger}</span>
          <span className="mt-1 text-[10px] text-rose-400/70">필수이행</span>
        </div>
        <div className="flex flex-col items-center">
          <span className="text-2xl font-bold text-yellow-400">{levelCounts.caution}</span>
          <span className="mt-1 text-[10px] text-yellow-400/70">확인필요</span>
        </div>
        <div className="flex flex-col items-center">
          <span className="text-2xl font-bold text-emerald-400">{levelCounts.safe}</span>
          <span className="mt-1 text-[10px] text-emerald-400/70">참고사항</span>
        </div>
      </div>
    </div>
  );
}
