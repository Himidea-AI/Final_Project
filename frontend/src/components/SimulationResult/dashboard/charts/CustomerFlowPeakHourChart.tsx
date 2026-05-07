/**
 * CustomerFlowPeakHourChart — 4동 통합 24시간 유동인구 시각화 (재구조 2026-05-03)
 *
 * 변경 동기 (강민): 96개 grouped bar (24h × 4동) → 색동저고리 + 시간 패턴 비교 어려움.
 * 새 패턴:
 *   1) 동별 Peak Hour KPI 카드 4개 (winner 첫 카드 + ring 강조)
 *   2) Heatmap 4 row × 24 col — Deep Blue 단일 hue + opacity 변조 (4동 통합 max 기준 normalize)
 *
 * recharts heatmap 미지원 → HTML/CSS grid 자체 구현.
 *
 * 입력: dpredicts (DistrictPredictionResult[]) — 4동 모두, is_excluded_combo 제외 후
 * 각 동의 living_pop_forecast.quarters[0].all_hours 24시간대 인구를 사용.
 *
 * 빈 데이터 (모든 동에서 living_pop_forecast 가 null) → PlaceholderPanel.
 * 일부 동만 데이터 있는 경우 — 해당 row 만 색칠, 나머지 row 는 0 opacity (— 표시).
 *
 * winner: ranking 첫 번째 카드 + Heatmap 첫 row, ring-primary/30 강조.
 */

import { useEffect, useRef, useState } from 'react';
import type {
  DistrictPredictionResult,
  LivingPopForecast,
  SimulationOutput,
} from '../../../../types';
import { SERIES_COLORS } from '../../QuarterlyProjectionChart';
import { PlaceholderPanel } from '../shared/PlaceholderPanel';
import { sortByRanking } from '../utils/rankSort';

interface Props {
  dpredicts: DistrictPredictionResult[];
  /** ranking 정렬 (winner→4위) 시 사용 — winner_district / top_3_candidates 참조. */
  simResult: SimulationOutput;
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

/** 시간대 → 한국어 라벨 (점심/저녁 등 — KPI 카드용) */
function bucketLabel(tz: number): string {
  if (tz >= 0 && tz < 6) return '심야';
  if (tz >= 6 && tz < 11) return '오전';
  if (tz >= 11 && tz < 14) return '점심';
  if (tz >= 14 && tz < 17) return '오후';
  if (tz >= 17 && tz < 21) return '저녁';
  return '야간';
}

interface DistrictPeakSummary {
  district: string;
  peakTz: number | null;
  peakPop: number | null;
  hours: Array<{ time_zone: number; predicted_pop: number }>;
}

function summarize(p: DistrictPredictionResult): DistrictPeakSummary {
  const lp = p.living_pop_forecast as LivingPopForecast | null;
  const all = lp?.quarters?.[0]?.all_hours ?? [];
  if (all.length === 0) {
    return { district: p.district, peakTz: null, peakPop: null, hours: [] };
  }
  let peakTz = all[0]!.time_zone;
  let peakPop = all[0]!.predicted_pop;
  for (const h of all) {
    if (h.predicted_pop > peakPop) {
      peakPop = h.predicted_pop;
      peakTz = h.time_zone;
    }
  }
  return {
    district: p.district,
    peakTz,
    peakPop,
    hours: all.map((h) => ({ time_zone: h.time_zone, predicted_pop: h.predicted_pop })),
  };
}

export function CustomerFlowPeakHourChart({ dpredicts, simResult }: Props) {
  // ranking 정렬 (winner→4위)
  const sorted = sortByRanking(dpredicts, simResult);
  const summaries = sorted.map(summarize);

  // Heatmap 박스 폭 측정 → cell 개수(SUB) 동적 결정.
  // cell 모양(w-4=16px, gap-px=1px) 고정 + 박스 폭에 맞춰 24h 를 SUB 등분 보간.
  // ex) 박스 1200px → 약 70 cell → SUB=2 (48 cell). 빈 공간이 cell 한 개 미만 남도록.
  const heatmapRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(0);
  useEffect(() => {
    if (!heatmapRef.current) return;
    const ro = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) setContainerWidth(entry.contentRect.width);
    });
    ro.observe(heatmapRef.current);
    return () => ro.disconnect();
  }, []);
  const CELL_W = 16; // w-4
  const CELL_GAP = 1; // gap-px
  const LABEL_W = 80; // w-20
  const LABEL_GAP = 12; // gap-3
  const cellsArea = Math.max(0, containerWidth - LABEL_W - LABEL_GAP);
  const cellsCapacity =
    cellsArea > 0 ? Math.max(24, Math.floor((cellsArea + CELL_GAP) / (CELL_W + CELL_GAP))) : 24;
  const SUB = Math.max(1, Math.floor(cellsCapacity / 24));
  const TOTAL_CELLS = 24 * SUB;

  // 모든 동에서 living_pop_forecast 가 null 이면 placeholder
  const anyHasData = summaries.some((s) => s.hours.length > 0);
  if (!anyHasData) {
    return (
      <PlaceholderPanel
        modelName="living_pop_forecast"
        description="모든 동에서 유동인구 데이터 미수신"
      />
    );
  }

  // 4동 통합 max (heatmap normalize 기준)
  let globalMax = 0;
  for (const s of summaries) {
    for (const h of s.hours) {
      if (h.predicted_pop > globalMax) globalMax = h.predicted_pop;
    }
  }
  if (globalMax <= 0) globalMax = 1;

  const winnerDistrict = simResult.winner_district ?? summaries[0]!.district;

  // 시간대 기준 lookup map (district × hour → pop)
  const popByDistrictHour = new Map<string, number>();
  for (const s of summaries) {
    for (const h of s.hours) {
      popByDistrictHour.set(`${s.district}::${h.time_zone}`, h.predicted_pop);
    }
  }

  return (
    <div className="space-y-6 min-w-0 max-w-full">
      {/* ── KPI 카드 4개 (ranking 순, winner ring 강조). 동별 색 = dot + 숫자. ── */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {summaries.map((s, idx) => {
          const isWinner = s.district === winnerDistrict;
          const hasData = s.peakTz != null && s.peakPop != null;
          const seriesColor = SERIES_COLORS[idx % SERIES_COLORS.length]!;
          return (
            <div
              key={s.district}
              className={[
                'rounded-2xl border bg-card p-4',
                isWinner ? 'border-primary/30 ring-2 ring-primary/30' : 'border-border',
              ].join(' ')}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <span
                    aria-hidden
                    className="size-2 shrink-0 rounded-full"
                    style={{ backgroundColor: seriesColor }}
                  />
                  <span className="text-sm font-black text-foreground tracking-tight truncate">
                    {s.district}
                  </span>
                </div>
                {isWinner && (
                  <span className="rounded-full border border-primary/20 bg-primary/10 px-2 py-0.5 text-[0.5625rem] font-black uppercase tracking-widest text-primary">
                    Winner
                  </span>
                )}
              </div>
              {hasData ? (
                <div className="mt-3 flex items-end justify-between gap-3">
                  {/* 좌측 — 라벨 + 시간대 */}
                  <div className="min-w-0">
                    <div className="text-[0.625rem] font-black uppercase tracking-widest text-muted-foreground">
                      Peak · {bucketLabel(s.peakTz!)}
                    </div>
                    <div className="mt-1 text-base font-black tabular-nums tracking-tight text-foreground">
                      {formatTimeZone(s.peakTz!)}
                    </div>
                  </div>
                  {/* 우측 — 값 (인구수) */}
                  <div
                    className="shrink-0 text-2xl font-black tabular-nums tracking-tighter leading-none"
                    style={{ color: seriesColor }}
                  >
                    {formatPop(s.peakPop!)}
                    <span className="ml-1 text-xs font-bold text-muted-foreground">명</span>
                  </div>
                </div>
              ) : (
                <div className="mt-3 text-xs text-muted-foreground">데이터 없음</div>
              )}
            </div>
          );
        })}
      </div>

      {/* ── Heatmap 4 row × (24×SUB) col ──
          cell flex-1 로 컨테이너 폭에 균등 분배 → 저장/리사이즈에도 카드 밖 튀어나감 없음.
          인접 시간대 사이 linear interpolation 으로 자연스러운 그라데이션. */}
      <div ref={heatmapRef} className="w-full min-w-0">
        {/* row 컨테이너 */}
        <div className="flex flex-col gap-1">
          {summaries.map((s, idx) => {
            const seriesColor = SERIES_COLORS[idx % SERIES_COLORS.length]!;
            return (
              <div key={s.district} className="flex items-center gap-3">
                {/* 동 라벨 — 좌측 동별 색 dot + 동 이름 */}
                <div className="flex w-20 shrink-0 items-center gap-1.5">
                  <span
                    aria-hidden
                    className="size-2 shrink-0 rounded-full"
                    style={{ backgroundColor: seriesColor }}
                  />
                  <span className="text-sm font-bold tabular-nums text-foreground truncate">
                    {s.district}
                  </span>
                </div>
                {/* (24×SUB) cell row — 인접 시간대 linear interpolation.
                    flex-1 + min-w-0 으로 컨테이너 폭에 균등 분배 → 카드 밖 튀어나감 차단. */}
                <div className="flex flex-1 gap-px min-w-0">
                  {Array.from({ length: TOTAL_CELLS }, (_, i) => {
                    const h0 = Math.floor(i / SUB);
                    const h1 = (h0 + 1) % 24;
                    const t = (i % SUB) / SUB; // 0 ~ <1 보간 가중치
                    const popA = popByDistrictHour.get(`${s.district}::${h0}`) ?? null;
                    const popB = popByDistrictHour.get(`${s.district}::${h1}`) ?? null;
                    const pop =
                      popA != null && popB != null
                        ? popA + (popB - popA) * t
                        : (popA ?? popB ?? null);
                    const ratio = pop != null ? pop / globalMax : 0;
                    const opacity = pop == null ? 1 : Math.max(0.05, Math.min(1, ratio));
                    const tooltip =
                      pop != null
                        ? `${s.district} · ${formatTimeZone(h0)} · ${formatPop(pop)}명`
                        : `${s.district} · ${formatTimeZone(h0)} · 데이터 없음`;
                    return (
                      <div
                        key={i}
                        title={tooltip}
                        className="flex-1 min-w-0 h-8 rounded-sm transition-opacity"
                        style={{
                          backgroundColor: pop == null ? 'var(--secondary)' : seriesColor,
                          opacity,
                        }}
                      />
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

        {/* X축 시간 라벨 — cell row 와 동일하게 flex-1 분배. */}
        <div className="mt-2 flex items-center gap-3">
          <div className="w-20 shrink-0" />
          <div className="flex flex-1 gap-px min-w-0">
            {Array.from({ length: TOTAL_CELLS }, (_, i) => {
              const h = Math.floor(i / SUB);
              const isHourStart = i % SUB === 0;
              return (
                <div
                  key={i}
                  className="flex-1 min-w-0 text-center text-[0.5625rem] tabular-nums text-muted-foreground"
                >
                  {isHourStart && h % 3 === 0 ? h : ''}
                </div>
              );
            })}
          </div>
        </div>

        {/* 범례 — 동별 색 + opacity 강도. cell 색 = 동별, 진하기 = 인구 강도. */}
        <div className="mt-4 flex items-center gap-3">
          <div className="w-20 shrink-0 text-[0.625rem] font-black uppercase tracking-widest text-muted-foreground">
            인구 강도
          </div>
          <span className="text-[0.625rem] tabular-nums text-muted-foreground">낮음</span>
          <div className="flex items-center gap-px">
            {[0.1, 0.3, 0.55, 0.8, 1].map((op) => (
              <div
                key={op}
                className="h-2 w-6 rounded-sm"
                style={{ backgroundColor: 'var(--rank-1)', opacity: op }}
              />
            ))}
          </div>
          <span className="text-[0.625rem] tabular-nums text-muted-foreground">
            {formatPop(globalMax)}명
          </span>
          <span className="ml-3 text-[0.625rem] text-muted-foreground">
            · 색 = 동, 진하기 = 인구
          </span>
        </div>
      </div>
    </div>
  );
}
