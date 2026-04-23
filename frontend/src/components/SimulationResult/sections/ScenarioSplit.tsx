import type { SimulationOutput } from '../../../types';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { SectionLabel } from '../shared/SectionLabel';
import { AgentCard } from '../shared/AgentCard';

interface Props {
  simResult: SimulationOutput;
}

function fmtWan(v: number | null | undefined): string {
  if (v == null) return '—';
  return `${Math.round(v / 10000).toLocaleString()}만원`;
}

export function ScenarioSplit({ simResult }: Props) {
  const sc = simResult.scenarios;
  const synthesis = simResult.agent_attributions?.find((a) => a.id === 'synthesis');

  if (!sc) {
    return (
      <section>
        <SectionLabel label="SCENARIOS" subtitle="낙관 / 기본 / 비관 분기 매출 시나리오" />
        <div className="rounded-lg border border-stone-700 bg-stone-800 p-6 text-center text-sm text-stone-400">
          시나리오 분석 데이터가 없습니다
        </div>
      </section>
    );
  }

  const base = sc.base ?? [];
  const chartData = base.map((b, i) => ({
    quarter: `Q${b.quarter}`,
    optimistic: sc.optimistic?.[i]?.revenue ?? b.revenue,
    base: b.revenue,
    pessimistic: sc.pessimistic?.[i]?.revenue ?? b.revenue,
  }));

  const lastBase = base[base.length - 1]?.revenue ?? null;
  const lastOpt = sc.optimistic?.[base.length - 1]?.revenue ?? null;
  const lastPess = sc.pessimistic?.[base.length - 1]?.revenue ?? null;

  const CARDS = [
    {
      label: '낙관',
      value: lastOpt,
      color: 'text-emerald-400',
      border: 'border-emerald-500/30',
      bg: 'bg-emerald-500/10',
    },
    {
      label: '기본',
      value: lastBase,
      color: 'text-amber-400',
      border: 'border-amber-500/30',
      bg: 'bg-amber-500/10',
    },
    {
      label: '비관',
      value: lastPess,
      color: 'text-rose-400',
      border: 'border-rose-500/30',
      bg: 'bg-rose-500/10',
    },
  ];

  return (
    <section>
      <SectionLabel label="SCENARIOS" subtitle="낙관 / 기본 / 비관 분기 매출 시나리오" />

      {/* 시나리오별 최종 분기 매출 요약 카드 */}
      <div className="mb-4 grid grid-cols-3 gap-3">
        {CARDS.map(({ label, value, color, border, bg }) => (
          <div key={label} className={`rounded-lg border p-4 ${border} ${bg}`}>
            <div className="text-[10px] uppercase tracking-widest text-stone-500">
              {label} 시나리오
            </div>
            <div className={`mt-1 text-xl font-bold font-mono ${color}`}>{fmtWan(value)}</div>
            <div className="mt-0.5 text-[10px] text-stone-600">최종 분기 기준</div>
          </div>
        ))}
      </div>

      {/* 분기별 범위 영역 차트 */}
      <div className="rounded-lg border border-stone-700 bg-stone-800 p-4">
        <ResponsiveContainer width="100%" height={260}>
          <AreaChart data={chartData} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="rangeGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#f59e0b" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" />
            <XAxis dataKey="quarter" stroke="#71717a" fontSize={11} />
            <YAxis
              stroke="#71717a"
              fontSize={11}
              tickFormatter={(v: number) => `${Math.round(v / 10000)}만`}
              width={52}
            />
            <Tooltip
              contentStyle={{
                background: 'rgba(24,24,27,0.95)',
                border: '1px solid #3f3f46',
                borderRadius: 6,
                fontSize: 12,
                color: '#e4e4e7',
              }}
              formatter={(v: number, name: string) => [fmtWan(v), name]}
              labelStyle={{ color: '#a1a1aa', marginBottom: 4 }}
            />
            {/* 낙관-비관 범위 면적 */}
            <Area
              type="monotone"
              dataKey="optimistic"
              stroke="#10b981"
              strokeWidth={1.5}
              strokeDasharray="4 2"
              fill="url(#rangeGrad)"
              fillOpacity={1}
              name="낙관"
              dot={false}
            />
            <Area
              type="monotone"
              dataKey="pessimistic"
              stroke="#ef4444"
              strokeWidth={1.5}
              strokeDasharray="4 2"
              fill="#18181b"
              fillOpacity={1}
              name="비관"
              dot={false}
            />
            {/* 기본 라인 */}
            <Area
              type="monotone"
              dataKey="base"
              stroke="#f59e0b"
              strokeWidth={2.5}
              fill="none"
              name="기본"
              dot={{ fill: '#f59e0b', r: 3 }}
            />
            {lastBase != null && (
              <ReferenceLine
                y={lastBase}
                stroke="#f59e0b"
                strokeOpacity={0.2}
                strokeDasharray="2 4"
              />
            )}
          </AreaChart>
        </ResponsiveContainer>
        <div className="mt-2 flex gap-4 justify-end text-[11px] text-zinc-500">
          <span className="flex items-center gap-1">
            <span className="inline-block w-4 border-t-2 border-emerald-500 border-dashed" /> 낙관
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-4 border-t-2 border-amber-500" /> 기본
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-4 border-t-2 border-rose-500 border-dashed" /> 비관
          </span>
        </div>
      </div>

      {synthesis && (
        <div className="mt-3">
          <AgentCard attribution={synthesis} size="compact" />
        </div>
      )}
    </section>
  );
}
