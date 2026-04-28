/**
 * QuarterlyProjectionChart — 분기별 매출 예측 차트
 *
 * TCN 모델 출력(quarterly_projection)을 시각화:
 * - 신뢰구간(Area): confidence_lower ~ confidence_upper
 * - 분기 매출(Line): revenue
 * - BEP 도달 시점(ReferenceLine): cumulative_profit >= 0 첫 분기
 */

import {
  ComposedChart,
  Area,
  Line,
  ReferenceLine,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
} from 'recharts';
import type { QuarterlyProjection } from '../../types';

interface Props {
  data: QuarterlyProjection[];
}

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

export function QuarterlyProjectionChart({ data }: Props) {
  // 데이터 없거나 빈 배열이면 안내 메시지 표시
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-400 text-sm">데이터 없음</div>
    );
  }

  // BEP 도달 시점: cumulative_profit이 처음으로 0 이상인 분기
  const bepQuarter = data.find((d) => d.cumulative_profit >= 0)?.quarter ?? null;

  // Critical #2 — is_mock 분기 시각 구분: 헤더 배지 + dot 색상/투명도
  const hasMockQuarters = data.some((d) => d.is_mock === true);
  const mockQuarterSet = new Set(data.filter((d) => d.is_mock === true).map((d) => d.quarter));

  return (
    <div className="relative">
      {hasMockQuarters && (
        <div className="absolute right-2 top-0 z-10 flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-widest text-amber-300">
          <span className="h-1 w-1 rounded-full bg-amber-400" />
          일부 분기 mock
        </div>
      )}
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={data} margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
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

          {/* Tooltip — 분기/매출/신뢰구간/누적손익 표시 */}
          <Tooltip
            formatter={(value: number, name: string) => {
              const labels: Record<string, string> = {
                revenue: '분기 매출',
                confidence_lower: '예상 매출 범위 하한',
                confidence_upper: '예상 매출 범위 상한',
              };
              return [formatKRW(value), labels[name] ?? name];
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

          {/* 범례는 차트 외부 미니 카드로 분리 (ForecastTab에서 렌더) */}

          {/* 신뢰구간 — Track B #107 2단계 CI 있으면 95/80 이중 밴드, 없으면 기존 단일 */}
          {data.some((d) => d.ci_95_upper != null && d.ci_95_lower != null) ? (
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
                legendType="square"
                isAnimationActive={false}
                dot={false}
                activeDot={false}
                name="95% 상한"
              />
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
                name="예상 매출 범위 상한"
                legendType="square"
                isAnimationActive={false}
                dot={false}
                activeDot={false}
              />
            </>
          )}

          {/* 분기 매출 라인 — 은은한 drop-shadow glow + 강조 activeDot */}
          <defs>
            <filter id="qp-line-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="2.5" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          <Line
            type="monotone"
            dataKey="revenue"
            stroke="#818cf8"
            strokeWidth={2}
            // mock 분기는 amber dot + opacity 0.4로 시각 구분 (실데이터 기여도와 분리 인지용)
            dot={(props: {
              cx?: number;
              cy?: number;
              payload?: QuarterlyProjection;
              index?: number;
            }) => {
              const { cx, cy, payload, index } = props;
              if (cx == null || cy == null || !payload) {
                return <g key={`qp-dot-${index ?? 0}`} />;
              }
              const isMock = mockQuarterSet.has(payload.quarter);
              return (
                <circle
                  key={`qp-dot-${index ?? payload.quarter}`}
                  cx={cx}
                  cy={cy}
                  r={3.5}
                  fill={isMock ? '#f59e0b' : '#818cf8'}
                  fillOpacity={isMock ? 0.4 : 1}
                />
              );
            }}
            activeDot={{
              r: 5,
              fill: '#818cf8',
              stroke: '#fff',
              strokeWidth: 2,
              filter: 'drop-shadow(0 0 6px rgba(129,140,248,0.9))',
            }}
            name="revenue"
            filter="url(#qp-line-glow)"
            isAnimationActive={false}
          />

          {/* BEP 도달 시점 — null이면 미렌더링 */}
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
