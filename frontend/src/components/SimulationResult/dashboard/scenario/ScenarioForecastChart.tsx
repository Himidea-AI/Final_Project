/**
 * ScenarioForecastChart — TCN v3 4분기 매출 곡선 (7-tier delta line).
 *
 * 명세서 §4.6:
 *   - x축: 1분기 후 / 2분기 후 / 3분기 후 / 4분기 후 (절대 분기명 X — 가입 시점 기준 상대)
 *   - y축: 매출 (원/점포/분기)
 *   - 7-tier DELTA_COLOR — palette-catalog SoT (chart-2/3 + muted-foreground opacity 변조)
 *   - 0% 라인은 dashed (기준선)
 *   - quarter_num categorical 모드 = 4 라인 비교 (별도 분기 비교 차트)
 *
 * mode = "delta": 4 sliders 합산 결과 — 액티브 슬라이더 1종 의 7-level delta 만 그릴 수도 있음.
 *                  여기서는 "active slider" prop 받아 해당 slider 의 7-level 곡선을 모두 그림.
 *                  + combined 라인 (모든 슬라이더 합산) 강조.
 * mode = "quarter": quarter_num 4-tab Q1~Q4 별도 라인 비교.
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
import type { PctSliderKey, QuarterKey, SensitivityResponse } from '../../../../types/elasticity';
import { SLIDER_LABELS } from '../../../../types/elasticity';
import { selectPerStoreBaseline } from './baseline';

// palette-catalog SoT — chart-2 Danger Coral(손실) / muted-foreground(중립) / chart-3 Success Emerald(이익) opacity 변조
const DELTA_COLOR: Record<string, string> = {
  '-30': '#FB565B', // Danger Coral 100%
  '-20': '#FB565B99', // 60%
  '-10': '#FB565B4D', // 30%
  '0': 'var(--muted-foreground)', // 중립 (dashed 기준선)
  '+10': '#008B004D', // Success Emerald 30%
  '+20': '#008B0099', // 60%
  '+30': '#008B00', // 100%
};
// palette-catalog SoT — Deep Blue Sequential 4-tier (Q1~Q4 ordinal 시간 비교).
// Q1~Q4 = 시간 ordinal 의미라 categorical (chart-1~4) 보다 sequential 정합.
const QUARTER_COLOR: Record<QuarterKey, string> = {
  Q1: 'var(--rank-1)', // Deep Blue
  Q2: 'var(--rank-2)', // Electric Blue
  Q3: 'var(--rank-3)', // Sky Blue
  Q4: 'var(--rank-4)', // Ice Blue
};

const X_LABELS = ['1분기 후', '2분기 후', '3분기 후', '4분기 후'];

const formatKRW = (value: number): string => {
  const abs = Math.abs(value);
  if (abs >= 100_000_000) return `${(value / 100_000_000).toFixed(1)}억`;
  if (abs >= 10_000) return `${Math.round(value / 10_000).toLocaleString('ko-KR')}만`;
  return `${Math.round(value).toLocaleString('ko-KR')}원`;
};

const formatTooltip = (value: number): string => `₩${Math.round(value).toLocaleString('ko-KR')}`;

const LEVELS: ReadonlyArray<keyof typeof DELTA_COLOR> = [
  '-30',
  '-20',
  '-10',
  '0',
  '+10',
  '+20',
  '+30',
];

export interface ScenarioForecastChartProps {
  data: SensitivityResponse;
  /** 4 슬라이더 합산 라인 그릴지 (현재 슬라이더 값). null 이면 합산 라인 X. */
  combined?: { values: number[]; label: string } | null;
  /** delta 모드 — 어떤 슬라이더의 7-tier 곡선을 그릴지. null 이면 7-tier 안 그림. */
  activeSlider?: PctSliderKey | null;
  /** "quarter" 모드 = quarter_num Q1~Q4 4 라인 별도 비교. */
  mode?: 'delta' | 'quarter';
  height?: number | string;
}

export function ScenarioForecastChart({
  data,
  combined = null,
  activeSlider = null,
  mode = 'delta',
  height = 320,
}: ScenarioForecastChartProps) {
  const baseline = selectPerStoreBaseline(data);

  // chart data — quarter index → row {quarter: "1분기 후", "-30": value, "+30": ..., combined: ...}
  const rows = X_LABELS.map((label, q) => {
    const row: Record<string, number | string | null> = { quarter: label };
    row['baseline'] = baseline[q] ?? null;

    if (mode === 'delta' && activeSlider) {
      const elasticityForSlider = data.elasticity[activeSlider] ?? {};
      for (const level of LEVELS) {
        const arr = elasticityForSlider[level];
        if (Array.isArray(arr) && arr.length > q && Number.isFinite(arr[q])) {
          row[level] = (baseline[q] ?? 0) * (1 + arr[q] / 100);
        } else {
          row[level] = null;
        }
      }
    }

    if (mode === 'quarter') {
      const qData = data.elasticity.quarter_num ?? {};
      for (const qKey of ['Q1', 'Q2', 'Q3', 'Q4'] as QuarterKey[]) {
        const arr = qData[qKey];
        if (Array.isArray(arr) && arr.length > q && Number.isFinite(arr[q])) {
          row[qKey] = (baseline[q] ?? 0) * (1 + arr[q] / 100);
        } else {
          row[qKey] = null;
        }
      }
    }

    if (combined && combined.values.length > q) {
      row['combined'] = combined.values[q];
    }
    return row;
  });

  // y axis domain
  const allValues: number[] = [];
  for (const row of rows) {
    for (const [k, v] of Object.entries(row)) {
      if (k === 'quarter') continue;
      if (typeof v === 'number' && Number.isFinite(v)) allValues.push(v);
    }
  }
  const yDomain: [number, number] =
    allValues.length === 0
      ? [0, 1]
      : (() => {
          const lo = Math.min(...allValues);
          const hi = Math.max(...allValues);
          return lo === hi ? [lo * 0.9 || 0, hi * 1.1 || 1] : [lo * 0.95, hi * 1.05];
        })();

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={rows} margin={{ top: 12, right: 24, left: 12, bottom: 0 }}>
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
          label={{
            value: '매출 (원/점포/분기)',
            angle: -90,
            position: 'insideLeft',
            style: {
              fontSize: 10,
              fill: 'var(--muted-foreground)',
              textAnchor: 'middle',
            },
          }}
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
          formatter={(v: number, name: string) => {
            const labelMap: Record<string, string> = {
              baseline: '기준선',
              combined: combined?.label ?? '합산',
              ...Object.fromEntries(LEVELS.map((l) => [l, `${l}%`])),
              Q1: 'Q1 시작',
              Q2: 'Q2 시작',
              Q3: 'Q3 시작',
              Q4: 'Q4 시작',
            };
            return [formatTooltip(v), labelMap[name] ?? name];
          }}
        />
        <Legend wrapperStyle={{ fontSize: 10, color: 'var(--muted-foreground)' }} iconType="line" />

        {/* baseline (회색 점선) */}
        <Line
          type="monotone"
          dataKey="baseline"
          stroke="var(--muted-foreground)"
          strokeWidth={1.8}
          strokeDasharray="4 4"
          dot={false}
          name="기준선"
          isAnimationActive={false}
        />

        {/* delta mode 7-tier */}
        {mode === 'delta' &&
          activeSlider &&
          LEVELS.map((level) => (
            <Line
              key={level}
              type="monotone"
              dataKey={level}
              stroke={DELTA_COLOR[level]}
              strokeWidth={level === '0' ? 1.5 : 1.8}
              strokeDasharray={level === '0' ? '5 3' : undefined}
              dot={{ r: 2, fill: DELTA_COLOR[level] }}
              name={`${SLIDER_LABELS[activeSlider]} ${level}%`}
              isAnimationActive={false}
              connectNulls
            />
          ))}

        {/* quarter mode 4 라인 */}
        {mode === 'quarter' &&
          (['Q1', 'Q2', 'Q3', 'Q4'] as QuarterKey[]).map((q) => (
            <Line
              key={q}
              type="monotone"
              dataKey={q}
              stroke={QUARTER_COLOR[q]}
              strokeWidth={2}
              dot={{ r: 2.5, fill: QUARTER_COLOR[q] }}
              name={`${q} 시작`}
              isAnimationActive={false}
              connectNulls
            />
          ))}

        {/* combined (4 슬라이더 합산) */}
        {combined && (
          <Line
            type="monotone"
            dataKey="combined"
            stroke="var(--primary)"
            strokeWidth={2.8}
            dot={{ r: 4, fill: 'var(--primary)' }}
            activeDot={{ r: 6, fill: 'var(--primary)', stroke: 'var(--card)', strokeWidth: 2 }}
            name={combined.label}
            isAnimationActive={false}
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}
