/**
 * PredictScenarioSimTab — TCN 시나리오 시뮬레이터 (What-if 분석).
 *
 * 백엔드: GET /predict/sensitivity?dong_code=&industry_code= (탄성치 + 상관 + baseline_sales)
 *
 * 매출 식: baseline × (1 + Σ(elasticity[feature][slider_pct]/100))  — 4 sliders 선형 결합.
 * quarter_num 은 별도 정보 (기준선에 이미 반영, 표시용 카드).
 *
 * dong_code: 사용자가 dropdown 으로 직접 선택 (16 마포 동). 기본값은 simResult.winner_district
 *            (있고 매핑되면) 또는 첫 동.
 * industry_code: useSimulationStore.params.business_type → BIZ_TO_INDUSTRY_CODE 미러 매핑.
 *
 * simResult 없이도 진입 가능 — params.business_type 만 있으면 OK.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronRight, RotateCcw, Sliders } from 'lucide-react';
import type { SimulationOutput } from '../../../../../types';
import type { ElasticityFeature } from '../../../../../types/elasticity';
import { useElasticity } from '../../../../../hooks/useElasticity';
import { ElasticityNotFoundError } from '../../../../../api/elasticity';
import { resolveBizToIndustry } from '../../../../../constants/bizToIndustry';
import { MAPO_DONGS, resolveDongCode } from '../../../../../constants/mapoDongs';
import { useSimulationStore } from '../../../../../stores/simulationStore';
import { useToastStore } from '../../../../../stores/toastStore';
import { ElasticitySlider } from '../../charts/ElasticitySlider';
import { ScenarioComparisonChart } from '../../charts/ScenarioComparisonChart';

interface Props {
  simResult?: SimulationOutput | null;
}

const FEATURES: { key: ElasticityFeature; label: string }[] = [
  { key: 'floating_pop', label: '유동인구' },
  { key: 'rent_1f', label: '1층 임대료' },
  { key: 'trend_score', label: '트렌드 점수' },
  { key: 'vacancy_rate', label: '공실률' },
];

export const FEATURE_LABELS: Record<ElasticityFeature, string> = {
  floating_pop: '유동인구',
  rent_1f: '1층 임대료',
  trend_score: '트렌드 점수',
  vacancy_rate: '공실률',
};

const STEP = 10;
const MAX_LEVEL = 30;
const MIN_LEVEL = -30;

const roundToStep = (v: number) => Math.round(v / STEP) * STEP;
const clampLevel = (v: number) => Math.max(MIN_LEVEL, Math.min(MAX_LEVEL, roundToStep(v)));

const elasticityKey = (v: number): string => (v > 0 ? `+${v}` : String(v));

const INITIAL_VALUES: Record<ElasticityFeature, number> = {
  floating_pop: 0,
  rent_1f: 0,
  trend_score: 0,
  vacancy_rate: 0,
};

const FEATURE_SET = new Set<ElasticityFeature>(FEATURES.map((f) => f.key));

interface PeerCorrelation {
  peer: ElasticityFeature;
  r: number;
}

/** correlations dict 에서 주어진 feature 의 peer 목록 추출 ("a→b" 양방향 모두 매칭). */
function extractPeers(
  feature: ElasticityFeature,
  correlations: Record<string, number>,
): PeerCorrelation[] {
  const peers: PeerCorrelation[] = [];
  for (const [key, r] of Object.entries(correlations)) {
    const [a, b] = key.split('→');
    if (!a || !b) continue;
    if (a === feature && FEATURE_SET.has(b as ElasticityFeature)) {
      peers.push({ peer: b as ElasticityFeature, r });
    } else if (b === feature && FEATURE_SET.has(a as ElasticityFeature)) {
      peers.push({ peer: a as ElasticityFeature, r });
    }
  }
  return peers;
}

export function PredictScenarioSimTab({ simResult }: Props) {
  // dong_code — 사용자 dropdown 직접 선택. 기본값: simResult.winner_district (있고 매핑되면) → fallback 첫 동.
  const winnerDistrict = simResult?.winner_district ?? null;
  const initialDong =
    winnerDistrict && MAPO_DONGS.some((d) => d.name === winnerDistrict)
      ? winnerDistrict
      : MAPO_DONGS[0].name;
  const [selectedDong, setSelectedDong] = useState<string>(initialDong);

  const dongCode = resolveDongCode(selectedDong);

  // industry_code — store.params.business_type 미러 매핑 (simResult 와 무관).
  const businessType = useSimulationStore((s) => s.params?.business_type ?? null);
  const industryCode = resolveBizToIndustry(businessType);

  const { data, error, loading } = useElasticity(dongCode, industryCode);

  const [sliderValues, setSliderValues] =
    useState<Record<ElasticityFeature, number>>(INITIAL_VALUES);

  const handleSliderChange = (feature: ElasticityFeature, newValue: number) => {
    const clampedNew = clampLevel(newValue);
    setSliderValues((prev) => ({ ...prev, [feature]: clampedNew }));
  };

  const handleReset = () => setSliderValues(INITIAL_VALUES);

  const result = useMemo(() => {
    if (!data) return null;
    let sliderDelta = 0;
    for (const { key } of FEATURES) {
      const v = sliderValues[key];
      const lookup =
        data.elasticity[key]?.[elasticityKey(v)] ?? data.elasticity[key]?.[String(v)] ?? 0;
      sliderDelta += lookup / 100;
    }
    const adjusted = data.baseline_sales.map((s) => s * (1 + sliderDelta));
    return { sliderDelta, adjusted };
  }, [data, sliderValues]);

  // 404 + 일반 에러 — 인라인 placeholder 대신 toast.
  const pushToast = useToastStore((s) => s.push);
  useEffect(() => {
    if (error instanceof ElasticityNotFoundError) {
      pushToast({ variant: 'error', title: '일시 오류, 다른 동 시도해주세요' });
    } else if (error) {
      pushToast({
        variant: 'error',
        title: '데이터 로드 실패',
        description: '잠시 후 다시 시도하세요.',
      });
    }
  }, [error, pushToast]);

  const businessMissing = !industryCode;

  return (
    <div className="space-y-6">
      <Header selectedDong={selectedDong} onSelectDong={setSelectedDong} onReset={handleReset} />

      {businessMissing && (
        <div className="rounded-3xl border border-dashed border-border bg-secondary p-8 text-center">
          <Sliders size={32} className="mx-auto mb-3 text-muted-foreground" aria-hidden="true" />
          <p className="text-sm font-bold text-foreground">업종 정보 필요</p>
          <p className="mt-2 text-[0.6875rem] text-muted-foreground">
            시뮬레이션 인풋(업종)을 먼저 입력해주세요.
          </p>
        </div>
      )}

      {!businessMissing && loading && <SkeletonState />}

      {!businessMissing && !loading && (data || error) && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="lg:col-span-5 space-y-3">
            <div className="rounded-3xl border border-border bg-card p-6 space-y-3">
              <h4 className="text-[0.6875rem] font-black uppercase tracking-widest text-muted-foreground mb-2">
                What-if 변수 조정
              </h4>
              {FEATURES.map(({ key, label }) => {
                const peersAll = data ? extractPeers(key, data.correlations) : [];
                const peersStrong = peersAll.filter((p) => Math.abs(p.r) >= 0.5);
                return (
                  <ElasticitySlider
                    key={key}
                    feature={key}
                    label={label}
                    value={sliderValues[key]}
                    onChange={(v) => handleSliderChange(key, v)}
                    elasticity={data?.elasticity[key] ?? {}}
                    peerCorrelations={peersStrong}
                  />
                );
              })}
            </div>
            {data && <QuarterSeasonalityCard quarterElasticity={data.elasticity.quarter_num} />}
          </div>

          {/* 우측 wrapper — lg 에서 flex-col 로 좌측 합산 높이에 자동 매칭.
              KpiHero 고정 + 4분기 박스 lg:flex-1 로 남은 공간 채움 → ScenarioComparisonChart
              가 ResponsiveContainer height="100%" 로 부모 채움. lg 미만 (mobile) 은 fixed height 280 으로 안전. */}
          <div className="flex flex-col gap-4 lg:col-span-7">
            {data && result ? (
              <>
                <KpiHero
                  sliderDelta={result.sliderDelta}
                  baseline={data.baseline_sales}
                  adjusted={result.adjusted}
                />
                <div className="flex flex-col rounded-3xl border border-border bg-card p-6 lg:flex-1">
                  <h4 className="mb-4 text-[0.6875rem] font-black uppercase tracking-widest text-muted-foreground">
                    4분기 매출 시뮬 — 기준선 vs 시나리오
                  </h4>
                  <div className="min-h-[280px] lg:flex-1">
                    <ScenarioComparisonChart
                      baseline={data.baseline_sales}
                      adjusted={result.adjusted}
                      height="100%"
                    />
                  </div>
                  <p className="mt-3 text-[0.625rem] leading-relaxed text-muted-foreground">
                    ※ 매출 = baseline × (1 + Σ slider_pct/100) — 선형 결합 가정. 실제 비선형
                    상호작용은 일부 누락될 수 있습니다.
                  </p>
                </div>
              </>
            ) : (
              <div className="rounded-3xl border border-dashed border-border bg-secondary p-12 text-center text-xs text-muted-foreground">
                시계열 데이터 없음
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// Sub-components (file-local)
// ─────────────────────────────────────────────────────────

function Header({
  selectedDong,
  onSelectDong,
  onReset,
}: {
  selectedDong: string;
  onSelectDong: (next: string) => void;
  onReset: () => void;
}) {
  return (
    <header>
      <div className="flex flex-wrap items-start gap-4">
        <div>
          <h3 className="flex items-center gap-3 text-2xl font-black italic text-foreground">
            <Sliders className="text-primary" /> 시나리오 시뮬레이터
          </h3>
          <p className="text-xs text-muted-foreground mt-2">
            What-if 분석 — 슬라이더로 변수 조정해 4분기 매출 시뮬
          </p>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-3">
          <DongDropdown selectedDong={selectedDong} onSelectDong={onSelectDong} />
          <button
            type="button"
            onClick={onReset}
            className="inline-flex h-10 items-center gap-1.5 rounded-lg border border-border bg-card px-3 text-sm text-foreground transition-colors hover:border-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1"
          >
            <RotateCcw size={14} /> 리셋
          </button>
        </div>
      </div>
    </header>
  );
}

function DongDropdown({
  selectedDong,
  onSelectDong,
}: {
  selectedDong: string;
  onSelectDong: (next: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // 시뮬 입력의 분석 대상 동만 — 사용자가 RUN 시점에 고른 1~4 동 (target_districts).
  // store.params 가 없으면 (직접 URL 진입 등) fallback 으로 마포 16동 전체 노출 — UX 차단 회피.
  const targetDistricts = useSimulationStore((s) => s.params?.target_districts ?? null);
  const optionDongs = useMemo(() => {
    if (targetDistricts && targetDistricts.length > 0) {
      const set = new Set(targetDistricts);
      return MAPO_DONGS.filter((d) => set.has(d.name));
    }
    return MAPO_DONGS;
  }, [targetDistricts]);

  useEffect(() => {
    if (!open) return;
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((s) => !s)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label="행정동 선택"
        className="relative flex h-10 min-w-[140px] items-center justify-center rounded-lg border border-border bg-card px-9 text-sm text-foreground transition-colors hover:border-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1"
      >
        <span className="truncate">{selectedDong}</span>
        <ChevronRight
          size={14}
          className={`absolute right-3 text-muted-foreground transition-transform duration-200 ${
            open ? 'rotate-90' : ''
          }`}
        />
      </button>
      {open && (
        <div
          role="listbox"
          className="custom-scrollbar absolute z-50 mt-1 max-h-52 w-full overflow-y-auto rounded-lg border border-border bg-card shadow-2xl"
          style={{ overscrollBehavior: 'contain' }}
        >
          {optionDongs.map((d) => {
            const active = d.name === selectedDong;
            return (
              <button
                key={d.code}
                role="option"
                aria-selected={active}
                onClick={() => {
                  onSelectDong(d.name);
                  setOpen(false);
                }}
                className={`flex w-full items-center justify-center px-3 py-2 text-center text-xs transition-colors ${
                  active ? 'bg-primary/10 font-bold text-primary' : 'text-foreground hover:bg-muted'
                }`}
              >
                {d.name}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function SkeletonState() {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
      <div className="lg:col-span-5 rounded-3xl border border-border bg-card p-6 space-y-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-20 rounded-2xl bg-secondary animate-pulse" aria-hidden="true" />
        ))}
      </div>
      <div className="lg:col-span-7 space-y-4">
        <div className="h-24 rounded-3xl bg-secondary animate-pulse" aria-hidden="true" />
        <div className="h-72 rounded-3xl bg-secondary animate-pulse" aria-hidden="true" />
      </div>
    </div>
  );
}

function KpiHero({
  sliderDelta,
  baseline,
  adjusted,
}: {
  sliderDelta: number;
  baseline: number[];
  adjusted: number[];
}) {
  const baselineTotal = baseline.reduce((sum, v) => sum + v, 0);
  const adjustedTotal = adjusted.reduce((sum, v) => sum + v, 0);
  const diff = adjustedTotal - baselineTotal;
  const avg = adjusted.length > 0 ? adjustedTotal / adjusted.length : 0;
  const deltaPct = sliderDelta * 100;

  const deltaTone =
    deltaPct > 0 ? 'text-success' : deltaPct < 0 ? 'text-danger' : 'text-muted-foreground';
  const diffTone = diff > 0 ? 'text-success' : diff < 0 ? 'text-danger' : 'text-muted-foreground';

  return (
    <div className="rounded-3xl border border-border bg-card p-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <KpiCell
          label="총 변화율"
          value={`${deltaPct >= 0 ? '+' : ''}${deltaPct.toFixed(1)}%`}
          tone={deltaTone}
        />
        <KpiCell label="분기 평균 매출" value={`₩${formatKrw(Math.round(avg))}`} />
        <KpiCell
          label="기준선 대비 차이"
          value={`${diff >= 0 ? '+' : ''}₩${formatKrw(Math.round(Math.abs(diff)))}`}
          tone={diffTone}
        />
      </div>
    </div>
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

function QuarterSeasonalityCard({
  quarterElasticity,
}: {
  quarterElasticity: Record<'Q1' | 'Q2' | 'Q3' | 'Q4', number>;
}) {
  const quarters: ('Q1' | 'Q2' | 'Q3' | 'Q4')[] = ['Q1', 'Q2', 'Q3', 'Q4'];
  return (
    <div className="rounded-2xl bg-secondary p-3">
      <div className="flex items-baseline justify-between mb-2">
        <span className="text-[0.625rem] font-black uppercase tracking-widest text-muted-foreground">
          분기 시즌성
        </span>
        <span className="text-[0.5625rem] font-bold text-muted-foreground">
          기준선에 이미 반영, 정보용
        </span>
      </div>
      <div className="grid grid-cols-4 gap-2">
        {quarters.map((q) => {
          const v = quarterElasticity?.[q] ?? 0;
          const tone = v > 0 ? 'text-success' : v < 0 ? 'text-danger' : 'text-muted-foreground';
          return (
            <div key={q} className="rounded-lg border border-border bg-card px-2 py-2 text-center">
              <div className="text-[0.5625rem] font-bold text-muted-foreground">{q}</div>
              <div className={`text-xs font-black tabular-nums ${tone}`}>
                {`${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// 만원/억원 자동 스케일 (양수 값 포맷, 부호는 호출 측에서 처리)
function formatKrw(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 100_000_000) return `${(value / 100_000_000).toFixed(1)}억`;
  if (abs >= 10_000) return `${Math.round(value / 10_000).toLocaleString('ko-KR')}만`;
  return `${Math.round(value).toLocaleString('ko-KR')}`;
}
