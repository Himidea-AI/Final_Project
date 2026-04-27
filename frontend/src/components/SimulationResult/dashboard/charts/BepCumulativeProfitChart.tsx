/**
 * BepCumulativeProfitChart — 분기별 투자 회수 곡선
 *
 * 데이터 소스: quarterly_projection[].cumulative_profit
 * - 음수(투자 미회수)는 rose, 양수(회수 후)는 emerald 영역
 * - y=0 ReferenceLine 으로 BEP 도달점 강조
 * - 매출 ComposedChart와 분리하여 scale 충돌 방지
 */

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  ReferenceLine,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
} from 'recharts';
import type { QuarterlyProjection } from '../../../../types';

interface Props {
  data: QuarterlyProjection[];
  height?: number;
}

const formatKRW = (value: number): string => {
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  if (abs >= 100_000_000) return `${sign}${(abs / 100_000_000).toFixed(1)}억`;
  if (abs >= 10_000) return `${sign}${Math.round(abs / 10_000).toLocaleString()}만`;
  return `${sign}${Math.round(abs).toLocaleString()}원`;
};

export function BepCumulativeProfitChart({ data, height = 200 }: Props) {
  if (!data || data.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-stone-800 bg-stone-950/40 p-6 text-center text-xs text-stone-500">
        투자 회수 데이터 없음
      </div>
    );
  }

  const rows = data.map((d) => ({
    quarter: `Q${d.quarter}`,
    cumulative: d.cumulative_profit,
    positive: d.cumulative_profit >= 0 ? d.cumulative_profit : 0,
    negative: d.cumulative_profit < 0 ? d.cumulative_profit : 0,
    is_mock: d.is_mock === true,
  }));

  const bep = data.find((d) => d.cumulative_profit >= 0);
  // Critical #2 — 일부 분기 is_mock 시 헤더 배지로 인지 보강
  const hasMockQuarters = data.some((d) => d.is_mock === true);

  return (
    <div className="mt-3 rounded-lg border border-stone-800/60 bg-stone-950/40 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-[10px] font-black uppercase tracking-widest text-stone-500 flex items-center gap-2">
          <span>분기별 투자 회수 곡선</span>
          <span className="text-[9px] font-bold text-stone-600 normal-case tracking-normal">
            cumulative_profit · BEP 도달 시점 강조
          </span>
          {hasMockQuarters && (
            <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[9px] font-bold normal-case tracking-normal text-amber-300">
              <span className="h-1 w-1 rounded-full bg-amber-400" />
              일부 분기 mock
            </span>
          )}
        </div>
        {bep && (
          <span className="text-[10px] font-black tabular-nums text-emerald-400">
            BEP Q{bep.quarter}
          </span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={rows} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="cum-pos" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#22c55e" stopOpacity={0.5} />
              <stop offset="100%" stopColor="#22c55e" stopOpacity={0.05} />
            </linearGradient>
            <linearGradient id="cum-neg" x1="0" y1="1" x2="0" y2="0">
              <stop offset="0%" stopColor="#ef4444" stopOpacity={0.5} />
              <stop offset="100%" stopColor="#ef4444" stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#292524" vertical={false} />
          <XAxis
            dataKey="quarter"
            tick={{ fontSize: 10, fill: '#a8a29e' }}
            axisLine={{ stroke: '#44403c' }}
          />
          <YAxis
            tickFormatter={formatKRW}
            tick={{ fontSize: 10, fill: '#a8a29e' }}
            axisLine={{ stroke: '#44403c' }}
            width={60}
          />
          <Tooltip
            cursor={{ stroke: '#44403c' }}
            contentStyle={{
              backgroundColor: '#1a1a1a',
              border: '1px solid #44403c',
              borderRadius: 8,
              fontSize: 12,
            }}
            formatter={(v: number) => [formatKRW(v), '누적이익']}
          />
          <ReferenceLine y={0} stroke="#a8a29e" strokeDasharray="2 2" />
          <Area
            type="monotone"
            dataKey="positive"
            stroke="#22c55e"
            strokeWidth={2}
            fill="url(#cum-pos)"
            isAnimationActive={false}
            // is_mock 분기에는 amber dot + opacity 0.4
            dot={(props: {
              cx?: number;
              cy?: number;
              payload?: { is_mock?: boolean };
              index?: number;
            }) => {
              const { cx, cy, payload, index } = props;
              if (cx == null || cy == null || !payload?.is_mock) {
                return <g key={`bep-pos-dot-${index ?? 0}`} />;
              }
              return (
                <circle
                  key={`bep-pos-dot-${index ?? 0}`}
                  cx={cx}
                  cy={cy}
                  r={3}
                  fill="#f59e0b"
                  fillOpacity={0.4}
                />
              );
            }}
          />
          <Area
            type="monotone"
            dataKey="negative"
            stroke="#ef4444"
            strokeWidth={2}
            fill="url(#cum-neg)"
            isAnimationActive={false}
            dot={(props: {
              cx?: number;
              cy?: number;
              payload?: { is_mock?: boolean };
              index?: number;
            }) => {
              const { cx, cy, payload, index } = props;
              if (cx == null || cy == null || !payload?.is_mock) {
                return <g key={`bep-neg-dot-${index ?? 0}`} />;
              }
              return (
                <circle
                  key={`bep-neg-dot-${index ?? 0}`}
                  cx={cx}
                  cy={cy}
                  r={3}
                  fill="#f59e0b"
                  fillOpacity={0.4}
                />
              );
            }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
