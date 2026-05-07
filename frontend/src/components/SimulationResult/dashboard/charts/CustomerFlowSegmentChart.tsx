/**
 * CustomerFlowSegmentChart — 4동 통합 타겟 고객 매출 기여 시각화 (재구조 2026-05-03)
 *
 * 변경 동기 (강민):
 *   - mode='sales': 12 grouped bar 의 nested 의미 (전체⊃식별⊃세그먼트) 손실 → Nested Progress
 *   - mode='dimensions': 80+ horizontal bar 4동 거의 동일값 노이즈 → winner 동 Hero KPI 4 카드
 *
 * 두 모드 한 컴포넌트로 통합 (코드 재사용 + 시각 일관성):
 *   - mode='sales'      : 4동 row × 3 layer (전체/식별/세그먼트) HTML/CSS Progress, opacity 1.0/0.7/0.4
 *   - mode='dimensions' : winner 동의 dimension peak 4 카테고리 (연령·성별·시간대·요일) Hero KPI grid
 *
 * recharts 미사용 — Tailwind + inline width %.
 *
 * 색: SERIES_COLORS — ranking idx 매핑. 같은 동의 3 layer 는 같은 색 + opacity 변조.
 * DIMENSION_LABEL: CustomerSegmentCard export 재사용.
 */

import { useState } from 'react';
import type {
  CustomerSegment,
  DistrictPredictionResult,
  SimulationOutput,
} from '../../../../types';
import { SERIES_COLORS } from '../../QuarterlyProjectionChart';
import { formatKrw } from '../utils/formatters';
import { sortByRanking } from '../utils/rankSort';
import { DIMENSION_LABEL } from './CustomerSegmentCard';
import { PlaceholderPanel } from '../shared/PlaceholderPanel';

interface Props {
  dpredicts: DistrictPredictionResult[];
  mode: 'sales' | 'dimensions';
  /** ranking 정렬 (winner→4위) 시 사용 — winner_district / top_3_candidates 참조. */
  simResult: SimulationOutput;
}

// ─────────────────────────────────────────────────────────────────────────────
// SALES — Nested Progress Bar (4동 row × 3 layer)
// ─────────────────────────────────────────────────────────────────────────────

interface SalesRow {
  district: string;
  total: number;
  identified: number;
  segment: number;
  hasData: boolean;
}

function buildSalesRows(sorted: DistrictPredictionResult[]): { rows: SalesRow[]; max: number } {
  const rows: SalesRow[] = sorted.map((p) => {
    const seg = p.customer_segment as CustomerSegment | null;
    const total = seg?.total_sales_per_store ?? 0;
    const identified = seg?.identified_sales ?? 0;
    const segment = seg?.segment_sales ?? 0;
    return {
      district: p.district,
      total,
      identified,
      segment,
      hasData: seg != null,
    };
  });
  const max = Math.max(1, ...rows.map((r) => r.total));
  return { rows, max };
}

function SalesNestedProgress({
  sorted,
  winnerDistrict,
}: {
  sorted: DistrictPredictionResult[];
  winnerDistrict: string;
}) {
  const { rows, max } = buildSalesRows(sorted);

  return (
    <div className="space-y-3">
      {rows.map((r, idx) => {
        const isWinner = r.district === winnerDistrict;
        const baseColor = SERIES_COLORS[idx % SERIES_COLORS.length]!;
        const totalPct = (r.total / max) * 100;
        const identifiedPct = (r.identified / max) * 100;
        const segmentPct = (r.segment / max) * 100;
        const identifiedRatio = r.total > 0 ? Math.round((r.identified / r.total) * 100) : null;
        const segmentRatio = r.total > 0 ? Math.round((r.segment / r.total) * 100) : null;

        return (
          <div
            key={r.district}
            className={[
              'rounded-2xl border bg-card p-4 space-y-3',
              isWinner ? 'border-primary/30 ring-2 ring-primary/30' : 'border-border',
            ].join(' ')}
          >
            {/* row header */}
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span
                  className="inline-block h-3 w-3 rounded-full"
                  style={{ backgroundColor: baseColor }}
                />
                <span className="text-sm font-black tracking-tight text-foreground">
                  {r.district}
                </span>
                {isWinner && (
                  <span className="rounded-full border border-primary/20 bg-primary/10 px-2 py-0.5 text-[0.5625rem] font-black uppercase tracking-widest text-primary">
                    Winner
                  </span>
                )}
              </div>
              {!r.hasData && (
                <span className="text-[0.6875rem] text-muted-foreground">데이터 없음</span>
              )}
            </div>

            {/* 3 layer progress — 같은 색, opacity 1.0 / 0.7 / 0.4 */}
            <div className="space-y-2">
              <ProgressLayer
                label="점포당 분기 매출"
                widthPct={totalPct}
                color={baseColor}
                opacity={1.0}
                rightLabel={r.total > 0 ? `₩${formatKrw(r.total)}` : '—'}
                ratioLabel={null}
              />
              <ProgressLayer
                label="식별 매출"
                widthPct={identifiedPct}
                color={baseColor}
                opacity={0.7}
                rightLabel={r.identified > 0 ? `₩${formatKrw(r.identified)}` : '—'}
                ratioLabel={identifiedRatio != null ? `${identifiedRatio}%` : null}
              />
              <ProgressLayer
                label="세그먼트"
                widthPct={segmentPct}
                color={baseColor}
                opacity={0.4}
                rightLabel={r.segment > 0 ? `₩${formatKrw(r.segment)}` : '—'}
                ratioLabel={segmentRatio != null ? `${segmentRatio}%` : null}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

interface ProgressLayerProps {
  label: string;
  widthPct: number;
  color: string;
  opacity: number;
  rightLabel: string;
  ratioLabel: string | null;
}

function ProgressLayer({
  label,
  widthPct,
  color,
  opacity,
  rightLabel,
  ratioLabel,
}: ProgressLayerProps) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-20 shrink-0 text-[0.6875rem] font-bold text-muted-foreground">
        {label}
      </span>
      <div className="flex-1 h-2.5 rounded-full bg-secondary overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{
            width: `${Math.max(0, Math.min(100, widthPct)).toFixed(2)}%`,
            backgroundColor: color,
            opacity,
          }}
        />
      </div>
      <span className="w-24 shrink-0 text-right text-[0.75rem] font-black tabular-nums tracking-tighter text-foreground">
        {rightLabel}
        {ratioLabel && (
          <span className="ml-1 text-[0.625rem] font-bold text-muted-foreground">
            ({ratioLabel})
          </span>
        )}
      </span>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// DIMENSIONS — Hero KPI 카드 4개 (winner 동 peak 4 카테고리)
// ─────────────────────────────────────────────────────────────────────────────

interface DimensionPeak {
  label: string;
  value: number; // 0~1
}

/** prefix 또는 정확 매칭으로 가장 높은 비율 차원 1개 추출.
 *  age_* / gender_* / time_* / weekday|weekend 등 키 변형 대응. */
function getPeakDimension(
  segment: CustomerSegment | null,
  matchers: { prefixes: string[]; exactKeys: string[] },
): DimensionPeak | null {
  if (!segment?.dimension_ratios) return null;
  const filtered = Object.entries(segment.dimension_ratios).filter(([k]) => {
    if (matchers.exactKeys.includes(k)) return true;
    return matchers.prefixes.some((p) => k.startsWith(p));
  });
  if (filtered.length === 0) return null;
  filtered.sort((a, b) => b[1] - a[1]);
  const [key, value] = filtered[0]!;
  return { label: DIMENSION_LABEL[key] ?? key, value };
}

const DIMENSION_CATEGORIES: Array<{
  category: string;
  matchers: { prefixes: string[]; exactKeys: string[] };
}> = [
  {
    category: '연령',
    matchers: { prefixes: ['age_'], exactKeys: [] },
  },
  {
    category: '성별',
    matchers: {
      prefixes: ['gender_'],
      exactKeys: ['male', 'female', 'male_ratio', 'female_ratio'],
    },
  },
  {
    category: '시간대',
    matchers: { prefixes: ['time_'], exactKeys: [] },
  },
  {
    category: '요일',
    matchers: {
      prefixes: [],
      exactKeys: ['weekday', 'weekend', 'weekday_ratio', 'weekend_ratio'],
    },
  },
];

function DimensionsHeroCards({
  sorted,
  winnerDistrict,
}: {
  sorted: DistrictPredictionResult[];
  winnerDistrict: string;
}) {
  // chip selector — 기본 선택: winner. 클릭 시 selectedDistrict 전환.
  const [selectedDistrict, setSelectedDistrict] = useState(winnerDistrict);

  const selectedPred = sorted.find((p) => p.district === selectedDistrict) ?? sorted[0]!;
  const selectedSegment = (selectedPred.customer_segment as CustomerSegment | null) ?? null;
  const selectedIdx = sorted.findIndex((p) => p.district === selectedPred.district);
  const selectedColor = SERIES_COLORS[selectedIdx % SERIES_COLORS.length]!;

  // 모든 동 segment null 이면 PlaceholderPanel
  const anySegment = sorted.some((p) => p.customer_segment != null);
  if (!anySegment) {
    return (
      <PlaceholderPanel
        modelName="customer_segment"
        description="모든 동에서 타겟 차원 데이터 미수신 — chip 입력 후 재분석 시 활성화됩니다."
      />
    );
  }

  const peaks = DIMENSION_CATEGORIES.map((c) => ({
    category: c.category,
    peak: getPeakDimension(selectedSegment, c.matchers),
  }));

  return (
    <div className="space-y-4">
      {/* ── chip selector — 4동 chip 가로 (ranking 순). 동별 색 dot. winner 기본 선택. ── */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[0.625rem] font-black uppercase tracking-widest text-muted-foreground">
          타겟 동
        </span>
        {sorted.map((p, idx) => {
          const isSelected = p.district === selectedDistrict;
          const isWinner = p.district === winnerDistrict;
          const chipColor = SERIES_COLORS[idx % SERIES_COLORS.length]!;
          return (
            <button
              key={p.district}
              type="button"
              onClick={() => setSelectedDistrict(p.district)}
              className={[
                'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[0.75rem] font-bold tracking-tight transition-colors',
                isSelected
                  ? 'border-foreground bg-foreground text-background'
                  : 'border-border bg-card text-foreground hover:bg-secondary',
              ].join(' ')}
            >
              <span
                aria-hidden
                className="size-2 shrink-0 rounded-full"
                style={{ backgroundColor: chipColor }}
              />
              <span>{p.district}</span>
              {isWinner && (
                <span
                  className={[
                    'rounded-full px-1.5 py-0.5 text-[0.5rem] font-black uppercase tracking-widest',
                    isSelected ? 'bg-background/20 text-background' : 'bg-primary/10 text-primary',
                  ].join(' ')}
                >
                  Winner
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* ── 선택된 동의 peak profile 카드 4 (연령·성별·시간대·요일) ── */}
      {selectedSegment ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {peaks.map(({ category, peak }) => {
            const pct = peak ? peak.value * 100 : 0;
            return (
              <div
                key={category}
                className="rounded-2xl border border-border bg-card p-4 space-y-3"
              >
                <div className="text-[0.625rem] font-black uppercase tracking-widest text-muted-foreground">
                  {category}
                </div>
                {peak ? (
                  <>
                    <div className="text-2xl font-black tracking-tight text-foreground leading-none">
                      {peak.label}
                    </div>
                    <div
                      className="text-3xl font-black tabular-nums tracking-tighter leading-none"
                      style={{ color: selectedColor }}
                    >
                      {pct.toFixed(1)}
                      <span className="ml-0.5 text-base text-muted-foreground">%</span>
                    </div>
                    <div className="w-full h-1.5 bg-muted overflow-hidden rounded-full">
                      <div
                        className="h-full transition-all"
                        style={{
                          width: `${Math.min(100, pct).toFixed(2)}%`,
                          backgroundColor: selectedColor,
                        }}
                      />
                    </div>
                  </>
                ) : (
                  <div className="text-xs text-muted-foreground">차원 데이터 없음</div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-border bg-card p-8 text-center">
          <p className="text-xs text-muted-foreground">{selectedDistrict} 타겟 차원 데이터 없음</p>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// 메인 export
// ─────────────────────────────────────────────────────────────────────────────

export function CustomerFlowSegmentChart({ dpredicts, mode, simResult }: Props) {
  // ranking 정렬 (winner→4위)
  const sorted = sortByRanking(dpredicts, simResult);
  const winnerDistrict = simResult.winner_district ?? sorted[0]!.district;

  if (mode === 'sales') {
    const anySales = sorted.some((p) => p.customer_segment != null);
    if (!anySales) {
      return (
        <PlaceholderPanel
          modelName="customer_segment"
          description="모든 동에서 타겟 매출 데이터 미수신"
        />
      );
    }
    return <SalesNestedProgress sorted={sorted} winnerDistrict={winnerDistrict} />;
  }

  // mode === 'dimensions' — chip selector + 선택된 동의 peak profile (winner 기본)
  return <DimensionsHeroCards sorted={sorted} winnerDistrict={winnerDistrict} />;
}
