/**
 * QuarterlyProjectionChart — 분기별 매출 예측 차트 (다중 동)
 *
 * TCN 모델 출력(quarterly_projection)을 동별로 시각화:
 * - 각 동별 별도 Line (Deep Blue Sequential 4-tier — winner 진하게 → 4위 옅게)
 * - winner 동: strokeWidth 3, dot r 5 강조 (winnerDistrict prop)
 * - BEP 도달 시점(ReferenceLine): winner 동의 cumulative_profit > 0 첫 분기 (강조 라인과 일치)
 * - 범례: 동 이름
 *
 * Round 2 / B4 (2026-04-29): 단일 동 → 다중 동 시리즈 전환.
 * 2026-05-04 (강민): CI 음영(Area) + "낙관/비관 범위" 범례 제거 — 차트 정돈.
 * 호출처에서 series 가 비어있거나 길이 0 이면 "데이터 없음" 표시.
 */

import { useState } from 'react';
import {
  ComposedChart,
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
  /** 강조 + BEP 라인 대상 동 (없으면 series[0] 사용) */
  winnerDistrict?: string;
}

// 2026-05-04: 4동 ranking 비교 categorical 4 색 (Sequential Blue 가독성 부족으로 회귀).
// hue distinct: Deep Blue / Console Purple / Console Pink / Starbucks Green (60° 균등 분포).
// 사용처: dpredicts 를 ranking 순(winner_district + top_3_candidates) 으로 정렬 후 idx 매핑.
// idx 0 = winner / 1=2위 / 2=3위 / 3=4위. winner 만 stroke 3px / 나머지 2.5px solid 로 ordinal 강조.
// QuarterlyStatStrip 의 동 chip 색도 동일 순서 — drift 방지 위해 export.
export const SERIES_COLORS = [
  'var(--rank-1)',
  'var(--rank-2)',
  'var(--rank-3)',
  'var(--rank-4)',
] as const;
const COLORS = SERIES_COLORS;

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

  // 2026-05-04: 매출 예측은 TCN 모델이 4분기를 출력하므로 UI 도 4분기까지만 표시.
  // 백엔드가 그 이상 분기를 보내더라도 매출 예측 탭에서는 4분기로 trim.
  const QUARTER_CAP = 4;
  const maxLen = Math.max(...validSeries.map((s) => s.projection.length));
  const visibleLen = Math.min(QUARTER_CAP, maxLen);
  const trimmedSeries = validSeries.map((s) => ({
    district: s.district,
    data: s.projection.slice(0, visibleLen).map((d, i) => ({ ...d, quarter: i + 1 })),
  }));

  // wide format 변환: row = { quarter, [동]_revenue, ... }
  const quarterAxis = Array.from({ length: visibleLen }, (_, i) => i + 1);
  const chartData = quarterAxis.map((q) => {
    const row: Record<string, number | null | undefined> = { quarter: q };
    for (const s of trimmedSeries) {
      const point = s.data.find((p) => p.quarter === q);
      row[`${s.district}_revenue`] = point?.revenue ?? null;
    }
    return row;
  });

  // BEP 도달 시점: winner 동 기준 (강조 라인과 일치).
  // cumulative_profit > 0 strict 비교로 backend default 0 폴백 매칭 방지.
  const winnerSourceSeries =
    trimmedSeries.find((s) => s.district === effectiveWinner) ?? trimmedSeries[0]!;
  const bepQuarter = winnerSourceSeries.data.find((d) => d.cumulative_profit > 0)?.quarter ?? null;

  // ─── Y축 auto-zoom 계산 ───
  // 모든 동의 매출 값을 모아 min/max 산출. zoom ON 시 [min - 18%, max + 18%].
  // OFF 시 [0, max + 18%] (zero-baseline 보호).
  const allValues: number[] = [];
  for (const s of trimmedSeries) {
    for (const d of s.data) if (d.revenue != null) allValues.push(d.revenue);
  }
  const dataMin = allValues.length > 0 ? Math.min(...allValues) : 0;
  const dataMax = allValues.length > 0 ? Math.max(...allValues) : 1;
  const range = Math.max(1, dataMax - dataMin);
  const yPad = range * 0.18;
  const yDomain: [number, number] = zoomY
    ? [Math.max(0, dataMin - yPad), dataMax + yPad]
    : [0, dataMax * 1.1];

  // ─── winner 동 4분기 평균 (reference line 용) ───
  // winnerSourceSeries 재사용 (BEP 라인과 동일 기준).
  const winnerVals = winnerSourceSeries.data
    .map((d) => d.revenue)
    .filter((v): v is number => v != null);
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

  // Legend payload — 동별 매출 라인 circle 만.
  const legendPayload = trimmedSeries.map((s, idx) => ({
    value: s.district,
    type: 'circle' as const,
    color: COLORS[idx % COLORS.length]!,
    id: `series-${s.district}`,
  }));

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
        {bepQuarter === null && (
          <span
            className="inline-flex items-center gap-1 rounded-full border border-muted-foreground/30 bg-muted/30 px-2 py-0.5 text-[0.5625rem] font-bold uppercase tracking-widest text-muted-foreground"
            title="winner 동의 누적이익이 시뮬 기간 내 양수 도달 못 함"
          >
            <span className="h-1 w-1 rounded-full bg-muted-foreground" />
            BEP 미도달
          </span>
        )}
        {maxLen > QUARTER_CAP && (
          <span
            className="inline-flex items-center gap-1 rounded-full border border-warning/30 bg-warning/10 px-2 py-0.5 text-[0.5625rem] font-bold uppercase tracking-widest text-warning"
            title={`실제 시뮬은 ${maxLen}분기 — 첫 ${QUARTER_CAP}분기만 표시`}
          >
            <span className="h-1 w-1 rounded-full bg-warning" />
            {QUARTER_CAP}+분기 표시 생략
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

          {/* 범례 — 그래프 아래. 동별 매출 라인만 (CI 음영 제거). */}
          <Legend
            verticalAlign="bottom"
            height={28}
            wrapperStyle={{ paddingTop: 8, fontSize: 11 }}
            payload={legendPayload}
          />

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

          {/* 동별 매출 라인 — Deep Blue Sequential 4-tier stroke hierarchy.
              winner (idx 0): stroke 3px / dot r 5 / solid (강조)
              2~3위 (idx 1~2): stroke 2.5px / dot r 4 / solid
              4위 (마지막 idx, Ice Blue): stroke 3px / dot r 4 / dashed `6 3` — 1.3:1 contrast 형태 채널 보완
              winner 만 Δ% 라벨 (4동 동시 표시 시 라벨 겹침 방지). */}
          {trimmedSeries.map((s, idx) => {
            const color = COLORS[idx % COLORS.length]!;
            const isWinner = s.district === effectiveWinner;
            // categorical 4 색 — 모두 AAA/AA contrast 통과라 dashed 형태 보완 불요.
            // winner=3px solid r=5 / 나머지=2.5px solid r=4 — ordinal 강조만 stroke 로 표현.
            const strokeWidth = isWinner ? 3 : 2.5;
            const dotR = isWinner ? 5 : 4;
            return (
              <Line
                key={s.district}
                type="monotone"
                dataKey={`${s.district}_revenue`}
                name={s.district}
                stroke={color}
                strokeWidth={strokeWidth}
                dot={{ r: dotR, fill: color }}
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

          {/* BEP 도달 시점 — winner 동 기준 (강조 라인과 일치). null이면 미렌더링 + 우상단 배지 */}
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
