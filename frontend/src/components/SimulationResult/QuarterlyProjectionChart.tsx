/**
 * QuarterlyProjectionChart — 분기별 매출 예측 차트 (다중 동)
 *
 * TCN 모델 출력(quarterly_projection)을 동별로 시각화:
 * - 각 동별 별도 Line (indigo / cyan / amber / rose)
 * - winner 동: strokeWidth 3, dot r 5 강조 (winnerDistrict prop)
 * - 신뢰구간(Area): 첫 번째 동(series[0])의 ci_95/80 또는 confidence_lower/upper 만 음영
 * - BEP 도달 시점(ReferenceLine): 첫 번째 동(series[0])의 cumulative_profit >= 0 첫 분기
 * - 범례: 동 이름
 *
 * Round 2 / B4 (2026-04-29): 단일 동 → 다중 동 시리즈 전환.
 * M5 (2026-04-29): CI 음영/BEP 기준을 winnerDistrict → series[0] 으로 변경 (명세 충실).
 * 호출처에서 series 가 비어있거나 길이 0 이면 "데이터 없음" 표시.
 */

import { useState } from 'react';
import {
  ComposedChart,
  Area,
  Line,
  Legend,
  LabelList,
  ReferenceLine,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
} from 'recharts';
import type { QuarterlyProjection } from '../../types';

/** 동별 분기 매출 시리즈 1건 */
export interface ChartSeries {
  district: string;
  projection: QuarterlyProjection[];
}

interface Props {
  series: ChartSeries[];
  /** 강조 + CI 음영 + BEP 라인 대상 동 (없으면 series[0] 사용) */
  winnerDistrict?: string;
}

// 4동 차트 팔레트 — 1위 동 = chart-1 (Deep Blue, brand primary).
// 2~4위는 vivid-red / teal-green / sunshine-yellow 로 hue 분리 (이 차트 한정).
// NOTE: sunshine-yellow 는 12색 팔레트 정책상 §Decoration (큰 면적 장식) 권장이지만,
//   light-pink CI 음영 위에서 hot-pink/purple 이 묻혀 가독성 약해 강민 판단으로 yellow 채택.
// QuarterlyStatStrip 의 동 선택 chip 색 매핑이 동일 순서를 사용 — drift 방지 위해 export.
export const SERIES_COLORS = [
  'var(--chart-1)',
  'var(--chart-2)',
  'var(--chart-3)',
  'var(--color-sunshine-yellow)',
] as const;
const COLORS = SERIES_COLORS;

// 신뢰구간 음영 fill — 1위 동 매출선(chart-1 = Deep Blue)과 시각 분리.
// 12색 팔레트의 §Decoration 색 (큰 면적 장식 적격, 라인/마커엔 부적격).
// light-pink 는 데이터 라인 색들과 hue 가 멀어 매출선이 또렷이 보이는 배경음영 역할.
const CI_FILL = 'var(--decor-light-pink)';

// 값 크기에 따라 억원/만원 단위 자동 스위칭 — 0.1억원 같은 라벨 중복·정보 손실 방지
const formatKRW = (value: number): string => {
  const abs = Math.abs(value);
  if (abs >= 100_000_000) {
    return `${(value / 100_000_000).toFixed(1)}억원`;
  }
  if (abs >= 10_000) {
    return `${Math.round(value / 10_000).toLocaleString()}만원`;
  }
  return `${Math.round(value).toLocaleString()}원`;
};

export function QuarterlyProjectionChart({ series, winnerDistrict }: Props) {
  // Y축 zoom 토글 — default ON (평탄 데이터 시각 amplification).
  // OFF 시 zero-baseline 복귀 — misleading 방지용 escape hatch.
  const [zoomY, setZoomY] = useState(true);

  // 빈 series / 모든 series projection 비어있음 → 안내 메시지
  const validSeries = (series ?? []).filter((s) => s.projection && s.projection.length > 0);
  if (validSeries.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-muted-foreground text-sm">
        데이터 없음
      </div>
    );
  }

  // winner 동 결정 — 명시값 없으면 첫 시리즈 (라인 강조용)
  const effectiveWinner = winnerDistrict ?? validSeries[0]!.district;

  // 각 동의 첫 4분기만 + quarter 1~4 강제 라벨
  const trimmedSeries = validSeries.map((s) => ({
    district: s.district,
    data: s.projection.slice(0, 4).map((d, i) => ({ ...d, quarter: i + 1 })),
  }));

  // CI 음영 / BEP 라인 기준 시리즈 — 명세상 첫 번째 동(series[0])
  const ciSourceSeries = trimmedSeries[0]!;

  // wide format 변환: row = { quarter, [동]_revenue, ci_high?, ci_low?, ... }
  const has95Ci = ciSourceSeries.data.some((d) => d.ci_95_upper != null && d.ci_95_lower != null);
  const has80Ci = ciSourceSeries.data.some((d) => d.ci_80_upper != null && d.ci_80_lower != null);
  const chartData = [1, 2, 3, 4].map((q) => {
    const row: Record<string, number | null | undefined> = { quarter: q };
    for (const s of trimmedSeries) {
      const point = s.data.find((p) => p.quarter === q);
      row[`${s.district}_revenue`] = point?.revenue ?? null;
    }
    // 첫 번째 동(series[0])의 CI 만 음영용으로 노출
    const ciPoint = ciSourceSeries.data.find((p) => p.quarter === q);
    if (ciPoint) {
      row.ci_95_lower = ciPoint.ci_95_lower ?? null;
      row.ci_95_upper = ciPoint.ci_95_upper ?? null;
      row.ci_80_lower = ciPoint.ci_80_lower ?? null;
      row.ci_80_upper = ciPoint.ci_80_upper ?? null;
      row.confidence_lower = ciPoint.confidence_lower ?? null;
      row.confidence_upper = ciPoint.confidence_upper ?? null;
    }
    return row;
  });

  // BEP 도달 시점: 첫 번째 동(series[0]) 기준
  const bepQuarter = ciSourceSeries.data.find((d) => d.cumulative_profit >= 0)?.quarter ?? null;

  // ─── Y축 auto-zoom 계산 ───
  // 모든 동의 매출 + CI 영역 값을 모아 min/max 산출. zoom ON 시 [min - 18%, max + 18%].
  // OFF 시 [0, max + 18%] (zero-baseline 보호).
  const allValues: number[] = [];
  for (const s of trimmedSeries) {
    for (const d of s.data) if (d.revenue != null) allValues.push(d.revenue);
  }
  for (const d of ciSourceSeries.data) {
    for (const v of [
      d.confidence_lower,
      d.confidence_upper,
      d.ci_95_lower,
      d.ci_95_upper,
      d.ci_80_lower,
      d.ci_80_upper,
    ]) {
      if (v != null) allValues.push(v);
    }
  }
  const dataMin = allValues.length > 0 ? Math.min(...allValues) : 0;
  const dataMax = allValues.length > 0 ? Math.max(...allValues) : 1;
  const range = Math.max(1, dataMax - dataMin);
  const yPad = range * 0.18;
  const yDomain: [number, number] = zoomY
    ? [Math.max(0, dataMin - yPad), dataMax + yPad]
    : [0, dataMax * 1.1];

  // ─── winner 동 4분기 평균 (reference line 용) ───
  const winnerSeries = trimmedSeries.find((s) => s.district === effectiveWinner) ?? ciSourceSeries;
  const winnerVals = winnerSeries.data.map((d) => d.revenue).filter((v): v is number => v != null);
  const winnerAvg =
    winnerVals.length > 0 ? winnerVals.reduce((a, b) => a + b, 0) / winnerVals.length : null;

  // ─── Δ% 라벨 — winner 동만, 직전 분기 대비 변화율 ───
  // 4동 동시 표시 시 라벨 겹침 방지를 위해 winner 단일 시리즈만.
  const winnerKey = `${effectiveWinner}_revenue`;
  const renderDeltaLabel = (props: {
    x?: number | string;
    y?: number | string;
    value?: number | string;
    index?: number;
  }) => {
    const { x, y, value, index } = props;
    const numericValue = typeof value === 'number' ? value : null;
    if (typeof index !== 'number' || index === 0 || numericValue == null) return null;
    const prevRaw = chartData[index - 1]?.[winnerKey];
    const prev = typeof prevRaw === 'number' ? prevRaw : null;
    if (prev == null || prev === 0) return null;
    const delta = ((numericValue - prev) / prev) * 100;
    const sign = delta >= 0 ? '+' : '';
    const fill = delta >= 0 ? 'var(--success)' : 'var(--danger)';
    return (
      <text
        x={typeof x === 'number' ? x + 8 : x}
        y={typeof y === 'number' ? y - 10 : y}
        fill={fill}
        fontSize={10}
        fontWeight={700}
      >
        {sign}
        {delta.toFixed(1)}%
      </text>
    );
  };

  // CI 음영이 한 번이라도 그려지는지 — 통합 범례 항목 표시 여부 결정
  const hasAnyCi =
    has95Ci ||
    has80Ci ||
    ciSourceSeries.data.some((d) => d.confidence_lower != null && d.confidence_upper != null);

  // Legend payload 를 명시적으로 구성 — recharts 의 legendType="none" 이 Area 의
  // name prop 가 있을 때 항목을 완전히 숨기지 못하는 동작을 우회.
  // 동별 매출 라인 (circle) + CI 음영 단일 통합 항목 (rect band).
  const legendPayload: Array<{
    value: string;
    type: 'circle' | 'rect';
    color: string;
    id: string;
  }> = [
    ...trimmedSeries.map((s, idx) => ({
      value: s.district,
      type: 'circle' as const,
      color: COLORS[idx % COLORS.length]!,
      id: `series-${s.district}`,
    })),
    ...(hasAnyCi
      ? [
          {
            value: '낙관 / 비관 범위',
            type: 'rect' as const,
            color: CI_FILL,
            id: 'ci-band',
          },
        ]
      : []),
  ];

  // mock 배지 — 임의 동에 mock 분기가 하나라도 있으면 표시
  const hasMockQuarters = trimmedSeries.some((s) => s.data.some((d) => d.is_mock === true));

  return (
    <div className="relative">
      {/* 우상단 컨트롤 — zoom 토글 + (있을 때) mock 배지. zoom ON 시 "Y축 0 미표시" 명시
          (misleading 방지 — 사용자가 확대 보기 모드임을 항상 인지). */}
      <div className="absolute right-2 top-0 z-10 flex items-center gap-2">
        <button
          type="button"
          onClick={() => setZoomY(!zoomY)}
          className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[0.5625rem] font-bold uppercase tracking-widest transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1 ${
            zoomY
              ? 'border-primary/40 bg-primary/10 text-primary hover:bg-primary/15'
              : 'border-border bg-card text-muted-foreground hover:bg-muted/40'
          }`}
          aria-pressed={zoomY}
          aria-label={zoomY ? 'Y축 자동 줌 ON — 클릭하여 OFF' : 'Y축 자동 줌 OFF — 클릭하여 ON'}
          title={zoomY ? '0 기준선으로 보기' : '데이터 영역으로 확대 보기'}
        >
          <span
            className={`h-1 w-1 rounded-full ${zoomY ? 'bg-primary' : 'bg-muted-foreground'}`}
          />
          {zoomY ? 'Y축 자동 줌: ON' : 'Y축 자동 줌: OFF'}
        </button>
        {hasMockQuarters && (
          <span className="inline-flex items-center gap-1 rounded-full border border-warning/30 bg-warning/10 px-2 py-0.5 text-[0.5625rem] font-bold uppercase tracking-widest text-warning">
            <span className="h-1 w-1 rounded-full bg-warning" />
            일부 분기 mock
          </span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={chartData} margin={{ top: 16, right: 56, left: 10, bottom: 0 }}>
          {/* 격자선 — 수평만 (세로 노이즈 제거로 선 그래프 가독성↑) */}
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />

          {/* X축 — 분기 번호를 한국어 "N분기" 형식으로 표시 (tooltip labelFormatter 와 일관). */}
          <XAxis
            dataKey="quarter"
            tickFormatter={(q: number) => `${q}분기`}
            tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }}
          />

          {/* Y축 — 억원 단위. zoom ON 시 데이터 min~max 영역으로 좁혀 평탄 변동 amplification.
              OFF 시 zero-baseline 으로 복귀 (misleading 회피 escape hatch). */}
          <YAxis
            domain={yDomain}
            tickFormatter={formatKRW}
            tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }}
            width={70}
          />

          {/* Tooltip */}
          <Tooltip
            formatter={(value: number, name: string) => {
              // ci_* / confidence_* 키는 라벨 보강
              const ciLabels: Record<string, string> = {
                ci_95_lower: '비관 시나리오',
                ci_95_upper: '낙관 시나리오',
                ci_80_lower: '비관 (80%)',
                ci_80_upper: '낙관 (80%)',
                confidence_lower: '비관 시나리오',
                confidence_upper: '낙관 시나리오',
              };
              if (name in ciLabels) {
                return [formatKRW(value), ciLabels[name]];
              }
              // {동}_revenue → "{동} 매출"
              if (name.endsWith('_revenue')) {
                const district = name.replace(/_revenue$/, '');
                return [formatKRW(value), `${district} 매출`];
              }
              return [formatKRW(value), name];
            }}
            labelFormatter={(q: number) => `${q}분기`}
            contentStyle={{
              backgroundColor: 'var(--card)',
              border: '1px solid var(--border)',
              borderRadius: 8,
            }}
            labelStyle={{ color: 'var(--card-foreground)' }}
            itemStyle={{ color: 'var(--muted-foreground)' }}
          />

          {/* 범례 — 그래프 아래(standard 위치). payload 명시 구성:
              동별 매출 (circle) + CI 음영 통합 항목 "예상 매출 범위" (rect).
              상한/하한 분리 노출 제거 — 같은 음영 band 의 두 경계라 의미상 중복. */}
          <Legend
            verticalAlign="bottom"
            height={28}
            wrapperStyle={{ paddingTop: 8, fontSize: 11 }}
            payload={legendPayload}
          />

          {/* 신뢰구간 — 첫 번째 동(series[0]) 만 음영. 95/80 이중 또는 단일 confidence.
              fill 색상은 COLORS[0] (chart-1) 로 series[0] 라인 색과 일치 */}
          {has95Ci ? (
            <>
              <Area
                type="monotone"
                dataKey="ci_95_lower"
                stroke="none"
                fill={CI_FILL}
                fillOpacity={0}
                legendType="none"
                isAnimationActive={false}
                dot={false}
                activeDot={false}
                name="95% 하한"
              />
              <Area
                type="monotone"
                dataKey="ci_95_upper"
                stroke="none"
                fill={CI_FILL}
                fillOpacity={0.08}
                legendType="none"
                isAnimationActive={false}
                dot={false}
                activeDot={false}
                name="95% 상한"
              />
              {has80Ci && (
                <>
                  <Area
                    type="monotone"
                    dataKey="ci_80_lower"
                    stroke="none"
                    fill="var(--chart-1)"
                    fillOpacity={0}
                    legendType="none"
                    isAnimationActive={false}
                    dot={false}
                    activeDot={false}
                    name="80% 하한"
                  />
                  <Area
                    type="monotone"
                    dataKey="ci_80_upper"
                    stroke="none"
                    fill="var(--chart-1)"
                    fillOpacity={0.22}
                    legendType="none"
                    isAnimationActive={false}
                    dot={false}
                    activeDot={false}
                    name="80% 상한"
                  />
                </>
              )}
            </>
          ) : (
            <>
              <Area
                type="monotone"
                dataKey="confidence_lower"
                stroke="none"
                fill={CI_FILL}
                fillOpacity={0}
                legendType="none"
                isAnimationActive={false}
                dot={false}
                activeDot={false}
                name="예상 매출 범위 하한"
              />
              <Area
                type="monotone"
                dataKey="confidence_upper"
                stroke="none"
                fill={CI_FILL}
                fillOpacity={0.1}
                legendType="none"
                isAnimationActive={false}
                dot={false}
                activeDot={false}
                name="예상 매출 범위 상한"
              />
            </>
          )}

          {/* winner 동 4분기 평균선 — 미세 변동을 평균 대비 시각 강조용 reference. */}
          {winnerAvg !== null && (
            <ReferenceLine
              y={winnerAvg}
              stroke="var(--muted-foreground)"
              strokeDasharray="3 6"
              strokeOpacity={0.6}
              label={{
                value: '평균',
                position: 'right',
                fill: 'var(--muted-foreground)',
                fontSize: 10,
              }}
            />
          )}

          {/* 동별 매출 라인 — winner 강조 (stroke 3, dot r 5) + winner 만 Δ% 라벨 */}
          {trimmedSeries.map((s, idx) => {
            const color = COLORS[idx % COLORS.length]!;
            const isWinner = s.district === effectiveWinner;
            return (
              <Line
                key={s.district}
                type="monotone"
                dataKey={`${s.district}_revenue`}
                name={s.district}
                stroke={color}
                strokeWidth={isWinner ? 3 : 2}
                dot={{ r: isWinner ? 5 : 3, fill: color }}
                activeDot={{ r: 6, stroke: 'var(--card)', strokeWidth: 2 }}
                isAnimationActive={false}
                connectNulls
              >
                {isWinner && (
                  <LabelList dataKey={`${s.district}_revenue`} content={renderDeltaLabel} />
                )}
              </Line>
            );
          })}

          {/* BEP 도달 시점 — 첫 번째 동(series[0]) 기준, null이면 미렌더링 */}
          {bepQuarter !== null && (
            <ReferenceLine
              x={bepQuarter}
              stroke="var(--success)"
              strokeDasharray="4 3"
              label={{ value: 'BEP', fill: 'var(--success)', fontSize: 12 }}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
