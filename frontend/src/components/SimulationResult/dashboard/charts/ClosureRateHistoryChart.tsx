/**
 * ClosureRateHistoryChart — 과거 12개월 폐업률 추이 LineChart
 *
 * 2026-04-27 추가: 사용자(강민) 지적 — 폐업률 시계열 차트가 아예 없었음.
 * 데이터 소스: closure_rate.monthly_closure_rates (B2 수지니, 예측 아님 실측 누적).
 *
 * 임계선:
 *   - safe   : 0.30 이하 (emerald)
 *   - caution: 0.30 ~ 0.60 (amber)
 *   - danger : 0.60 초과 (rose)
 */

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  ReferenceLine,
} from 'recharts';

interface Props {
  rates: number[] | undefined;
  height?: number;
}

interface Row {
  month: string;
  rate: number;
}

export function ClosureRateHistoryChart({ rates, height = 200 }: Props) {
  if (!rates || rates.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-stone-800 bg-stone-950/40 p-6 text-center text-xs text-stone-500">
        과거 12개월 폐업률 데이터 없음
      </div>
    );
  }

  const data: Row[] = rates.map((r, i) => ({
    month: `M${i + 1}`,
    rate: Number((r * 100).toFixed(2)),
  }));

  return (
    <div className="mt-3 rounded-lg border border-stone-800/60 bg-stone-950/40 p-4">
      <div className="text-[0.625rem] font-black uppercase tracking-widest text-stone-500 mb-3">
        과거 12개월 폐업률 추이
        <span className="ml-2 text-[0.5625rem] font-bold text-stone-600 normal-case tracking-normal">
          monthly_closure_rates · 실측 (예측 아님)
        </span>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#292524" vertical={false} />
          <XAxis
            dataKey="month"
            tick={{ fontSize: 10, fill: '#a8a29e' }}
            axisLine={{ stroke: '#44403c' }}
            interval={0}
          />
          <YAxis
            tick={{ fontSize: 10, fill: '#a8a29e' }}
            axisLine={{ stroke: '#44403c' }}
            tickFormatter={(v) => `${v}%`}
            domain={[0, (max: number) => Math.max(60, Math.ceil(max / 10) * 10)]}
          />
          <Tooltip
            cursor={{ stroke: '#44403c' }}
            contentStyle={{
              backgroundColor: '#1a1a1a',
              border: '1px solid #44403c',
              borderRadius: 8,
              fontSize: 12,
            }}
            formatter={(v: number) => [`${v.toFixed(2)}%`, '폐업률']}
          />
          <ReferenceLine
            y={30}
            stroke="#22c55e"
            strokeDasharray="3 3"
            label={{ value: 'safe 30%', position: 'right', fill: '#22c55e', fontSize: 9 }}
          />
          <ReferenceLine
            y={60}
            stroke="#ef4444"
            strokeDasharray="3 3"
            label={{ value: 'danger 60%', position: 'right', fill: '#ef4444', fontSize: 9 }}
          />
          <Line
            type="monotone"
            dataKey="rate"
            stroke="#a8a29e"
            strokeWidth={2}
            dot={{ r: 2, fill: '#a8a29e' }}
            activeDot={{ r: 4 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
