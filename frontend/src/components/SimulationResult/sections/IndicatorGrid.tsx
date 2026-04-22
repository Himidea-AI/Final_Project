import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import type { SimulationOutput } from '../../../types';
import { SectionLabel } from '../shared/SectionLabel';
import { AgentCard } from '../shared/AgentCard';

interface Props {
  simResult: SimulationOutput;
}

const INDICATORS: Array<{ key: string; label: string; shortLabel: string }> = [
  { key: 'floating_population', label: '유동인구', shortLabel: '유동' },
  { key: 'rent_index', label: '임대료 지수', shortLabel: '임대' },
  { key: 'competition_intensity', label: '경쟁강도', shortLabel: '경쟁' },
  { key: 'estimated_revenue', label: '예상 매출', shortLabel: '매출' },
  { key: 'survival_rate', label: '생존율', shortLabel: '생존' },
  { key: 'growth_potential', label: '성장 잠재력', shortLabel: '성장' },
  { key: 'accessibility', label: '접근성', shortLabel: '접근' },
];

function scoreColor(v: number): string {
  if (v >= 70) return 'text-emerald-400';
  if (v >= 45) return 'text-amber-400';
  return 'text-rose-400';
}

function scoreBorder(v: number): string {
  if (v >= 70) return 'border-emerald-500/30';
  if (v >= 45) return 'border-amber-500/30';
  return 'border-rose-500/30';
}

function scoreBg(v: number): string {
  if (v >= 70) return 'bg-emerald-500/10';
  if (v >= 45) return 'bg-amber-500/10';
  return 'bg-rose-500/10';
}

export function IndicatorGrid({ simResult }: Props) {
  const report = simResult.market_report;
  const attrs = simResult.agent_attributions ?? [];
  const market = attrs.find((a) => a.id === 'market_analyst');
  const population = attrs.find((a) => a.id === 'population_analyst');
  const ranking = attrs.find((a) => a.id === 'district_ranking');

  if (!report) {
    return (
      <section>
        <SectionLabel label="INDICATOR GRID" subtitle="7 핵심 상권 지표" />
        <div className="rounded-lg border border-zinc-700 bg-zinc-800 p-6 text-center text-sm text-zinc-400">
          상권 지표 데이터 없음
        </div>
      </section>
    );
  }

  const values = INDICATORS.map(({ key, label, shortLabel }) => {
    const rawVal = (report as Record<string, unknown>)[key];
    const val = typeof rawVal === 'number' ? Math.max(0, Math.min(100, rawVal)) : 0;
    return { key, label, shortLabel, val };
  });

  const radarData = values.map(({ shortLabel, val }) => ({
    subject: shortLabel,
    value: val,
    fullMark: 100,
  }));

  return (
    <section>
      <SectionLabel label="INDICATOR GRID" subtitle="7 핵심 상권 지표" />

      <div className="grid gap-4 lg:grid-cols-[1fr_auto]">
        {/* KPI 카드 그리드 */}
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
          {values.map(({ key, label, val }) => (
            <div key={key} className={`rounded-lg border p-3 ${scoreBorder(val)} ${scoreBg(val)}`}>
              <div className="text-[10px] uppercase tracking-wider text-zinc-500">{label}</div>
              <div className={`mt-1 text-2xl font-bold font-mono ${scoreColor(val)}`}>
                {Math.round(val)}
              </div>
              <div className="mt-1.5 h-1 w-full rounded-full bg-zinc-700">
                <div
                  className={`h-full rounded-full ${val >= 70 ? 'bg-emerald-500' : val >= 45 ? 'bg-amber-500' : 'bg-rose-500'}`}
                  style={{ width: `${val}%` }}
                />
              </div>
              <div className="mt-1 text-[9px] text-zinc-600">/ 100</div>
            </div>
          ))}
        </div>

        {/* 레이더 차트 */}
        <div className="flex items-center justify-center rounded-lg border border-zinc-700 bg-zinc-800 p-4 lg:w-72">
          <ResponsiveContainer width="100%" height={220}>
            <RadarChart data={radarData} margin={{ top: 10, right: 20, bottom: 10, left: 20 }}>
              <PolarGrid stroke="#3f3f46" />
              <PolarAngleAxis
                dataKey="subject"
                tick={{ fill: '#a1a1aa', fontSize: 10, fontWeight: 600 }}
              />
              <Radar
                dataKey="value"
                stroke="#f59e0b"
                fill="#f59e0b"
                fillOpacity={0.15}
                strokeWidth={1.5}
              />
              <Tooltip
                contentStyle={{
                  background: 'rgba(24,24,27,0.95)',
                  border: '1px solid #3f3f46',
                  borderRadius: 6,
                  fontSize: 12,
                  color: '#e4e4e7',
                }}
                formatter={(v: number) => [Math.round(v), '점수']}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>

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
