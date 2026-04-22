import type { SimulationOutput } from '../../../types';
import { SectionLabel } from '../shared/SectionLabel';

interface Props {
  simResult: SimulationOutput;
}

const RISK_BADGE: Record<string, string> = {
  safe: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  caution: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30',
  danger: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
};

const RISK_LABEL: Record<string, string> = {
  safe: '안전',
  caution: '주의',
  danger: '위험',
};

function localizeTerms(text: string): string {
  return text
    .replace(/'caution'/gi, "'주의'").replace(/'safe'/gi, "'안전'").replace(/'danger'/gi, "'위험'")
    .replace(/\bcaution\b/gi, '주의').replace(/\bsafe\b/gi, '안전').replace(/\bdanger\b/gi, '위험')
    .replace(/\bsparse\b/gi, '희박').replace(/\bmedium\b/gi, '보통').replace(/\bhigh\b/gi, '높음')
    .replace(/\bsaturated\b/gi, '포화').replace(/\byellow\b/gi, '주의').replace(/\bgreen\b/gi, '양호')
    .replace(/\bred\b/gi, '위험').replace(/\bwarning\b/gi, '경고');
}

export function HeadlineBlock({ simResult }: Props) {
  const sim = simResult as SimulationOutput & Record<string, any>;

  const district = sim.winner_district ?? sim.target_district ?? '—';
  const rawRec: string = sim.ai_recommendation ?? sim.analysis_report ?? '';
  const recommendation = rawRec ? localizeTerms(rawRec) : '';
  const riskKey = (sim.overall_legal_risk ?? 'safe') as string;
  const riskCls = RISK_BADGE[riskKey] ?? RISK_BADGE.safe;
  const riskLabel = RISK_LABEL[riskKey] ?? riskKey;

  const compIntel = sim.competitor_intel as Record<string, any> | null | undefined;
  const compWithinRadius = compIntel?.competition_500m?.count ?? null;

  return (
    <section>
      <SectionLabel label="HEADLINE" subtitle="핵심 결론과 AI 권고" />
      <div className="rounded-lg border border-stone-700 bg-stone-800 p-6 space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="text-xs uppercase tracking-widest text-stone-500">추천 입지</div>
          <div className="text-2xl font-bold text-indigo-400">{district}</div>
          <span
            className={`ml-auto inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-bold ${riskCls}`}
          >
            ● {riskLabel}
          </span>
        </div>

        {recommendation && (
          <p className="text-sm leading-relaxed text-stone-200 whitespace-pre-line">
            {recommendation}
          </p>
        )}

        {compWithinRadius !== null && (
          <div className="flex flex-wrap gap-4 border-t border-stone-700 pt-3 text-xs text-stone-400">
            <div>
              500m 경쟁점 <span className="font-semibold text-stone-200">{compWithinRadius}개</span>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
