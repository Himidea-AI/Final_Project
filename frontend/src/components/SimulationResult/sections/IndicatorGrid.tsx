import { useMemo, useState } from 'react';
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import type { SimulationOutput, DistrictRanking } from '../../../types';
import { SERIES_COLORS } from '../QuarterlyProjectionChart';
import { SectionLabel } from '../shared/SectionLabel';

interface Props {
  simResult: SimulationOutput;
}

// scale: 백엔드 원본 단위 → 0~100 렌더 단위 변환 배수. closure_rate 만 0~1 fraction.
const INDICATORS: Array<{
  key: string;
  label: string;
  shortLabel: string;
  color: string;
  scale?: number;
}> = [
  { key: 'floating_population', label: '유동인구', shortLabel: '유동', color: 'bg-primary' },
  { key: 'rent_index', label: '임대료 지수', shortLabel: '임대', color: 'bg-primary' },
  { key: 'competition_intensity', label: '경쟁강도', shortLabel: '경쟁', color: 'bg-danger' },
  { key: 'estimated_revenue', label: '예상 매출', shortLabel: '매출', color: 'bg-success' },
  { key: 'survival_rate', label: '생존율', shortLabel: '생존', color: 'bg-primary' },
  { key: 'closure_rate', label: '폐업률', shortLabel: '폐업', color: 'bg-danger', scale: 100 },
  { key: 'growth_potential', label: '성장 잠재력', shortLabel: '성장', color: 'bg-primary' },
  { key: 'accessibility', label: '접근성', shortLabel: '접근', color: 'bg-primary' },
] as const;

// null 시 중립 회색 — 0 fallback 회피(거짓 양성 방지, api-contract §3.7).
function scoreColor(v: number | null): string {
  if (v == null) return 'text-muted-foreground';
  if (v >= 70) return 'text-success';
  if (v >= 45) return 'text-warning';
  return 'text-danger';
}

function scoreBorder(v: number | null): string {
  if (v == null) return 'border-border';
  if (v >= 70) return 'border-success/30';
  if (v >= 45) return 'border-warning/30';
  return 'border-danger/30';
}

function scoreBg(v: number | null): string {
  if (v == null) return 'bg-muted';
  if (v >= 70) return 'bg-success/10';
  if (v >= 45) return 'bg-warning/10';
  return 'bg-danger/10';
}

function barColor(v: number): string {
  if (v >= 70) return 'bg-success';
  if (v >= 45) return 'bg-warning';
  return 'bg-danger';
}

export function IndicatorGrid({ simResult }: Props) {
  const report = simResult.market_report;
  const winnerDistrict = simResult.winner_district ?? null;

  // 시뮬한 동 list (winner + top_3_candidates 순서, 중복 제거).
  // backend 가 다른 동의 market_report 를 채우지 않으므로 winner 외 동 선택 시 district_rankings 폴백.
  const districtOrder = useMemo<string[]>(() => {
    const top3 = simResult.top_3_candidates ?? [];
    const arr: string[] = [];
    if (winnerDistrict) arr.push(winnerDistrict);
    for (const d of top3) {
      if (d && !arr.includes(d)) arr.push(d);
    }
    return arr;
  }, [winnerDistrict, simResult.top_3_candidates]);

  const [selectedDistrict, setSelectedDistrict] = useState<string | null>(winnerDistrict);
  const effectiveSelected = selectedDistrict ?? winnerDistrict ?? districtOrder[0] ?? null;
  const isWinnerSelected = effectiveSelected === winnerDistrict;

  // district_rankings → 8 지표 부분 매핑 (winner 외 동용).
  // backend 가 winner 만 market_report 풀 8 지표 채우므로, 다른 동은 district_rankings 의 5 지표만 가능.
  const selectedRanking = useMemo(
    () => simResult.district_rankings?.find((r) => r.district === effectiveSelected) ?? null,
    [simResult.district_rankings, effectiveSelected],
  );

  if (!report && districtOrder.length === 0) {
    return (
      <section>
        <SectionLabel label="INDICATOR GRID" subtitle="8개 핵심 상권 지표" />
        <div className="rounded-lg border border-border bg-card p-6 text-center text-sm text-muted-foreground">
          상권 지표 데이터 없음
        </div>
      </section>
    );
  }

  // 선택 동의 8 지표 추출 — winner 면 market_report 풀, 아니면 district_rankings 의
  // 동별 점수 필드(0~100 정규화, 16동 비교 가능) 로 매핑. 모든 동 8지표 표시 가능.
  // 주의: winner 의 market_report 8지표와 다른 동의 ranking 점수는 산식이 다르므로
  //   직접 비교는 신중. 화면엔 안내 문구로 명시.
  // closure_rate 은 0~1 fraction 이라 scale: 100 적용 후 0~100 점수화.
  // survival_rate 는 winner 외 동에선 100 - closure_rate*100 으로 역산.
  const values = INDICATORS.map(({ key, label, shortLabel, scale }) => {
    let rawVal: unknown = null;
    let appliedScale: number | undefined = scale;
    if (isWinnerSelected && report) {
      rawVal = (report as Record<string, unknown>)[key];
    } else if (selectedRanking) {
      // 동별 점수 매핑 — DistrictRanking (backend district_ranking_node) 의 0~100 점수 필드.
      // keyof DistrictRanking 가 인덱스 시그니처로 string|number|symbol 이 되어 string 으로 좁힘.
      const rankingMap: Record<string, Extract<keyof DistrictRanking, string>> = {
        floating_population: 'pop_score',
        rent_index: 'rent_score',
        competition_intensity: 'density_score',
        estimated_revenue: 'sales_score',
        growth_potential: 'trend_score',
        accessibility: 'inflow_score',
        closure_rate: 'closure_rate',
      };
      const rankingKey = rankingMap[key];
      if (rankingKey) {
        rawVal = (selectedRanking as Record<string, unknown>)[rankingKey] ?? null;
      } else if (key === 'survival_rate') {
        // ranking 응답엔 survival_rate 가 없어 closure_rate (0~1 fraction) 으로 역산.
        const cr = selectedRanking.closure_rate;
        if (typeof cr === 'number' && Number.isFinite(cr)) {
          rawVal = 100 - cr * 100;
          appliedScale = undefined; // 이미 0~100 으로 변환됨
        }
      }
    }
    if (typeof rawVal !== 'number' || !Number.isFinite(rawVal)) {
      return { key, label, shortLabel, val: null as number | null };
    }
    const scaled = appliedScale ? rawVal * appliedScale : rawVal;
    return { key, label, shortLabel, val: Math.max(0, Math.min(100, scaled)) };
  });

  const missingCount = values.filter((v) => v.val == null).length;

  // radar — null인 축은 0으로 그리지 않고 polygon에서 제외 (찌그러짐 방지).
  const radarData = values
    .filter((v) => v.val != null)
    .map(({ shortLabel, val }) => ({
      subject: shortLabel,
      value: val,
      fullMark: 100,
    }));

  return (
    <section>
      {/* 헤더 row — SectionLabel + 동 chip selector (시뮬 1~4동, winner 첫번째). */}
      <div className="mb-3 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <SectionLabel label="INDICATOR GRID" subtitle="8개 핵심 상권 지표" />
        {districtOrder.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[0.625rem] font-black uppercase tracking-widest text-muted-foreground">
              동 선택
            </span>
            {districtOrder.map((d, idx) => {
              const isSelected = d === effectiveSelected;
              const isWinner = d === winnerDistrict;
              const chipColor = SERIES_COLORS[idx % SERIES_COLORS.length]!;
              return (
                <button
                  key={d}
                  type="button"
                  onClick={() => setSelectedDistrict(d)}
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
                  <span>{d}</span>
                  {isWinner && (
                    <span
                      className={[
                        'rounded-full px-1.5 py-0.5 text-[0.5rem] font-black uppercase tracking-widest',
                        isSelected
                          ? 'bg-background/20 text-background'
                          : 'bg-primary/10 text-primary',
                      ].join(' ')}
                    >
                      Winner
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* winner 외 동 안내 — 점수 산식이 winner 와 다름을 명시. */}
      {!isWinnerSelected && (
        <div className="mb-3 rounded-md border border-warning/30 bg-warning/10 px-3 py-2 text-[0.6875rem] text-warning">
          ※ {effectiveSelected}: 16동 정규화 점수 (district_ranking) 기반.
          {winnerDistrict ?? '—'} 의 실측 시뮬 결과와는 산식이 달라 직접 비교는 참고용.
          {missingCount > 0 && ` (결측 ${missingCount}개)`}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[1fr_auto]">
        {/* KPI 카드 그리드 — 라벨(truncate) / 큰 숫자(우측 끝부분 미간 회피) / progress bar.
            "/100" 텍스트는 progress bar가 0~100을 시각화하므로 중복 → 제거(좁은 박스 깨짐 방지). */}
        {/* 2×4 가로 박스 — 박스당 폭 2배 확보로 모든 라벨 한 줄에 들어감.
            라벨 좌 / 숫자 우 (justify-between baseline align), bar 아래 풀폭. */}
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {values.map(({ key, label, val }) => (
            <div key={key} className={`rounded-lg border p-3 ${scoreBorder(val)} ${scoreBg(val)}`}>
              <div className="flex items-baseline justify-between gap-3">
                <div className="text-[0.6875rem] uppercase tracking-wide text-muted-foreground">
                  {label}
                </div>
                <div
                  className={`text-2xl font-bold font-mono tabular-nums leading-none ${scoreColor(val)}`}
                >
                  {val == null ? '—' : Math.round(val)}
                </div>
              </div>
              <div className="mt-2.5 h-1 w-full rounded-full bg-muted">
                {val != null && (
                  <div
                    className={`h-full rounded-full ${barColor(val)}`}
                    style={{ width: `${val}%` }}
                  />
                )}
              </div>
            </div>
          ))}
        </div>

        {/* 레이더 차트 — w-72(288px) → w-60(240px)로 줄여 좌측 KPI 그리드 공간 확보 */}
        <div className="flex items-center justify-center rounded-lg border border-border bg-card p-4 lg:w-60">
          <ResponsiveContainer width="100%" height={220}>
            <RadarChart data={radarData} margin={{ top: 10, right: 20, bottom: 10, left: 20 }}>
              <PolarGrid stroke="var(--border)" />
              <PolarAngleAxis
                dataKey="subject"
                tick={{ fill: 'var(--muted-foreground)', fontSize: 10, fontWeight: 600 }}
              />
              <Radar
                dataKey="value"
                stroke="var(--primary)"
                fill="var(--primary)"
                fillOpacity={0.15}
                strokeWidth={1.5}
              />
              <Tooltip
                contentStyle={{
                  background: 'var(--card)',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  fontSize: 12,
                  color: 'var(--card-foreground)',
                }}
                formatter={(v: number) => [Math.round(v), '점수']}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* AgentCard 3개(market/population/ranking)는 MarketTab의 full-width row로 분리 —
          좁은 컬럼에서 size="full" 카드가 깨지던 문제 해소 (2026-04-28). */}
    </section>
  );
}
