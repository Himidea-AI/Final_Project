import type { SimulationOutput } from '../../../types';
import { SectionLabel } from '../shared/SectionLabel';

interface Props {
  simResult: SimulationOutput;
}

const LEGAL_LABEL: Record<string, string> = {
  safe: '안전',
  caution: '주의',
  danger: '위험',
};

const LEGAL_COLOR: Record<string, string> = {
  safe: 'text-emerald-400',
  caution: 'text-yellow-400',
  danger: 'text-rose-400',
};

// 14개 법률을 의무/권고/참고로 분류
const LEGAL_CATEGORY: Record<string, '의무' | '권고' | '참고'> = {
  franchise_law: '의무',
  food_hygiene: '의무',
  commercial_lease_law: '의무',
  building_law: '의무',
  fire_safety_law: '의무',
  labor_law: '의무',
  ftc_franchise: '의무',
  zoning_regulation: '권고',
  safety_regulation: '권고',
  vat_law: '권고',
  privacy_law: '권고',
  accessibility_law: '참고',
  sewage_law: '참고',
  fair_trade_law: '참고',
};

function countLegalByCategory(risks: { type: string; risk_level: string }[]) {
  const cats = {
    의무: { total: 0, danger: 0 },
    권고: { total: 0, danger: 0 },
    참고: { total: 0, danger: 0 },
  };
  for (const r of risks) {
    const cat = LEGAL_CATEGORY[r.type] ?? '참고';
    cats[cat].total++;
    const lvl = r.risk_level?.toUpperCase();
    if (lvl === 'HIGH' || lvl === 'DANGER') cats[cat].danger++;
  }
  return cats;
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

  const legal = simResult.overall_legal_risk ?? 'unknown';
  const legalCats = countLegalByCategory(simResult.legal_risks ?? []);
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
          badgeColor="text-indigo-400"
        />
        <KpiCard
          label="임대료 적정성"
          value={rent}
          badge={rent === '—' ? '' : rent}
          badgeColor={RENT_COLOR[rent] ?? 'text-stone-400'}
        />
        <KpiCard
          label="경쟁강도"
          value={`${Math.round(competitionIntensity)}/100`}
          badge={saturation}
          badgeColor="text-rose-400"
        />
        <LegalKpiCard legal={legal} cats={legalCats} levelCounts={levelCounts} />
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
    <div className="rounded-lg border border-stone-700 bg-stone-800 p-4">
      <div className="text-xs text-stone-400">{label}</div>
      <div className="mt-2 flex items-baseline gap-1">
        <span className="text-2xl font-bold text-stone-100">{value}</span>
        {unit && <span className="text-xs text-stone-400">{unit}</span>}
      </div>
      {badge && <div className={`mt-2 text-xs font-semibold ${badgeColor}`}>{badge}</div>}
    </div>
  );
}

function LegalKpiCard({
  legal,
  levelCounts,
}: {
  legal: string;
  cats: Record<'의무' | '권고' | '참고', { total: number; danger: number }>;
  levelCounts: { safe: number; caution: number; danger: number };
}) {
  return (
    <div className="rounded-lg border border-stone-700 bg-stone-800 p-4">
      <div className="text-xs text-stone-400">법률안전도</div>
      <div className="mt-2 flex items-baseline gap-1">
        <span className={`text-2xl font-bold ${LEGAL_COLOR[legal] ?? 'text-stone-100'}`}>
          {LEGAL_LABEL[legal] ?? legal.toUpperCase()}
        </span>
      </div>
      <div className="mt-2 flex gap-2 text-[11px]">
        <span className="text-emerald-400">안전 {levelCounts.safe}</span>
        <span className="text-yellow-400">주의 {levelCounts.caution}</span>
        <span className="text-rose-400">위험 {levelCounts.danger}</span>
      </div>
    </div>
  );
}
