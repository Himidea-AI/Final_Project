/**
 * ScenarioDetailPanel — Master-Detail 우측 드릴다운.
 *
 * 구성 (위→아래):
 *   1. 후보 헤더 (동 × 업종 + 액티브 슬라이더 토글)
 *   2. KpiHero (총 변화율 / 분기 평균 매출 / 기준선 대비 차이)
 *   3. 합산 안내 문구 (명세서 §4.3)
 *   4. ScenarioForecastChart (delta 모드 = 액티브 슬라이더 7-tier + combined / quarter 모드 = Q1~Q4)
 *   5. 보조 문구 "*업종 평균 점포 1개 기준"
 *   6. PctElasticitySlider × 4 (vacancy_rate / trend_score / cpi_index / opr_sale_mt_avg)
 *   7. QuarterTab (4-탭 Q1/Q2/Q3/Q4)
 *   8. CorrelationInsightCard
 */

import { useMemo, useState } from 'react';
import { RotateCcw } from 'lucide-react';
import {
  PCT_SLIDER_KEYS,
  SLIDER_LABELS,
  SLIDER_TOOLTIPS,
  type PctSliderKey,
  type QuarterKey,
  type SensitivityResponse,
} from '../../../../types/elasticity';
import type {
  ScenarioCandidate,
  CandidateSliderState,
} from '../../../../hooks/useScenarioCandidates';
import { ScenarioForecastChart } from './ScenarioForecastChart';
import { PctElasticitySlider } from './PctElasticitySlider';
import { CorrelationInsightCard } from './CorrelationInsightCard';
import { selectPerStoreBaseline } from './baseline';

const elasticityKey = (v: number): string => (v > 0 ? `+${v}` : String(v));

const formatKrw = (value: number): string => {
  const abs = Math.abs(value);
  if (abs >= 100_000_000) return `${(value / 100_000_000).toFixed(1)}억`;
  if (abs >= 10_000) return `${Math.round(value / 10_000).toLocaleString('ko-KR')}만`;
  return `${Math.round(value).toLocaleString('ko-KR')}`;
};

const QUARTERS: QuarterKey[] = ['Q1', 'Q2', 'Q3', 'Q4'];

interface Props {
  candidate: ScenarioCandidate;
  data: SensitivityResponse | null;
  loading: boolean;
  error: Error | null;
  onSliderChange: (key: keyof CandidateSliderState, value: number | QuarterKey) => void;
  onReset: () => void;
}

export function ScenarioDetailPanel({
  candidate,
  data,
  loading,
  error,
  onSliderChange,
  onReset,
}: Props) {
  const [activeSlider, setActiveSlider] = useState<PctSliderKey>('vacancy_rate');
  const [chartMode, setChartMode] = useState<'delta' | 'quarter'>('delta');

  // 4 슬라이더 합산 → 4분기 % 결합
  const result = useMemo(() => {
    if (!data) return null;
    const baseline = selectPerStoreBaseline(data);
    const combinedPct: number[] = [0, 0, 0, 0];
    for (const k of PCT_SLIDER_KEYS) {
      const lvl = candidate.sliders[k];
      const key = elasticityKey(lvl);
      const arr = data.elasticity[k]?.[key] ?? data.elasticity[k]?.[String(lvl)] ?? null;
      if (Array.isArray(arr)) {
        for (let q = 0; q < 4; q++) {
          if (Number.isFinite(arr[q])) combinedPct[q] += arr[q];
        }
      }
    }
    const adjusted = baseline.map((s, q) => s * (1 + combinedPct[q] / 100));
    const baselineTotal = baseline.reduce((s, v) => s + v, 0);
    const adjustedTotal = adjusted.reduce((s, v) => s + v, 0);
    const totalDeltaPct =
      baselineTotal > 0 ? ((adjustedTotal - baselineTotal) / baselineTotal) * 100 : 0;
    const quarterAvg = adjusted.length > 0 ? adjustedTotal / adjusted.length : 0;
    return {
      adjusted,
      combinedPct,
      baselineTotal,
      adjustedTotal,
      totalDeltaPct,
      quarterAvg,
      diff: adjustedTotal - baselineTotal,
    };
  }, [data, candidate.sliders]);

  if (loading) {
    return <DetailSkeleton />;
  }

  if (error || !data) {
    return (
      <section className="flex-1 rounded-3xl border border-dashed border-border bg-secondary/40 p-8 text-center">
        <p className="text-sm font-bold text-foreground">데이터 로드 실패</p>
        <p className="mt-2 text-[0.6875rem] text-muted-foreground">
          {error?.message ?? '잠시 후 다시 시도하세요.'}
        </p>
      </section>
    );
  }

  const deltaTone =
    (result?.totalDeltaPct ?? 0) > 0
      ? 'text-success'
      : (result?.totalDeltaPct ?? 0) < 0
        ? 'text-danger'
        : 'text-muted-foreground';
  const diffTone =
    (result?.diff ?? 0) > 0
      ? 'text-success'
      : (result?.diff ?? 0) < 0
        ? 'text-danger'
        : 'text-muted-foreground';

  return (
    <section className="flex-1 space-y-4">
      {/* 1. 헤더 */}
      <header className="flex items-start justify-between gap-3 rounded-3xl border border-border bg-card p-5">
        <div>
          <h3 className="text-lg font-black tracking-tight text-foreground">
            {candidate.dong} <span className="text-muted-foreground">×</span> {candidate.industry}
          </h3>
          <p className="mt-1 text-[0.6875rem] text-muted-foreground">
            점포당 분기 매출 (원) · *업종 평균 점포 1개 기준
          </p>
        </div>
        <button
          type="button"
          onClick={onReset}
          className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-border bg-card px-3 text-xs font-bold text-foreground transition-colors hover:border-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1"
        >
          <RotateCcw size={12} /> 리셋
        </button>
      </header>

      {/* 2. KpiHero */}
      {result && (
        <div className="rounded-3xl border border-border bg-card p-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <KpiCell
              label="총 변화율"
              value={`${result.totalDeltaPct >= 0 ? '+' : ''}${result.totalDeltaPct.toFixed(1)}%`}
              tone={deltaTone}
            />
            <KpiCell
              label="분기 평균 매출"
              value={`₩${formatKrw(Math.round(result.quarterAvg))}`}
            />
            <KpiCell
              label="기준선 대비 차이"
              value={`${result.diff >= 0 ? '+' : ''}₩${formatKrw(Math.round(Math.abs(result.diff)))}`}
              tone={diffTone}
            />
          </div>
          <p className="mt-3 text-[0.625rem] text-muted-foreground">
            합계 표시 = 점포당 연 매출 (4분기 합) · 분기 값 ÷ 3 = 월 환산
          </p>
        </div>
      )}

      {/* 3. 차트 (with 합산 안내 문구) */}
      <div className="rounded-3xl border border-border bg-card p-6">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h4 className="text-[0.6875rem] font-black uppercase tracking-widest text-muted-foreground">
              점포당 분기 매출 (원)
            </h4>
            <p className="mt-1 text-[0.625rem] text-muted-foreground">
              ※ 여러 슬라이더의 영향은 단순 합산입니다. 실제 시장에서는 변수 간 상호작용이 있을 수
              있습니다.
            </p>
          </div>
          <div className="flex items-center gap-1 rounded-lg border border-border p-0.5">
            <ModeButton
              active={chartMode === 'delta'}
              onClick={() => setChartMode('delta')}
              label="섭동 7-tier"
            />
            <ModeButton
              active={chartMode === 'quarter'}
              onClick={() => setChartMode('quarter')}
              label="분기(Q1~Q4)"
            />
          </div>
        </div>

        {chartMode === 'delta' && (
          <div className="mb-3 flex flex-wrap gap-1.5">
            {PCT_SLIDER_KEYS.map((k) => (
              <button
                key={k}
                type="button"
                onClick={() => setActiveSlider(k)}
                className={`rounded-full border px-2.5 py-1 text-[0.625rem] font-bold transition-colors ${
                  activeSlider === k
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border bg-card text-muted-foreground hover:border-primary/40'
                }`}
                title={SLIDER_TOOLTIPS[k]}
              >
                {SLIDER_LABELS[k]}
              </button>
            ))}
          </div>
        )}

        <ScenarioForecastChart
          data={data}
          mode={chartMode}
          activeSlider={chartMode === 'delta' ? activeSlider : null}
          combined={result ? { values: result.adjusted, label: '현재 슬라이더 합산' } : null}
          height={320}
        />

        <p className="mt-2 text-right text-[0.5625rem] text-muted-foreground">
          *업종 평균 점포 1개 기준
        </p>
      </div>

      {/* 4. 슬라이더 4 + Quarter Tab */}
      <div className="rounded-3xl border border-border bg-card p-6 space-y-3">
        <h4 className="text-[0.6875rem] font-black uppercase tracking-widest text-muted-foreground">
          What-if 변수 조정
        </h4>
        {PCT_SLIDER_KEYS.map((k) => {
          const level = candidate.sliders[k];
          const arr = data.elasticity[k]?.[elasticityKey(level)] ??
            data.elasticity[k]?.[String(level)] ?? [0, 0, 0, 0];
          return (
            <PctElasticitySlider
              key={k}
              sliderKey={k}
              label={SLIDER_LABELS[k]}
              value={level}
              onChange={(next) => onSliderChange(k, next)}
              quarterDeltas={arr}
            />
          );
        })}

        {/* Quarter 4-tab */}
        <div className="rounded-2xl border border-border bg-secondary/40 p-4">
          <div className="flex items-center justify-between">
            <span
              className="text-xs font-black tracking-tight text-foreground"
              title={SLIDER_TOOLTIPS.quarter_num}
            >
              {SLIDER_LABELS.quarter_num}
            </span>
            <span className="text-[0.5625rem] font-bold text-muted-foreground">
              관측 시작 분기 (categorical, 합산 제외)
            </span>
          </div>
          <div className="mt-2 grid grid-cols-4 gap-1">
            {QUARTERS.map((q) => {
              const active = candidate.sliders.quarter_num === q;
              return (
                <button
                  key={q}
                  type="button"
                  onClick={() => onSliderChange('quarter_num', q)}
                  aria-pressed={active}
                  className={`rounded-lg border px-2 py-2 text-xs font-black transition-colors ${
                    active
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border bg-card text-foreground hover:border-primary/40'
                  }`}
                >
                  {q}
                </button>
              );
            })}
          </div>
          <p className="mt-2 text-[0.5625rem] leading-relaxed text-muted-foreground">
            {SLIDER_TOOLTIPS.quarter_num}
          </p>
        </div>
      </div>

      {/* 5. Correlation */}
      <CorrelationInsightCard correlations={data.correlations} />
    </section>
  );
}

function ModeButton({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-md px-2.5 py-1 text-[0.625rem] font-black transition-colors ${
        active
          ? 'bg-primary text-primary-foreground'
          : 'text-muted-foreground hover:text-foreground'
      }`}
    >
      {label}
    </button>
  );
}

function KpiCell({
  label,
  value,
  tone = 'text-foreground',
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div>
      <div className="text-[0.625rem] font-black uppercase tracking-widest text-muted-foreground">
        {label}
      </div>
      <div className={`mt-1 text-2xl font-black tabular-nums tracking-tighter ${tone}`}>
        {value}
      </div>
    </div>
  );
}

function DetailSkeleton() {
  return (
    <section className="flex-1 space-y-4">
      <div className="h-20 rounded-3xl bg-secondary/60 animate-pulse" aria-hidden="true" />
      <div className="h-28 rounded-3xl bg-secondary/60 animate-pulse" aria-hidden="true" />
      <div className="h-72 rounded-3xl bg-secondary/60 animate-pulse" aria-hidden="true" />
      <div className="h-48 rounded-3xl bg-secondary/60 animate-pulse" aria-hidden="true" />
    </section>
  );
}
