/**
 * CustomerFlowSegmentChart — 4동 통합 타겟 고객 매출 기여 grouped bar
 *
 * 두 모드 한 컴포넌트로 통합 (코드 재사용 + 시각 일관성):
 *   - mode='sales'      : 매출 3종 (세그먼트/식별/전체) 가로 grouped bar
 *   - mode='dimensions' : 차원별 비율 (연령·성별·시간대·요일) 가로 grouped bar (4동 평균 내림차순 정렬)
 *
 * Recharts layout="vertical" 은 horizontal bar (X=number, Y=category) 의미.
 *
 * 색: SERIES_COLORS — 12색 팔레트 SoT 준수.
 * DIMENSION_LABEL: CustomerSegmentCard export 재사용 (중복 정의 회피).
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
import type { CustomerSegment, DistrictPredictionResult } from '../../../../types';
import { SERIES_COLORS } from '../../QuarterlyProjectionChart';
import { formatKrw } from '../utils/formatters';
import { DIMENSION_LABEL } from './CustomerSegmentCard';

interface Props {
  dpredicts: DistrictPredictionResult[];
  mode: 'sales' | 'dimensions';
}

/** 단일 차원 키의 4동 평균 비율 (정렬 키) */
function avgRatio(key: string, dpredicts: DistrictPredictionResult[]): number {
  const vals: number[] = [];
  for (const p of dpredicts) {
    const seg = p.customer_segment as CustomerSegment | null;
    const v = seg?.dimension_ratios?.[key];
    if (typeof v === 'number') vals.push(v);
  }
  if (vals.length === 0) return 0;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

export function CustomerFlowSegmentChart({ dpredicts, mode }: Props) {
  // Legend payload (공통 — 동별 circle + 색)
  const legendPayload = dpredicts.map((p, idx) => ({
    value: p.district,
    type: 'circle' as const,
    color: SERIES_COLORS[idx % SERIES_COLORS.length]!,
    id: `district-${p.district}`,
  }));

  if (mode === 'sales') {
    const rows = [
      {
        category: '세그먼트 매출',
        ...Object.fromEntries(
          dpredicts.map((p) => {
            const seg = p.customer_segment as CustomerSegment | null;
            return [p.district, seg?.segment_sales ?? 0];
          }),
        ),
      },
      {
        category: '식별 매출',
        ...Object.fromEntries(
          dpredicts.map((p) => {
            const seg = p.customer_segment as CustomerSegment | null;
            return [p.district, seg?.identified_sales ?? 0];
          }),
        ),
      },
      {
        category: '전체 매출',
        ...Object.fromEntries(
          dpredicts.map((p) => {
            const seg = p.customer_segment as CustomerSegment | null;
            return [p.district, seg?.total_sales_ref ?? 0];
          }),
        ),
      },
    ];

    return (
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={rows} layout="vertical" margin={{ top: 8, right: 24, left: 4, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
          <XAxis
            type="number"
            tickFormatter={(v: number) => formatKrw(v)}
            tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }}
          />
          <YAxis
            type="category"
            dataKey="category"
            width={140}
            tick={{ fill: 'var(--muted-foreground)', fontSize: 14, fontWeight: 600 }}
          />
          <Tooltip
            formatter={(value: number, name: string) => [`₩${formatKrw(value)}`, name]}
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

  // mode === 'dimensions'
  // 4동 dimension_ratios 의 합집합 키 (동마다 같지만 안전 가드)
  const allKeys = new Set<string>();
  for (const p of dpredicts) {
    const seg = p.customer_segment as CustomerSegment | null;
    if (seg?.dimension_ratios) {
      for (const k of Object.keys(seg.dimension_ratios)) allKeys.add(k);
    }
  }

  const sortedKeys = Array.from(allKeys).sort(
    (a, b) => avgRatio(b, dpredicts) - avgRatio(a, dpredicts),
  );

  const rows = sortedKeys.map((key) => {
    const row: Record<string, number | string> = {
      dimension: DIMENSION_LABEL[key] ?? key,
    };
    for (const p of dpredicts) {
      const seg = p.customer_segment as CustomerSegment | null;
      row[p.district] = (seg?.dimension_ratios?.[key] ?? 0) * 100;
    }
    return row;
  });

  const dynamicHeight = Math.max(260, sortedKeys.length * 44 + 60);

  return (
    <ResponsiveContainer width="100%" height={dynamicHeight}>
      <BarChart data={rows} layout="vertical" margin={{ top: 8, right: 24, left: 4, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
        <XAxis
          type="number"
          tickFormatter={(v: number) => `${v.toFixed(0)}%`}
          tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }}
        />
        <YAxis
          type="category"
          dataKey="dimension"
          width={130}
          tick={{ fill: 'var(--muted-foreground)', fontSize: 14, fontWeight: 600 }}
        />
        <Tooltip
          formatter={(value: number, name: string) => [`${value.toFixed(1)}%`, name]}
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
          wrapperStyle={{ paddingTop: 8, fontSize: 11 }}
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
