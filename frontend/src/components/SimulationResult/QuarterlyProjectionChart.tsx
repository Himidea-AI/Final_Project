/**
 * QuarterlyProjectionChart — 분기별 매출 예측 차트 (다중 동)
 *
 * TCN 모델 출력(quarterly_projection)을 동별로 시각화:
 * - 각 동별 별도 Line (indigo / cyan / amber / rose)
 * - winner 동: strokeWidth 3, dot r 5 강조
 * - 신뢰구간(Area): winner 동의 ci_95/80 또는 confidence_lower/upper 만 음영
 * - BEP 도달 시점(ReferenceLine): winner 동의 cumulative_profit >= 0 첫 분기
 * - 범례: 동 이름
 *
 * Round 2 / B4 (2026-04-29): 단일 동 → 다중 동 시리즈 전환.
 * 호출처에서 series 가 비어있거나 길이 0 이면 "데이터 없음" 표시.
 */

import {
  ComposedChart,
  Area,
  Line,
  Legend,
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

// indigo / cyan / amber / rose
const COLORS = ['#818cf8', '#22d3ee', '#fbbf24', '#fb7185'] as const;

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
  // 빈 series / 모든 series projection 비어있음 → 안내 메시지
  const validSeries = (series ?? []).filter((s) => s.projection && s.projection.length > 0);
  if (validSeries.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-400 text-sm">데이터 없음</div>
    );
  }

  // winner 동 결정 — 명시값 없으면 첫 시리즈
  const effectiveWinner = winnerDistrict ?? validSeries[0]!.district;

  // 각 동의 첫 4분기만 + quarter 1~4 강제 라벨
  const trimmedSeries = validSeries.map((s) => ({
    district: s.district,
    data: s.projection.slice(0, 4).map((d, i) => ({ ...d, quarter: i + 1 })),
  }));

  // winner 시리즈 (CI 음영 / BEP 라인 / mock 배지 판단용)
  const winnerSeries =
    trimmedSeries.find((s) => s.district === effectiveWinner) ?? trimmedSeries[0]!;

  // wide format 변환: row = { quarter, [동]_revenue, ci_high?, ci_low?, ... }
  const has95Ci = winnerSeries.data.some((d) => d.ci_95_upper != null && d.ci_95_lower != null);
  const has80Ci = winnerSeries.data.some((d) => d.ci_80_upper != null && d.ci_80_lower != null);
  const chartData = [1, 2, 3, 4].map((q) => {
    const row: Record<string, number | null | undefined> = { quarter: q };
    for (const s of trimmedSeries) {
      const point = s.data.find((p) => p.quarter === q);
      row[`${s.district}_revenue`] = point?.revenue ?? null;
    }
    // winner 동의 CI 만 음영용으로 노출
    const winnerPoint = winnerSeries.data.find((p) => p.quarter === q);
    if (winnerPoint) {
      row.ci_95_lower = winnerPoint.ci_95_lower ?? null;
      row.ci_95_upper = winnerPoint.ci_95_upper ?? null;
      row.ci_80_lower = winnerPoint.ci_80_lower ?? null;
      row.ci_80_upper = winnerPoint.ci_80_upper ?? null;
      row.confidence_lower = winnerPoint.confidence_lower ?? null;
      row.confidence_upper = winnerPoint.confidence_upper ?? null;
    }
    return row;
  });

  // BEP 도달 시점: winner 동 기준
  const bepQuarter = winnerSeries.data.find((d) => d.cumulative_profit >= 0)?.quarter ?? null;

  // mock 배지 — 임의 동에 mock 분기가 하나라도 있으면 표시
  const hasMockQuarters = trimmedSeries.some((s) => s.data.some((d) => d.is_mock === true));

  return (
    <div className="relative">
      {hasMockQuarters && (
        <div className="absolute right-2 top-0 z-10 flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[0.5625rem] font-bold uppercase tracking-widest text-amber-300">
          <span className="h-1 w-1 rounded-full bg-amber-400" />
          일부 분기 mock
        </div>
      )}
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
          {/* 격자선 — 수평만 (세로 노이즈 제거로 선 그래프 가독성↑) */}
          <CartesianGrid strokeDasharray="3 3" stroke="#3a3633" vertical={false} />

          {/* X축 — 분기 번호를 Q1, Q2 형식으로 표시 */}
          <XAxis
            dataKey="quarter"
            tickFormatter={(q: number) => `Q${q}`}
            tick={{ fill: '#9ca3af', fontSize: 12 }}
          />

          {/* Y축 — 억원 단위 */}
          <YAxis tickFormatter={formatKRW} tick={{ fill: '#9ca3af', fontSize: 11 }} width={70} />

          {/* Tooltip */}
          <Tooltip
            formatter={(value: number, name: string) => {
              // ci_* / confidence_* 키는 라벨 보강
              const ciLabels: Record<string, string> = {
                ci_95_lower: '95% 하한',
                ci_95_upper: '95% 상한',
                ci_80_lower: '80% 하한',
                ci_80_upper: '80% 상한',
                confidence_lower: '예상 매출 범위 하한',
                confidence_upper: '예상 매출 범위 상한',
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
              backgroundColor: '#1e1b18',
              border: '1px solid #3a3633',
              borderRadius: 8,
            }}
            labelStyle={{ color: '#fff' }}
            itemStyle={{ color: '#9ca3af' }}
          />

          {/* 범례 — 동 이름. CI Area 는 legendType="none" 으로 숨김 */}
          <Legend
            verticalAlign="top"
            height={28}
            wrapperStyle={{ paddingBottom: 4, fontSize: 11 }}
            iconType="circle"
          />

          {/* 신뢰구간 — winner 동만 음영. 95/80 이중 또는 단일 confidence */}
          {has95Ci ? (
            <>
              <Area
                type="monotone"
                dataKey="ci_95_lower"
                stroke="none"
                fill="#818cf8"
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
                fill="#818cf8"
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
                    fill="#818cf8"
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
                    fill="#818cf8"
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
                fill="#818cf8"
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
                fill="#818cf8"
                fillOpacity={0.1}
                legendType="none"
                isAnimationActive={false}
                dot={false}
                activeDot={false}
                name="예상 매출 범위 상한"
              />
            </>
          )}

          {/* 동별 매출 라인 — winner 강조 (stroke 3, dot r 5) */}
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
                activeDot={{ r: 6, stroke: '#fff', strokeWidth: 2 }}
                isAnimationActive={false}
                connectNulls
              />
            );
          })}

          {/* BEP 도달 시점 — winner 동 기준, null이면 미렌더링 */}
          {bepQuarter !== null && (
            <ReferenceLine
              x={bepQuarter}
              stroke="#10B981"
              strokeDasharray="4 3"
              label={{ value: 'BEP', fill: '#10B981', fontSize: 12 }}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
