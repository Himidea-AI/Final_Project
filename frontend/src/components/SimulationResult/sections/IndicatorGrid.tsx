import type { SimulationOutput } from '../../../types';
import { SectionLabel } from '../shared/SectionLabel';
import { AgentCard } from '../shared/AgentCard';

interface Props {
  simResult: SimulationOutput;
}

const INDICATORS: Array<{ key: string; label: string; color: string }> = [
  { key: 'floating_population', label: '유동인구', color: 'bg-sky-500' },
  { key: 'rent_index', label: '임대료 지수', color: 'bg-indigo-500' },
  { key: 'competition_intensity', label: '경쟁강도', color: 'bg-rose-500' },
  { key: 'estimated_revenue', label: '예상 매출', color: 'bg-emerald-500' },
  { key: 'survival_rate', label: '생존율', color: 'bg-violet-500' },
  { key: 'growth_potential', label: '성장 잠재력', color: 'bg-cyan-500' },
  { key: 'accessibility', label: '접근성', color: 'bg-blue-500' },
];

export function IndicatorGrid({ simResult }: Props) {
  const report = simResult.market_report;
  const attrs = simResult.agent_attributions ?? [];
  const market = attrs.find((a) => a.id === 'market_analyst');
  const population = attrs.find((a) => a.id === 'population_analyst');
  const ranking = attrs.find((a) => a.id === 'district_ranking');

  return (
    <section>
      <SectionLabel label="INDICATOR GRID" subtitle="7 핵심 상권 지표" />

      {!report ? (
        <div className="rounded-lg border border-stone-700 bg-stone-800 p-6 text-center text-sm text-stone-400">
          상권 지표 데이터 없음
        </div>
      ) : (
        <div className="rounded-lg border border-stone-700 bg-stone-800 p-6">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {INDICATORS.map(({ key, label, color }) => {
              const rawVal = (report as Record<string, unknown>)[key];
              const isMissing = typeof rawVal !== 'number' || rawVal === 0;
              const val = typeof rawVal === 'number' ? rawVal : 0;
              const clamped = Math.max(0, Math.min(100, val));
              return (
                <div key={key} className="flex items-center gap-3">
                  <div className="w-24 shrink-0 text-xs text-stone-400 flex items-center gap-1">
                    {label}
                    {isMissing && (
                      <span
                        title="데이터 수집 중 — 백엔드 pipeline에서 해당 지표가 0/누락"
                        className="text-amber-500 text-[10px] font-mono"
                      >
                        ⚠
                      </span>
                    )}
                  </div>
                  <div className="relative flex-1 overflow-hidden rounded-full bg-stone-900 h-2">
                    {isMissing ? (
                      <div className="absolute left-0 top-0 h-full w-full border border-dashed border-stone-700 rounded-full" />
                    ) : (
                      <div
                        className={`absolute left-0 top-0 h-full rounded-full ${color}`}
                        style={{ width: `${clamped}%` }}
                      />
                    )}
                  </div>
                  <div
                    className={`w-10 shrink-0 text-right font-mono text-xs ${isMissing ? 'text-stone-500' : 'text-stone-100'}`}
                  >
                    {isMissing ? '—' : Math.round(clamped)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {(market || population || ranking) && (
        <div className="mt-3 grid gap-2 md:grid-cols-3">
          {market && <AgentCard attribution={market} size="compact" />}
          {population && <AgentCard attribution={population} size="compact" />}
          {ranking && <AgentCard attribution={ranking} size="compact" />}
        </div>
      )}
    </section>
  );
}
