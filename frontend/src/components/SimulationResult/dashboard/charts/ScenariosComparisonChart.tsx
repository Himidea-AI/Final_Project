/**
 * ScenariosComparisonChart — 낙관/기본/비관 시나리오 비교
 *
 * 데이터 소스: scenarios.{optimistic, base, pessimistic} (각 [{quarter, revenue}])
 * 시각: ComposedChart
 *  - Range Area: 낙관~비관 envelope (indigo translucent)
 *  - 3개 Line: optimistic(emerald 얇게), base(indigo 굵게), pessimistic(rose 얇게)
 * Best practice: 기본 시나리오 강조 + 신뢰 envelope 동시 표현
 */

import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  ResponsiveContainer,
} from 'recharts';

interface ScenarioPoint {
  quarter: number;
  revenue: number;
}

interface Props {
  scenarios:
    | {
        optimistic?: ScenarioPoint[];
        base?: ScenarioPoint[];
        pessimistic?: ScenarioPoint[];
      }
    | null
    | undefined;
  height?: number;
}

const formatKRW = (value: number): string => {
  const abs = Math.abs(value);
  if (abs >= 100_000_000) return `${(value / 100_000_000).toFixed(1)}억`;
  if (abs >= 10_000) return `${Math.round(value / 10_000).toLocaleString()}만`;
  return `${Math.round(value).toLocaleString()}원`;
};

export function ScenariosComparisonChart({ scenarios, height = 240 }: Props) {
  if (!scenarios || !scenarios.base || scenarios.base.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-stone-800 bg-stone-950/40 p-8 text-center text-xs text-stone-500">
        시나리오 데이터 없음
      </div>
    );
  }

  const base = scenarios.base ?? [];
  const opt = scenarios.optimistic ?? [];
  const pess = scenarios.pessimistic ?? [];

  // 모든 시나리오를 quarter 기준으로 join
  const quarters = base.map((b) => b.quarter);
  const merged = quarters.map((q) => ({
    quarter: `Q${q}`,
    base: base.find((d) => d.quarter === q)?.revenue ?? null,
    optimistic: opt.find((d) => d.quarter === q)?.revenue ?? null,
    pessimistic: pess.find((d) => d.quarter === q)?.revenue ?? null,
    rangeMin: pess.find((d) => d.quarter === q)?.revenue ?? null,
    rangeMax: opt.find((d) => d.quarter === q)?.revenue ?? null,
  }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={merged} margin={{ top: 12, right: 20, left: 10, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#292524" vertical={false} />
        <XAxis
          dataKey="quarter"
          tick={{ fontSize: 11, fill: '#a8a29e' }}
          axisLine={{ stroke: '#44403c' }}
        />
        <YAxis
          tickFormatter={formatKRW}
          tick={{ fontSize: 10, fill: '#a8a29e' }}
          axisLine={{ stroke: '#44403c' }}
          width={70}
        />
        <Tooltip
          cursor={{ stroke: '#44403c', strokeDasharray: '3 3' }}
          contentStyle={{
            backgroundColor: '#1a1a1a',
            border: '1px solid #44403c',
            borderRadius: 8,
            fontSize: 12,
          }}
          formatter={(v: number, name: string) => {
            const labels: Record<string, string> = {
              base: '기본',
              optimistic: '낙관',
              pessimistic: '비관',
              rangeMin: '비관(범위)',
              rangeMax: '낙관(범위)',
            };
            return [formatKRW(v), labels[name] ?? name];
          }}
        />
        <Legend
          wrapperStyle={{ fontSize: 10, color: '#a8a29e' }}
          iconType="circle"
          formatter={(v) =>
            v === 'optimistic'
              ? '낙관'
              : v === 'base'
                ? '기본 (P50)'
                : v === 'pessimistic'
                  ? '비관'
                  : v
          }
        />
        {/* Envelope (낙관-비관) */}
        <Area
          type="monotone"
          dataKey="rangeMax"
          stroke="none"
          fill="#818cf8"
          fillOpacity={0.08}
          isAnimationActive={false}
          legendType="none"
          name="rangeMax"
        />
        <Area
          type="monotone"
          dataKey="rangeMin"
          stroke="none"
          fill="#0a0a0a"
          fillOpacity={1}
          isAnimationActive={false}
          legendType="none"
          name="rangeMin"
        />
        {/* 낙관 */}
        <Line
          type="monotone"
          dataKey="optimistic"
          stroke="#22c55e"
          strokeWidth={1.5}
          strokeDasharray="4 3"
          dot={{ r: 2, fill: '#22c55e' }}
          isAnimationActive={false}
        />
        {/* 기본 (강조) */}
        <Line
          type="monotone"
          dataKey="base"
          stroke="#818cf8"
          strokeWidth={2.5}
          dot={{ r: 3.5, fill: '#818cf8' }}
          activeDot={{ r: 5, fill: '#818cf8', stroke: '#fff', strokeWidth: 2 }}
          isAnimationActive={false}
        />
        {/* 비관 */}
        <Line
          type="monotone"
          dataKey="pessimistic"
          stroke="#ef4444"
          strokeWidth={1.5}
          strokeDasharray="4 3"
          dot={{ r: 2, fill: '#ef4444' }}
          isAnimationActive={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
