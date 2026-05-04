/**
 * MarketTab — 상권 분석 탭
 * 1) 상단 풀와이드: Kakao 지도 + vacancy_applied 배지
 * 2) 중단 Bento 2 col: IndicatorGrid (8 지표 + 레이더) + DistrictRankings (16동)
 * 3) 하단 풀와이드: 법률 리스크 (InsightsGrid legalOnly)
 */

import { AlertTriangle, Layers, MapPin, BarChart3, ShieldAlert, Brain } from 'lucide-react';
import type { SimulationOutput } from '../../../../types';
import type { DetailModalContent } from '../shared/DetailModal';
import { MapSection } from '../../sections/MapSection';
import { IndicatorGrid } from '../../sections/IndicatorGrid';
import { DistrictRankings } from '../../sections/DistrictRankings';
import { AgentCard } from '../../shared/AgentCard';
import { calcHHI, hhiToDiversity, formatScore, formatKrw } from '../utils/formatters';
import { interpretHHI, SATURATION_MAP, safeMap } from '../utils/mappings';
import { FlowVsRevenueScatter } from '../charts/FlowVsRevenueScatter';
import { DifferentiationCard } from '../charts/DifferentiationCard';
import { CannibalizationDistanceChart } from '../charts/CannibalizationDistanceChart';
import { IndustryClosureTrendCard } from '../charts/IndustryClosureTrendCard';
import { Sparkline } from '../charts/Sparkline';

interface Props {
  simResult: SimulationOutput;
  openModal?: (content: DetailModalContent) => void;
}

export function MarketTab({ simResult }: Props) {
  // Medium #5 — competitor_intel을 강타입(CompetitorIntel)으로 받음. 기존 Record<string, any> 캐스팅 제거.
  const ci = simResult.competitor_intel ?? null;
  const samples = ci?.competition_500m?.samples ?? [];
  const hhi = calcHHI(samples);
  const diversity = hhiToDiversity(hhi);
  const hhiInfo = interpretHHI(hhi);
  const saturationRaw = ci?.competition_500m?.saturation_level;
  const saturationLabel = saturationRaw
    ? safeMap(SATURATION_MAP, saturationRaw, SATURATION_MAP.medium)
    : '—';

  const vacancyApplied = Boolean(simResult.vacancy_applied);
  const winnerDistrict = simResult.winner_district || simResult.target_district;

  // 사이드바 핵심 지표
  // - 동일업종 수: backend가 명시 count를 주면 우선 사용, 없으면 samples.length 폴백
  // - 평균 거리: samples 중 distance_m 유효값만 평균
  // - 경쟁/임대 인덱스: market_report 0~100 정규화 값
  const sameIndustryCount =
    typeof ci?.competition_500m?.count === 'number'
      ? ci.competition_500m.count
      : samples.length > 0
        ? samples.length
        : null;
  const distances = samples
    .map((s) => (typeof s.distance_m === 'number' ? s.distance_m : null))
    .filter((d): d is number => d != null);
  const avgDistance =
    distances.length > 0
      ? Math.round(distances.reduce((a, b) => a + b, 0) / distances.length)
      : null;
  const competitionIntensity = simResult.market_report?.competition_intensity ?? null;
  const rentIndex = simResult.market_report?.rent_index ?? null;

  // 가까운 순 정렬, 상위 5
  const topCompetitors = [...samples]
    .filter((s) => s.place_name)
    .sort((a, b) => (a.distance_m ?? Infinity) - (b.distance_m ?? Infinity))
    .slice(0, 5);

  return (
    <div className="space-y-6">
      {/* ═══ 상단 2:1 분할: Kakao 지도 (좌) + 분석 사이드바 (우) ═══ */}
      <div className="grid grid-cols-3 gap-6">
        {/* ── 좌측: 지도 영역 (col-span-2 ≈ 67%) ── */}
        <div className="col-span-2 bg-card border border-border rounded-[40px] p-6 relative">
          <div className="flex justify-between items-start mb-4">
            <div className="min-w-0">
              <h3 className="text-lg font-black text-foreground flex items-center gap-3 italic text-left">
                <MapPin className="text-primary" size={20} /> 상권 지리 정보
                <span className="text-[0.6875rem] font-black text-muted-foreground tracking-widest not-italic truncate">
                  {winnerDistrict ?? '—'} · 반경 500m
                </span>
              </h3>
              <p className="text-xs text-muted-foreground mt-1 text-left">
                반경 500m 경쟁 매장 / 16동 choropleth / winner 하이라이트
              </p>
            </div>
            <div className="flex gap-2 shrink-0">
              {vacancyApplied && (
                <div className="px-3 py-1 bg-warning/10 border border-warning/20 rounded-full text-[0.5625rem] font-black text-warning flex items-center gap-1.5 uppercase">
                  <AlertTriangle size={10} /> 공실 페널티 반영
                </div>
              )}
              <div className="px-3 py-1 bg-primary/10 border border-primary/20 rounded-full text-[0.5625rem] font-black text-primary flex items-center gap-1.5">
                <MapPin size={10} /> 500m 반경
              </div>
            </div>
          </div>
          {/* 기존 MapSection 재활용 (Kakao SDK) */}
          <div className="rounded-2xl overflow-hidden">
            <MapSection simResult={simResult} />
          </div>
        </div>

        {/* ── 우측: 분석 사이드바 (col-span-1 ≈ 33%) ── */}
        <MarketAnalysisSidebar
          sameIndustryCount={sameIndustryCount}
          avgDistance={avgDistance}
          competitionIntensity={competitionIntensity}
          rentIndex={rentIndex}
          topCompetitors={topCompetitors}
          simResult={simResult}
        />
      </div>

      {/* ═══ 중단 Bento 2 col: Indicator + Ranking ═══ */}
      <div className="grid grid-cols-2 gap-6">
        <div className="bg-card border border-border p-8 rounded-3xl flex flex-col">
          <h4 className="text-sm font-black text-foreground mb-6 flex items-center gap-2 uppercase tracking-tight">
            <BarChart3 size={16} className="text-primary" /> 8대 핵심 상권 지표
          </h4>
          <div className="flex-grow">
            <IndicatorGrid simResult={simResult} />
          </div>
        </div>
        <div className="bg-card border border-border p-8 rounded-3xl flex flex-col">
          <h4 className="text-sm font-black text-foreground mb-6 flex items-center gap-2 uppercase tracking-tight">
            <Layers size={16} className="text-primary" /> 마포구 동별 랭킹
            {winnerDistrict && (
              <span className="ml-auto text-[0.625rem] font-bold text-primary normal-case tracking-normal">
                {winnerDistrict} 추천
              </span>
            )}
          </h4>
          <div className="flex-grow">
            <DistrictRankings simResult={simResult} />
          </div>
        </div>
      </div>

      {/* ═══ 에이전트 분석 요약 — 시장/인구/랭킹 (full-width 3-col) ═══
          IndicatorGrid 내부 좁은 컬럼에서 size="full" 카드 깨지던 것을 분리해 가로 정렬로 해소. */}
      {(() => {
        const attrs = simResult.agent_attributions ?? [];
        const market = attrs.find((a) => a.id === 'market_analyst');
        const population = attrs.find((a) => a.id === 'population_analyst');
        const ranking = attrs.find((a) => a.id === 'district_ranking');
        if (!market && !population && !ranking) return null;
        return (
          <div className="bg-card border border-border rounded-3xl p-8">
            <h4 className="text-sm font-black text-foreground mb-6 flex items-center gap-2 uppercase tracking-tight">
              <Brain size={16} className="text-primary" /> 에이전트 분석 요약
            </h4>
            {/* 3 카드 세로 stack — 한 줄에 한 에이전트씩 풀폭 사용해 verdict/reasoning 가독성 확보 */}
            <div className="flex flex-col gap-3">
              {market && <AgentCard attribution={market} size="full" />}
              {population && <AgentCard attribution={population} size="full" />}
              {ranking && <AgentCard attribution={ranking} size="full" />}
            </div>
          </div>
        );
      })()}

      {/* ═══ Scatter: 유동인구 × 매출 상관 (가이드 #8) ═══ */}
      <div className="bg-card border border-border rounded-3xl p-8">
        <h4 className="text-sm font-black text-foreground mb-6 flex items-center gap-2 uppercase tracking-tight">
          유동인구 × 매출 상관 (16 동)
        </h4>
        <FlowVsRevenueScatter
          rankings={simResult.district_rankings ?? []}
          winnerDistrict={simResult.winner_district}
        />
      </div>

      {/* ═══ Competitor Intel: 차별화 포지션 + 카니발 거리 분포 + 동 업종 폐업률 추세 ═══ */}
      <DifferentiationCard
        differentiation={ci?.differentiation_position ?? null}
        opportunities={ci?.key_opportunities}
        risks={ci?.key_risks}
      />

      {(ci?.cannibalization || ci?.industry_closure_trend) && (
        <div className="grid grid-cols-2 gap-6">
          {ci?.cannibalization && (
            <CannibalizationDistanceChart
              bins={ci.cannibalization.distance_bins ?? null}
              closestM={ci.cannibalization.closest_distance_m ?? null}
              impactPct={ci.cannibalization.estimated_revenue_impact_pct ?? null}
              impactIsCapped={ci.cannibalization.impact_is_capped ?? null}
            />
          )}
          {ci?.industry_closure_trend && (
            <IndustryClosureTrendCard trend={ci.industry_closure_trend} />
          )}
        </div>
      )}

      {/* ═══ HHI 경쟁 집중도 카드 (실데이터 기반) ═══ */}
      {samples.length > 0 && (
        <div className="bg-card border border-border rounded-3xl p-6 grid grid-cols-3 gap-6">
          <div className="text-left">
            <div className="text-[0.625rem] font-black text-muted-foreground uppercase tracking-widest mb-2">
              HHI 집중도 지수
            </div>
            <div className="text-3xl font-black text-foreground tabular-nums tracking-tighter">
              {Math.round(hhi).toLocaleString('ko-KR')}
            </div>
            <div className={`text-xs font-bold mt-1 text-${hhiInfo.color}-400`}>
              {hhiInfo.label}
            </div>
          </div>
          <div className="text-left">
            <div className="text-[0.625rem] font-black text-muted-foreground uppercase tracking-widest mb-2">
              시장 다양성 지수
            </div>
            <div className="text-3xl font-black text-foreground tabular-nums tracking-tighter">
              {diversity.toFixed(1)}%
            </div>
            <div className="w-full bg-card h-1 rounded-full overflow-hidden mt-2">
              <div
                className="bg-primary h-full transition-all"
                style={{ width: `${diversity}%` }}
              />
            </div>
          </div>
          <div className="text-left">
            <div className="text-[0.625rem] font-black text-muted-foreground uppercase tracking-widest mb-2">
              반경 포화도
            </div>
            <div className="text-3xl font-black text-foreground tabular-nums tracking-tighter">
              {saturationLabel}
            </div>
            <div className="text-xs font-bold text-muted-foreground mt-1">
              500m 내 {samples.length}개 매장 분석
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────
// MarketAnalysisSidebar — 지도 우측 1/3 분석 사이드바
// ────────────────────────────────────────────────────────────────────

interface MarketCompetitorSample {
  place_name?: string | null;
  brand_name?: string | null;
  distance_m?: number | null;
}

interface SidebarProps {
  sameIndustryCount: number | null;
  avgDistance: number | null;
  competitionIntensity: number | null;
  rentIndex: number | null;
  topCompetitors: MarketCompetitorSample[];
  simResult: SimulationOutput;
}

function MarketAnalysisSidebar({
  sameIndustryCount,
  avgDistance,
  competitionIntensity,
  rentIndex,
  topCompetitors,
  simResult,
}: SidebarProps) {
  const metrics: Array<{ label: string; value: string }> = [
    {
      label: '반경 500m 내 동일업종',
      value: sameIndustryCount != null ? `${sameIndustryCount}개` : '—',
    },
    {
      label: '평균 거리',
      value: avgDistance != null ? `${avgDistance.toLocaleString('ko-KR')}m` : '—',
    },
    {
      label: '경쟁 강도',
      value: competitionIntensity != null ? `${formatScore(competitionIntensity)}/100` : '—',
    },
    {
      label: '임대료 인덱스',
      value: rentIndex != null ? `${formatScore(rentIndex)}/100` : '—',
    },
  ];

  return (
    <aside className="col-span-1 bg-card border border-border rounded-[32px] p-6 flex flex-col gap-5 min-w-0">
      {/* ─ 섹션 1: 분석 결과 ─ */}
      <section>
        <h4 className="text-lg font-black text-foreground flex items-center gap-3 italic text-left mb-4">
          분석 결과
        </h4>
        <ul className="space-y-3">
          {metrics.map((m) => (
            <li key={m.label} className="flex items-center justify-between gap-3 min-w-0">
              <span className="text-[0.6875rem] font-bold text-muted-foreground truncate">
                {m.label}
              </span>
              <span className="text-sm font-black text-foreground tabular-nums tracking-tight shrink-0">
                {m.value}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <div className="border-t border-border" />

      {/* ─ 섹션 2: 분석 근거 ─ */}
      <section>
        <h4 className="text-lg font-black text-foreground flex items-center gap-3 italic text-left mb-3">
          분석 근거
        </h4>
        <div className="flex items-center gap-3">
          <div className="flex -space-x-2">
            <div className="w-7 h-7 rounded-full bg-card border-2 border-primary/60 flex items-center justify-center shadow-md">
              <BarChart3 size={12} className="text-primary" />
            </div>
            <div className="w-7 h-7 rounded-full bg-card border-2 border-warning/60 flex items-center justify-center shadow-md">
              <ShieldAlert size={12} className="text-warning" />
            </div>
          </div>
          <span className="text-[0.5625rem] font-bold text-muted-foreground leading-snug">
            Python 집계 + 상권 데이터
          </span>
        </div>
      </section>

      <div className="border-t border-border" />

      {/* ─ 섹션 3: 주요 경쟁점 ─ */}
      <section className="flex-1 min-h-0">
        <h4 className="text-lg font-black text-foreground flex items-center gap-3 italic text-left mb-3">
          주요 경쟁점
        </h4>
        {topCompetitors.length === 0 ? (
          <p className="text-[0.6875rem] text-muted-foreground font-medium leading-snug">
            반경 500m 경쟁 매장 데이터 없음
          </p>
        ) : (
          <ul className="space-y-2">
            {topCompetitors.map((c, i) => (
              <li
                key={`${c.place_name}-${i}`}
                className="flex items-center justify-between gap-3 min-w-0"
              >
                <span
                  className="text-[0.75rem] font-bold text-foreground truncate"
                  title={c.place_name ?? ''}
                >
                  {c.place_name ?? '—'}
                </span>
                <span className="text-[0.6875rem] font-mono text-muted-foreground tabular-nums shrink-0">
                  {c.distance_m != null ? `${Math.round(c.distance_m)}m` : '—'}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="border-t border-border" />

      {/* ─ 섹션 4: winner 동 한눈에 — 핵심 고객 + 공실률 + 4분기 매출 흐름 (사실 기반, mock 0) ─ */}
      <WinnerDistrictSummary simResult={simResult} />
    </aside>
  );
}

/** A + B 묶음 — winner 동의 기본 통계 3 metric + 분기별 매출 sparkline.
 *  데이터 출처:
 *  - 핵심 고객층 = demographic_report.core_demographic (age + gender)
 *  - 공실률 = district_rankings[winner].vacancy_rate (0~1 → %)
 *  - 분기 평균 매출 / 4분기 sparkline = quarterly_projection (winner 동 4 점)
 *  데이터 모두 비어있으면 섹션 자체 hide. */
function WinnerDistrictSummary({ simResult }: { simResult: SimulationOutput }) {
  const winner = simResult.winner_district;
  const winnerRanking =
    winner != null ? (simResult.district_rankings ?? []).find((r) => r.district === winner) : null;
  const vacancyRate = winnerRanking?.vacancy_rate ?? null;

  const demo = simResult.demographic_report;
  const coreCustomer = demo?.core_demographic
    ? `${demo.core_demographic.age} ${demo.core_demographic.gender}`
    : null;

  const quarterlyRevenues = (simResult.quarterly_projection ?? [])
    .slice(0, 4)
    .map((q) => (typeof q.revenue === 'number' ? q.revenue : 0));
  const totalRevenue = quarterlyRevenues.reduce((a, b) => a + b, 0);
  const avgQuarterly =
    quarterlyRevenues.length > 0 && totalRevenue > 0
      ? totalRevenue / quarterlyRevenues.length
      : null;

  const hasAnyData =
    coreCustomer != null || vacancyRate != null || quarterlyRevenues.some((v) => v > 0);
  if (!hasAnyData) return null;

  return (
    <section>
      <h4 className="text-lg font-black text-foreground flex items-center gap-3 italic text-left mb-4">
        동 한눈에
      </h4>
      <ul className="space-y-3">
        {coreCustomer && (
          <li className="flex items-center justify-between gap-3 min-w-0">
            <span className="text-[0.6875rem] font-bold text-muted-foreground truncate">
              핵심 고객층
            </span>
            <span className="text-sm font-black text-foreground shrink-0">{coreCustomer}</span>
          </li>
        )}
        {vacancyRate != null && (
          <li className="flex items-center justify-between gap-3 min-w-0">
            <span className="text-[0.6875rem] font-bold text-muted-foreground truncate">
              공실률
            </span>
            <span className="text-sm font-black text-foreground tabular-nums tracking-tight shrink-0">
              {(vacancyRate * 100).toFixed(1)}%
            </span>
          </li>
        )}
        {avgQuarterly != null && (
          <li className="flex items-center justify-between gap-3 min-w-0">
            <span className="text-[0.6875rem] font-bold text-muted-foreground truncate">
              분기 평균 매출
            </span>
            <span className="text-sm font-black text-foreground tabular-nums tracking-tight shrink-0">
              ₩{formatKrw(Math.round(avgQuarterly))}
            </span>
          </li>
        )}
      </ul>

      {/* B — 4분기 매출 sparkline + 합계 */}
      {quarterlyRevenues.some((v) => v > 0) && (
        <div className="mt-4 rounded-xl border border-border bg-secondary p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[0.625rem] font-bold uppercase tracking-widest text-muted-foreground">
              4분기 매출 흐름
            </span>
            <span className="text-[0.6875rem] font-mono tabular-nums text-foreground">
              합계 ₩{formatKrw(Math.round(totalRevenue))}
            </span>
          </div>
          <Sparkline data={quarterlyRevenues} height={32} />
        </div>
      )}
    </section>
  );
}
