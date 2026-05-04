/**
 * CustomerFlowPeakHourChart — 4동 통합 24시간 유동인구 grouped bar
 *
 * 입력: dpredicts (DistrictPredictionResult[]) — 4동 모두, is_excluded_combo 제외 후
 * 각 동의 living_pop_forecast.quarters[0].all_hours 24시간대 인구를 시간 기준 grouped bar 로 표시.
 *
 * 색: SERIES_COLORS (QuarterlyProjectionChart export) — 12색 팔레트 SoT 준수.
 * 빈 데이터 (모든 동에서 living_pop_forecast 가 null) → PlaceholderPanel.
 *
 * Layout: BarChart (vertical bar — X축=시간, Y축=인구). 4동 각각 1개 dataKey 로 grouped.
 */

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import type { DistrictPredictionResult, LivingPopForecast } from '../../../../types';
import { SERIES_COLORS } from '../../QuarterlyProjectionChart';
import { PlaceholderPanel } from '../shared/PlaceholderPanel';

interface Props {
  dpredicts: DistrictPredictionResult[];
}

function formatPop(pop: number): string {
  if (pop >= 10000) return `${(pop / 10000).toFixed(1)}만`;
  if (pop >= 1000) return `${(pop / 1000).toFixed(1)}천`;
  return Math.round(pop).toLocaleString('ko-KR');
}

function formatTimeZone(tz: number): string {
  const start = tz.toString().padStart(2, '0');
  const end = ((tz + 1) % 24).toString().padStart(2, '0');
  return `${start}–${end}시`;
}

export function CustomerFlowPeakHourChart({ dpredicts }: Props) {
  // 모든 동에서 living_pop_forecast 가 null 이면 placeholder
  const anyHasData = dpredicts.some((p) => {
    const lp = p.living_pop_forecast as LivingPopForecast | null;
    return lp != null && Array.isArray(lp.quarters) && lp.quarters.length > 0;
  });

  if (!anyHasData) {
    return (
      <PlaceholderPanel
        modelName="living_pop_forecast"
        description="모든 동에서 유동인구 데이터 미수신"
      />
    );
  }

  // wide format — row = { time_zone, [동A]: pop, [동B]: pop, ... }
  const rows = Array.from({ length: 24 }, (_, h) => {
    const row: Record<string, number | string> = { time_zone: h };
    for (const p of dpredicts) {
      const lp = p.living_pop_forecast as LivingPopForecast | null;
      const hour = lp?.quarters?.[0]?.all_hours?.find((a) => a.time_zone === h);
      row[p.district] = hour?.predicted_pop ?? 0;
    }
    return row;
  });

  // Legend payload (동별 circle + 색)
  const legendPayload = dpredicts.map((p, idx) => ({
    value: p.district,
    type: 'circle' as const,
    color: SERIES_COLORS[idx % SERIES_COLORS.length]!,
    id: `district-${p.district}`,
  }));

  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart data={rows} margin={{ top: 12, right: 16, left: 4, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
        <XAxis
          dataKey="time_zone"
          tickFormatter={(t: number) => (t % 3 === 0 ? `${t}시` : '')}
          tick={{ fill: 'var(--muted-foreground)', fontSize: 13 }}
          interval={0}
        />
        <YAxis
          tickFormatter={(v: number) =>
            v >= 10000 ? `${(v / 10000).toFixed(1)}만` : v.toLocaleString('ko-KR')
          }
          tick={{ fill: 'var(--muted-foreground)', fontSize: 13 }}
          width={72}
        />
        <Tooltip
          formatter={(value: number, name: string) => [`${formatPop(value)}명`, name]}
          labelFormatter={(t: number) => formatTimeZone(t)}
          contentStyle={{
            backgroundColor: 'var(--card)',
            border: '1px solid var(--border)',
            borderRadius: 8,
          }}
          labelStyle={{ color: 'var(--card-foreground)' }}
          itemStyle={{ color: 'var(--muted-foreground)' }}
        />
        <Legend
          verticalAlign="bottom"
          height={28}
          wrapperStyle={{ paddingTop: 8, fontSize: 13 }}
          payload={legendPayload}
        />
        {dpredicts.map((p, idx) => (
          <Bar
            key={p.district}
            dataKey={p.district}
            fill={SERIES_COLORS[idx % SERIES_COLORS.length]!}
            isAnimationActive={false}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
