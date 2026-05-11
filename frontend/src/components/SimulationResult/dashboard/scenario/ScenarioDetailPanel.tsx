/**
 * ScenarioDetailPanel — 시나리오 시뮬 단일 패널 (2026-05-03 v2 재구조).
 *
 * 헤더: 동 드롭다운 (4동 한정) + × + 업종 텍스트 + 우측 슬라이더 초기화 버튼
 *
 * 본문 구성 (위→아래):
 *   1. 헤더 (동 드롭다운 + 업종 + 리셋 버튼)
 *   2. KpiHero (총 변화율 / 분기 평균 매출 / 기준선 대비 차이)
 *   3. 합산 안내 문구 (명세서 §4.3)
 *   4. 좌(슬라이더) / 우(차트) split — lg:grid-cols-[280px_1fr]
 *      - 좌측: what-if 변수 chip × 4 + PctElasticitySlider × 4 + QuarterTab
 *      - 우측: ScenarioForecastChart (delta / quarter 토글)
 *   5. CorrelationInsightCard
 *
 * 모바일 (lg-): stack — 슬라이더 위, 차트 아래.
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
import { selectPerStoreBaseline } from './baseline';
import { DropdownSelect } from '../../../ui/DropdownSelect';

const elasticityKey = (v: number): string => (v > 0 ? `+${v}` : String(v));

const formatKrw = (value: number): string => {
  const abs = Math.abs(value);
  if (abs >= 100_000_000) return `${(value / 100_000_000).toFixed(1)}억`;
  if (abs >= 10_000) return `${Math.round(value / 10_000).toLocaleString('ko-KR')}만`;
  return `${Math.round(value).toLocaleString('ko-KR')}`;
};

interface Props {
  candidate: ScenarioCandidate;
  data: SensitivityResponse | null;
  loading: boolean;
  error: Error | null;
  onSliderChange: (key: keyof CandidateSliderState, value: number | QuarterKey) => void;
  onReset: () => void;
  /** 4동 한정 드롭다운 옵션. */
  availableDongs: { name: string; code: string }[];
  /** 헤더 동 드롭다운 변경 핸들러. */
  onChangeDong: (newDong: string) => void;
}

export function ScenarioDetailPanel({
  candidate,
  data,
  loading,
  error,
  onSliderChange,
  onReset,
  availableDongs,
  onChangeDong,
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

  // 동 드롭다운 옵션 = 시뮬 입력 4동 한정.
  // sessionStorage 잔존 후보의 invalid dong 은 부모 effect (PredictScenarioSimTab)
  // 가 자동으로 첫 동으로 update 하므로 fallback 옵션 불필요.
  const dongOptions = availableDongs.map((d) => d.name);

  // 통합 헤더+KPI 박스 inner — 헤더 row + (result 있을 때) KPI row.
  // 우측 컬럼 상단에 위치, loading/error 시에도 헤더는 항상 표시.
  // 헤더는 inner content 만 (외부 chrome 은 통합 박스가 가짐).
  const headerInner = (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-3">
        <DropdownSelect
          value={candidate.dong}
          onChange={onChangeDong}
          options={dongOptions}
          ariaLabel="동 선택"
          compact
        />
        <span className="text-sm text-muted-foreground">×</span>
        <span className="text-sm font-bold text-foreground">{candidate.industry}</span>
      </div>
      <button
        type="button"
        onClick={onReset}
        className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-border bg-card px-3 text-xs font-bold text-foreground transition-colors hover:border-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1"
      >
        <RotateCcw size={12} /> 슬라이더 초기화
      </button>
    </div>
  );

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

  // 우측 컬럼 통합 헤더+KPI 박스 — 한 chrome 안 두 영역 (헤더 + KPI), divider 로 분리.
  // 사용자 요청 (2026-05-04): 동×업종+리셋 박스와 KPI 박스를 우측 상단에 통합 + 좌측 슬라이더는 위로 올림.
  const headerKpiBox = (
    <div className="rounded-3xl border border-border bg-card p-5 space-y-4">
      {headerInner}
      {result && (
        <>
          <div className="grid grid-cols-1 gap-3 border-t border-border pt-4 sm:grid-cols-3">
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
          <p className="text-[0.625rem] text-muted-foreground">
            합계 표시 = 점포당 연 매출 (4분기 합) · 분기 값 ÷ 3 = 월 환산
          </p>
        </>
      )}
    </div>
  );

  // loading 상태 — 좌측 슬라이더는 그대로 (조작 가능), 우측은 헤더 박스 + skeleton 차트
  if (loading) {
    return (
      <section className="space-y-4">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_1fr]">
          <aside className="space-y-4">
            <h4 className="flex items-center gap-2 px-1 text-base font-black tracking-tight text-foreground">
              시뮬레이션 변수 조절
            </h4>
            <p className="text-[0.6875rem] text-muted-foreground">로드 중…</p>
          </aside>
          <div className="space-y-4">
            {headerKpiBox}
            <DetailSkeletonBody />
          </div>
        </div>
      </section>
    );
  }

  // error 상태 — 우측 통합 박스 + error 안내. 좌측 hide.
  if (error || !data) {
    return (
      <section className="space-y-4">
        {headerKpiBox}
        <div className="rounded-3xl border border-dashed border-border bg-secondary/40 p-8 text-center">
          <p className="text-sm font-bold text-foreground">데이터 로드 실패</p>
          <p className="mt-2 text-[0.6875rem] text-muted-foreground">
            {error?.message ?? '잠시 후 다시 시도하세요.'}
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="space-y-4">
      {/* 좌(슬라이더) / 우(통합 헤더+KPI + 합산안내 + 차트) split.
          좌측 슬라이더가 위에서부터 시작 (사용자 요청 — 상단 빈 공간 채움).
          퐁당퐁당 룰: 좌측 aside chrome 없음, 내부 슬라이더 4 + QuarterTab 각자 카드. */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_1fr]">
        {/* 좌측 — what-if 변수 조정 (bare, 위에서 시작) */}
        <aside className="space-y-3">
          <h4 className="px-1 text-[0.625rem] font-black uppercase tracking-widest text-muted-foreground">
            시뮬레이션 변수 조절
          </h4>

          {/* 액티브 슬라이더 chip × 4 (delta 모드 차트의 7-tier 표시 대상 선택).
              4 chip 한 줄 균등 배치 — flex-1 로 컬럼 폭(280px) 4등분, 폰트·패딩 키워 공백 흡수. */}
          <div className="flex flex-nowrap gap-1.5">
            {PCT_SLIDER_KEYS.map((k) => (
              <button
                key={k}
                type="button"
                onClick={() => setActiveSlider(k)}
                title={SLIDER_TOOLTIPS[k]}
                className={`flex-1 whitespace-nowrap rounded-full border px-1 py-1.5 text-center text-[0.6875rem] font-bold transition-colors ${
                  activeSlider === k
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border bg-card text-muted-foreground hover:border-primary/40'
                }`}
              >
                {SLIDER_LABELS[k]}
              </button>
            ))}
          </div>

          {/* 슬라이더 4개 */}
          <div className="space-y-3">
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
          </div>
        </aside>

        {/* 우측 — 통합 헤더+KPI + 합산 안내 + 차트 (flex-col + 차트 flex-1 으로 좌측 height 자동 정합) */}
        <div className="flex flex-col gap-4">
          {headerKpiBox}

          {/* 합산 안내 문구 */}
          <p className="px-1 text-[0.625rem] leading-relaxed text-muted-foreground">
            ※ 여러 슬라이더의 영향은 단순 합산입니다. 실제 시장에서는 변수 간 상호작용이 있을 수
            있습니다.
          </p>

          {/* 차트 — flex-1 로 grid row 의 남은 height 채움 (좌측 슬라이더 컬럼과 자동 정합) */}
          <div className="flex flex-1 flex-col rounded-3xl border border-border bg-card p-5">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h4 className="text-[0.6875rem] font-black uppercase tracking-widest text-muted-foreground">
                  점포당 분기 매출 (원)
                </h4>
                <p className="mt-1 text-[0.625rem] text-muted-foreground">
                  좌측 슬라이더 조정 → 4분기 매출 변화 시뮬
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

            <div className="flex-1">
              <ScenarioForecastChart
                data={data}
                mode={chartMode}
                activeSlider={chartMode === 'delta' ? activeSlider : null}
                combined={result ? { values: result.adjusted, label: '현재 슬라이더 합산' } : null}
                height="100%"
              />
            </div>

            <p className="mt-2 text-right text-[0.5625rem] text-muted-foreground">
              *업종 평균 점포 1개 기준
            </p>
          </div>
        </div>
      </div>
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

function DetailSkeletonBody() {
  return (
    <>
      <div className="h-28 rounded-3xl bg-secondary/60 animate-pulse" aria-hidden="true" />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_1fr]">
        <div className="h-96 rounded-3xl bg-secondary/60 animate-pulse" aria-hidden="true" />
        <div className="h-96 rounded-3xl bg-secondary/60 animate-pulse" aria-hidden="true" />
      </div>
      <div className="h-32 rounded-3xl bg-secondary/60 animate-pulse" aria-hidden="true" />
    </>
  );
}
