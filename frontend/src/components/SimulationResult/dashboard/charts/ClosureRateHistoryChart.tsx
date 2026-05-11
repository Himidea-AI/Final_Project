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
  /** 동별 자동 매핑 색 — SERIES_COLORS[idx] 그대로 전달. 미지정 시 muted-foreground (legacy). */
  color?: string;
}

interface Row {
  month: string;
  rate: number;
}

export function ClosureRateHistoryChart({ rates, height = 200, color }: Props) {
  const lineColor = color ?? 'var(--muted-foreground)';
  if (!rates || rates.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-secondary p-6 text-center text-xs text-muted-foreground">
        과거 12개월 폐업률 데이터 없음
      </div>
    );
  }

  const data: Row[] = rates.map((r, i) => ({
    month: `${i + 1}분기`,
    rate: Number((r * 100).toFixed(2)),
  }));

  // Y축 auto-zoom — 실제 값 범위 기준 [min - pad, max + pad]. min === max 이면 [0, max * 1.5].
  const rateValues = data.map((d) => d.rate);
  const dataMin = Math.min(...rateValues);
  const dataMax = Math.max(...rateValues);
  const yDomain: [number, number] =
    dataMin === dataMax
      ? [0, dataMax * 1.5 || 1]
      : [
          Math.max(0, dataMin - Math.max((dataMax - dataMin) * 0.15, 1)),
          dataMax + Math.max((dataMax - dataMin) * 0.15, 1),
        ];

  return (
    <div className="mt-3 rounded-lg border border-border bg-secondary p-4">
      <div className="text-[0.625rem] font-black uppercase tracking-widest text-muted-foreground mb-3">
        최근 4분기 폐업률 추이
        <span className="ml-2 text-[0.5625rem] font-bold text-muted-foreground normal-case tracking-normal">
          분기별 실측값 (예측 아님)
        </span>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="month"
            tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }}
            axisLine={{ stroke: 'var(--border)' }}
            interval={0}
          />
          <YAxis
            tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }}
            axisLine={{ stroke: 'var(--border)' }}
            tickFormatter={(v: number) => `${v.toFixed(1)}%`}
            domain={yDomain}
          />
          <Tooltip
            cursor={{ stroke: 'var(--border)' }}
            contentStyle={{
              backgroundColor: 'var(--card)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              fontSize: 12,
              color: 'var(--card-foreground)',
            }}
            formatter={(v: number) => [`${v.toFixed(2)}%`, '폐업률']}
          />
          <ReferenceLine
            y={30}
            stroke="var(--success)"
            strokeDasharray="3 3"
            label={{ value: 'safe 30%', position: 'right', fill: 'var(--success)', fontSize: 9 }}
          />
          <ReferenceLine
            y={60}
            stroke="var(--danger)"
            strokeDasharray="3 3"
            label={{ value: 'danger 60%', position: 'right', fill: 'var(--danger)', fontSize: 9 }}
          />
          <Line
            type="monotone"
            dataKey="rate"
            stroke={lineColor}
            strokeWidth={2}
            dot={{ r: 2, fill: lineColor }}
            activeDot={{ r: 4 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
      <p className="mt-2 text-[0.625rem] text-muted-foreground">
        Y축 자동 줌 — 실제 값 범위에 맞춤
      </p>
    </div>
  );
}
