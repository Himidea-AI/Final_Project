/**
 * BepCumulativeProfitChart — 분기별 투자 회수 곡선 (다중 동)
 *
 * 데이터 소스: quarterly_projection[].cumulative_profit (동별)
 * - 각 동별 별도 Line (indigo / cyan / amber / rose)
 * - BEP 도달 시점(ReferenceLine): 첫 번째 동(series[0]) cumulative_profit ≥ 0 첫 분기
 * - y=0 ReferenceLine 으로 BEP 기준선 강조
 *
 * Round 2 / M6 (2026-04-29): 단일 동 → 다중 동 시리즈 전환.
 *   B4/M5 (QuarterlyProjectionChart) 패턴을 그대로 따름.
 */

import {
  LineChart,
  Line,
  Legend,
  XAxis,
  YAxis,
  ReferenceLine,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
} from 'recharts';
import type { QuarterlyProjection } from '../../../../types';

/** 동별 분기 누적이익 시리즈 1건 */
type ChartSeries = { district: string; projection: QuarterlyProjection[] };

interface Props {
  series: ChartSeries[];
  height?: number;
}

// indigo / cyan / amber / rose — QuarterlyProjectionChart 와 동일
const COLORS = ['#818cf8', '#22d3ee', '#fbbf24', '#fb7185'] as const;

const formatKRW = (value: number): string => {
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  if (abs >= 100_000_000) return `${sign}${(abs / 100_000_000).toFixed(1)}억`;
  if (abs >= 10_000) return `${sign}${Math.round(abs / 10_000).toLocaleString()}만`;
  return `${sign}${Math.round(abs).toLocaleString()}원`;
};

export function BepCumulativeProfitChart({ series, height = 240 }: Props) {
  // 빈 series / 모든 series projection 비어있음 → 안내 메시지
  const validSeries = (series ?? []).filter((s) => s.projection && s.projection.length > 0);
  if (validSeries.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-stone-800 bg-stone-950/40 p-6 text-center text-xs text-stone-500">
        투자 회수 데이터 없음
      </div>
    );
  }

  // 각 동의 첫 4분기만 + quarter 1~4 강제 라벨 (quarterly_projection 필드 보존)
  const trimmedSeries = validSeries.map((s) => ({
    district: s.district,
    data: s.projection.slice(0, 4).map((d, i) => ({ ...d, quarter: i + 1 })),
  }));

  // wide format: row = { quarter, [동]_cumulative, ... }
  const chartData = [1, 2, 3, 4].map((q) => {
    const row: Record<string, number | null> = { quarter: q };
    trimmedSeries.forEach((s) => {
      const point = s.data.find((p) => p.quarter === q);
      row[`${s.district}_cumulative`] = point?.cumulative_profit ?? null;
    });
    return row;
  });

  // BEP 기준 = series[0] cumulative_profit ≥ 0 첫 분기
  const bepQuarter =
    trimmedSeries[0]?.data.find((d) => (d.cumulative_profit ?? -1) >= 0)?.quarter ?? null;

  // mock 배지 — 임의 동에 mock 분기가 하나라도 있으면 표시
  const hasMockQuarters = trimmedSeries.some((s) => s.data.some((d) => d.is_mock === true));

  return (
    <div className="mt-3 rounded-lg border border-stone-800/60 bg-stone-950/40 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-[0.625rem] font-black uppercase tracking-widest text-stone-500 flex items-center gap-2">
          <span>분기별 투자 회수 곡선</span>
          <span className="text-[0.5625rem] font-bold text-stone-600 normal-case tracking-normal">
            cumulative_profit · BEP 도달 시점 강조 (기준: {trimmedSeries[0]?.district ?? '—'})
          </span>
          {hasMockQuarters && (
            <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[0.5625rem] font-bold normal-case tracking-normal text-amber-300">
              <span className="h-1 w-1 rounded-full bg-amber-400" />
              일부 분기 mock
            </span>
          )}
        </div>
        {bepQuarter !== null && (
          <span className="text-[0.625rem] font-black tabular-nums text-emerald-400">
            BEP Q{bepQuarter}
          </span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#292524" vertical={false} />
          <XAxis
            dataKey="quarter"
            tickFormatter={(q: number) => `Q${q}`}
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
            formatter={(value: number, name: string) => {
              // {동}_cumulative → "{동} 누적이익"
              if (typeof name === 'string' && name.endsWith('_cumulative')) {
                const district = name.replace(/_cumulative$/, '');
                return [formatKRW(value), `${district} 누적이익`];
              }
              return [formatKRW(value), name];
            }}
            labelFormatter={(q: number) => `${q}분기`}
          />
          <Legend
            verticalAlign="top"
            height={24}
            wrapperStyle={{ paddingBottom: 4, fontSize: 11 }}
            iconType="circle"
          />
          {/* y=0 기준선 — BEP 도달 시각화 */}
          <ReferenceLine y={0} stroke="#a8a29e" strokeDasharray="2 2" />

          {/* 동별 누적이익 라인 — 4 색상 순환 */}
          {trimmedSeries.map((s, idx) => (
            <Line
              key={s.district}
              type="monotone"
              dataKey={`${s.district}_cumulative`}
              name={s.district}
              stroke={COLORS[idx % COLORS.length]}
              strokeWidth={2}
              dot={{ r: 3 }}
              activeDot={{ r: 5, stroke: '#fff', strokeWidth: 1 }}
              isAnimationActive={false}
              connectNulls
            />
          ))}

          {/* BEP ReferenceLine — series[0] 기준 */}
          {bepQuarter !== null && (
            <ReferenceLine
              x={bepQuarter}
              stroke="#10b981"
              strokeDasharray="3 3"
              label={{ value: 'BEP', fill: '#10b981', fontSize: 11 }}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
