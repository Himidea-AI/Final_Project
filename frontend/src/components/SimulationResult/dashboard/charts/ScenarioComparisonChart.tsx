/**
 * ScenarioComparisonChart — 4분기 매출 시뮬 (기준선 vs 시나리오).
 *
 * - baseline: 회색 점선
 * - adjusted: primary deep blue 실선
 * - Y축 자동 줌 — [min × 0.95, max × 1.05]
 * - tooltip ₩ + thousands separator
 */

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

interface Props {
  baseline: number[];
  adjusted: number[];
  quarterLabels?: string[];
  /** number(px) 또는 ResponsiveContainer 호환 string ("100%"). 부모 flex-1 안에서 fill 시 "100%". */
  height?: number | string;
}

const formatKRW = (value: number): string => {
  const abs = Math.abs(value);
  if (abs >= 100_000_000) return `${(value / 100_000_000).toFixed(1)}억`;
  if (abs >= 10_000) return `${Math.round(value / 10_000).toLocaleString('ko-KR')}만`;
  return `${Math.round(value).toLocaleString('ko-KR')}원`;
};

const formatTooltip = (value: number): string => `₩${Math.round(value).toLocaleString('ko-KR')}`;

export function ScenarioComparisonChart({
  baseline,
  adjusted,
  quarterLabels,
  height = 280,
}: Props) {
  const labels = quarterLabels ?? ['1분기', '2분기', '3분기', '4분기'];
  const len = Math.max(baseline.length, adjusted.length);
  const data = Array.from({ length: len }, (_, i) => ({
    quarter: labels[i] ?? `Q${i + 1}`,
    baseline: baseline[i] ?? null,
    adjusted: adjusted[i] ?? null,
  }));

  const all = [...baseline, ...adjusted].filter((v) => Number.isFinite(v));
  const dataMin = all.length > 0 ? Math.min(...all) : 0;
  const dataMax = all.length > 0 ? Math.max(...all) : 1;
  const yDomain: [number, number] =
    dataMin === dataMax
      ? [dataMin * 0.9 || 0, dataMax * 1.1 || 1]
      : [dataMin * 0.95, dataMax * 1.05];

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 12, right: 24, left: 12, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
        <XAxis
          dataKey="quarter"
          tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
          axisLine={{ stroke: 'var(--border)' }}
        />
        <YAxis
          tickFormatter={formatKRW}
          tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }}
          axisLine={{ stroke: 'var(--border)' }}
          domain={yDomain}
          width={70}
        />
        <Tooltip
          cursor={{ stroke: 'var(--border)', strokeDasharray: '3 3' }}
          contentStyle={{
            backgroundColor: 'var(--card)',
            border: '1px solid var(--border)',
            borderRadius: 8,
            fontSize: 12,
            color: 'var(--card-foreground)',
          }}
          formatter={(v: number, name: string) => [
            formatTooltip(v),
            name === 'baseline' ? '기준선' : '시나리오',
          ]}
        />
        <Legend
          wrapperStyle={{ fontSize: 11, color: 'var(--muted-foreground)' }}
          iconType="line"
          formatter={(v) => (v === 'baseline' ? '기준선' : '시나리오')}
        />
        <Line
          type="monotone"
          dataKey="baseline"
          stroke="var(--muted-foreground)"
          strokeWidth={2.5}
          strokeDasharray="4 4"
          dot={{ r: 3, fill: 'var(--muted-foreground)' }}
          name="baseline"
          isAnimationActive={false}
        />
        <Line
          type="monotone"
          dataKey="adjusted"
          stroke="var(--primary)"
          strokeWidth={2.5}
          dot={{ r: 3.5, fill: 'var(--primary)' }}
          activeDot={{ r: 5, fill: 'var(--primary)', stroke: 'var(--card)', strokeWidth: 2 }}
          name="adjusted"
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
