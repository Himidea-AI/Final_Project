/**
 * EmergingFourDongTrendChart — 4 동 8분기 변화도 시계열 비교 차트.
 *
 * 사용자 시나리오: 1~4동 선택해 들어온 후 emerging_district 탭에서 4동 비교.
 * 페이지 상단 풀와이드.
 *
 * 시각화:
 *   - 4 line (winner→4위 색, SERIES_COLORS) — quarter_history 8분기 시계열
 *   - winner stroke 3px / 나머지 2.5px (다른 탭 위계와 통일)
 *   - x축: Q-7 ~ 현재 (8분기)
 *   - y축: 0~1 anomaly_score
 *   - 16동 사분위 horizontal ReferenceLine 4개 (P25/P50/P75/P90) — peer_distribution 활용
 *   - tooltip: 분기별 4동 score 모두 표시
 *
 * peer_distribution null + 모든 동 quarter_history null → placeholder.
 */

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import type { DistrictPredictionResult } from '../../../../types';
import { SERIES_COLORS } from '../../QuarterlyProjectionChart';

interface Props {
  /** sortByRanking 으로 winner→4위 정렬된 4 동 */
  dpredicts: DistrictPredictionResult[];
  height?: number;
}

export function EmergingFourDongTrendChart({ dpredicts, height = 280 }: Props) {
  // 4동 중 quarter_history 가 있는 동만 시각화 대상
  const validSeries = dpredicts
    .map((p, idx) => ({
      district: p.district,
      history: p.emerging_signal?.quarter_history ?? null,
      color: SERIES_COLORS[idx % SERIES_COLORS.length]!,
      isWinner: idx === 0,
    }))
    .filter(
      (s): s is typeof s & { history: NonNullable<typeof s.history> } =>
        s.history != null && s.history.length > 0,
    );

  // peer_distribution — 4동 중 첫 동의 분포 (모두 동일 분포)
  const peer =
    dpredicts.find((p) => p.emerging_signal?.peer_distribution)?.emerging_signal
      ?.peer_distribution ?? null;

  if (validSeries.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-secondary p-6 text-center text-xs text-muted-foreground">
        4 동 시계열 데이터 미수신 — 잠시 후 다시 시도해주세요.
      </div>
    );
  }

  // wide format 변환: row = { quarter, [동]_score, ... }
  const quarterLabels =
    validSeries[0]?.history.map((h) => h.quarter) ??
    Array.from({ length: 8 }, (_, i) => (i === 7 ? '현재' : `Q-${7 - i}`));

  const chartData = quarterLabels.map((q, qIdx) => {
    const row: Record<string, string | number | null> = { quarter: q };
    for (const s of validSeries) {
      const point = s.history[qIdx];
      row[`${s.district}_score`] = point?.anomaly_score ?? null;
    }
    return row;
  });

  // Legend payload — 동별 라인 circle
  const legendPayload = validSeries.map((s) => ({
    value: s.district,
    type: 'circle' as const,
    color: s.color,
    id: `series-${s.district}`,
  }));

  // 사분위 reference line 정의 — peer 있을 때만
  const refLines: { y: number; label: string }[] = peer
    ? [
        { y: peer.p25, label: '16동 P25' },
        { y: peer.p50, label: '16동 P50' },
        { y: peer.p75, label: '16동 P75' },
        { y: peer.p90, label: '16동 P90' },
      ]
    : [];

  return (
    <div className="space-y-2">
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={chartData} margin={{ top: 8, right: 64, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="quarter"
            tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }}
            axisLine={{ stroke: 'var(--border)' }}
          />
          <YAxis
            domain={[0, 1]}
            ticks={[0, 0.25, 0.5, 0.75, 1]}
            tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
            tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }}
            axisLine={{ stroke: 'var(--border)' }}
            width={40}
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
            formatter={(value: number, name: string) => {
              if (typeof name === 'string' && name.endsWith('_score')) {
                const district = name.replace(/_score$/, '');
                return [value != null ? `${(value * 100).toFixed(0)}%` : '—', `${district} 변화도`];
              }
              return [`${(value * 100).toFixed(0)}%`, name];
            }}
            labelFormatter={(q: string) => q}
          />
          <Legend
            verticalAlign="bottom"
            height={28}
            wrapperStyle={{ paddingTop: 8, fontSize: 11 }}
            iconType="circle"
            payload={legendPayload}
          />

          {/* 16 동 사분위 reference line — y 축 옆 작은 라벨 */}
          {refLines.map((r) => (
            <ReferenceLine
              key={r.label}
              y={r.y}
              stroke="var(--muted-foreground)"
              strokeDasharray="3 3"
              strokeOpacity={0.4}
              label={{
                value: r.label,
                position: 'right',
                fill: 'var(--muted-foreground)',
                fontSize: 9,
              }}
            />
          ))}

          {/* 4 동 line — winner stroke 3px, 나머지 2.5px */}
          {validSeries.map((s) => (
            <Line
              key={s.district}
              type="monotone"
              dataKey={`${s.district}_score`}
              name={s.district}
              stroke={s.color}
              strokeWidth={s.isWinner ? 3 : 2.5}
              dot={{ r: s.isWinner ? 5 : 4 }}
              activeDot={{ r: 6, stroke: 'var(--card)', strokeWidth: 1 }}
              isAnimationActive={false}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
