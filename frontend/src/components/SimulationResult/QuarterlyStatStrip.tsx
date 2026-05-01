/**
 * QuarterlyStatStrip — 분기별 매출 요약 패널 (QuarterlyProjectionChart 우측 동반).
 *
 * winner 동의 4분기 매출 + 직전 분기 대비 Δ% 를 row 4개로 stack.
 * 하단에 합계/평균 mini stat — 본부 영업팀 매니저가 한눈에 정량 파악.
 *
 * 평탄 시계열에서 차트가 일자로 보일 때 숫자 진실(직접 라벨)을 별도 panel 로 보강.
 * §3.7 정직성 — 모든 값은 winner 동의 실데이터 기반, 임의 default 없음.
 */

import { useState, useMemo } from 'react';
import { TrendingDown, TrendingUp, Minus } from 'lucide-react';
import { SERIES_COLORS, type ChartSeries } from './QuarterlyProjectionChart';

// sunshine-yellow (idx 3) 위에는 텍스트 가독성 위해 black, 나머지는 white.
const ACTIVE_TEXT_BY_INDEX = ['#ffffff', '#ffffff', '#ffffff', 'var(--color-text-black)'] as const;

interface Props {
  series: ChartSeries[];
  winnerDistrict?: string;
}

const formatKRW = (value: number): string => {
  const abs = Math.abs(value);
  if (abs >= 100_000_000) return `${(value / 100_000_000).toFixed(2)}억`;
  if (abs >= 10_000) return `${Math.round(value / 10_000).toLocaleString()}만`;
  return `${Math.round(value).toLocaleString()}원`;
};

export function QuarterlyStatStrip({ series, winnerDistrict }: Props) {
  const validSeries = useMemo(
    () => (series ?? []).filter((s) => s.projection && s.projection.length > 0),
    [series],
  );

  // 사용자가 선택한 동 — default: winnerDistrict 또는 첫 시리즈.
  // series prop 변경 시 (단일 → 다중 또는 그 반대) selected 가 list 에 없으면 fallback.
  const defaultDistrict =
    validSeries.find((s) => s.district === winnerDistrict)?.district ??
    validSeries[0]?.district ??
    '';
  const [selected, setSelected] = useState<string>(defaultDistrict);
  const target =
    validSeries.find((s) => s.district === selected) ??
    validSeries.find((s) => s.district === winnerDistrict) ??
    validSeries[0];

  if (!target || validSeries.length === 0) return null;
  const quarters = target.projection.slice(0, 4);
  const showSelector = validSeries.length > 1;

  // 분기별 row 데이터 — Δ% 는 직전 분기 대비
  const rows = quarters.map((d, i) => {
    const revenue = d.revenue ?? null;
    const prev = i > 0 ? (quarters[i - 1]?.revenue ?? null) : null;
    const delta =
      revenue != null && prev != null && prev !== 0 ? ((revenue - prev) / prev) * 100 : null;
    return { quarter: i + 1, revenue, delta };
  });

  // 합계 / 평균 — null 제외하고 계산
  const validRevenues = rows.map((r) => r.revenue).filter((v): v is number => v != null);
  const sum = validRevenues.reduce((a, b) => a + b, 0);
  const avg = validRevenues.length > 0 ? sum / validRevenues.length : null;

  // 시나리오 범위 — TCN 95% 신뢰구간 (confidence_lower/upper) 4분기 평균.
  // 본부 영업팀이 가맹점주 제안 시 "비관 X억 ~ 낙관 Y억" 자연어로 사용.
  const lowerVals = quarters
    .map((d) => d.confidence_lower ?? d.ci_95_lower ?? null)
    .filter((v): v is number => v != null);
  const upperVals = quarters
    .map((d) => d.confidence_upper ?? d.ci_95_upper ?? null)
    .filter((v): v is number => v != null);
  const pessimisticAvg =
    lowerVals.length > 0 ? lowerVals.reduce((a, b) => a + b, 0) / lowerVals.length : null;
  const optimisticAvg =
    upperVals.length > 0 ? upperVals.reduce((a, b) => a + b, 0) / upperVals.length : null;

  return (
    <div className="flex h-full flex-col">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-[0.625rem] font-black uppercase tracking-[0.2em] text-muted-foreground">
          분기별 요약
        </h4>
        {!showSelector && (
          <span className="text-[0.625rem] font-bold text-foreground/70">{target.district}</span>
        )}
      </div>

      {/* 동 selector — 다중 시리즈일 때만 노출. 비활성은 원래 디자인 (outlined card) 유지,
          클릭(활성)된 chip 만 그 동의 차트 색을 bg 로 채워 시각 매칭. */}
      {showSelector && (
        <div
          role="tablist"
          aria-label="분기별 요약 동 선택"
          className="mb-3 flex flex-wrap items-center justify-center gap-1.5"
        >
          {validSeries.map((s, idx) => {
            const isActive = s.district === target.district;
            const seriesColor = SERIES_COLORS[idx % SERIES_COLORS.length]!;
            const activeText = ACTIVE_TEXT_BY_INDEX[idx % ACTIVE_TEXT_BY_INDEX.length]!;
            return (
              <button
                key={s.district}
                type="button"
                role="tab"
                aria-selected={isActive}
                onClick={() => setSelected(s.district)}
                style={
                  isActive
                    ? { backgroundColor: seriesColor, borderColor: seriesColor, color: activeText }
                    : undefined
                }
                className={`inline-flex items-center rounded-md border px-2 py-1 text-[0.6875rem] font-bold tracking-wide transition-colors ${
                  isActive
                    ? ''
                    : 'border-border bg-card text-foreground/70 hover:bg-secondary hover:text-foreground'
                }`}
              >
                {s.district}
              </button>
            );
          })}
        </div>
      )}

      {/* Q1~Q4 row stack */}
      <div className="flex flex-col gap-2">
        {rows.map((r) => {
          const deltaSign = r.delta == null ? null : r.delta >= 0 ? 'up' : 'down';
          const deltaIcon =
            deltaSign === 'up' ? (
              <TrendingUp className="h-3 w-3" />
            ) : deltaSign === 'down' ? (
              <TrendingDown className="h-3 w-3" />
            ) : (
              <Minus className="h-3 w-3" />
            );
          const deltaColor =
            deltaSign === 'up'
              ? 'text-success'
              : deltaSign === 'down'
                ? 'text-danger'
                : 'text-muted-foreground';
          return (
            <div
              key={r.quarter}
              className="flex items-center justify-between rounded-lg border border-border bg-card px-3 py-2"
            >
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-[0.625rem] font-bold uppercase tracking-widest text-muted-foreground">
                  Q{r.quarter}
                </span>
                <span className="text-sm font-black tabular-nums text-foreground">
                  {r.revenue != null ? formatKRW(r.revenue) : '—'}
                </span>
              </div>
              <span
                className={`inline-flex items-center gap-0.5 text-[0.6875rem] font-bold tabular-nums ${deltaColor}`}
              >
                {deltaIcon}
                {r.delta == null ? '—' : `${r.delta >= 0 ? '+' : ''}${r.delta.toFixed(1)}%`}
              </span>
            </div>
          );
        })}
      </div>

      {/* 합계 / 평균 mini stat — 분기별 row 와 시각 분리 (border-t) */}
      <div className="mt-4 grid grid-cols-2 gap-2 border-t border-border pt-3">
        <div className="rounded-lg border border-border bg-card px-3 py-2">
          <div className="text-[0.5625rem] font-bold uppercase tracking-widest text-muted-foreground">
            합계
          </div>
          <div className="mt-0.5 text-sm font-black tabular-nums text-foreground">
            {validRevenues.length > 0 ? formatKRW(sum) : '—'}
          </div>
        </div>
        <div className="rounded-lg border border-border bg-card px-3 py-2">
          <div className="text-[0.5625rem] font-bold uppercase tracking-widest text-muted-foreground">
            평균
          </div>
          <div className="mt-0.5 text-sm font-black tabular-nums text-foreground">
            {avg != null ? formatKRW(avg) : '—'}
          </div>
        </div>
      </div>

      {/* 시나리오 범위 한줄평 — TCN 95% 신뢰구간 4분기 평균 (낙관/비관). 영업 화법용. */}
      {pessimisticAvg != null && optimisticAvg != null && (
        <div className="mt-3 rounded-lg border border-border bg-card px-3 py-2.5">
          <div className="mb-1 text-[0.5625rem] font-bold uppercase tracking-widest text-muted-foreground">
            시나리오 범위 · 95% 신뢰
          </div>
          <div className="flex items-baseline justify-between gap-1 tabular-nums">
            <span className="text-[0.6875rem] font-bold text-danger">
              비관 {formatKRW(pessimisticAvg)}
            </span>
            <span className="text-[0.625rem] text-muted-foreground">~</span>
            <span className="text-[0.6875rem] font-bold text-success">
              낙관 {formatKRW(optimisticAvg)}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
