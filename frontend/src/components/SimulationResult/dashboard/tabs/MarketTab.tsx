/**
 * MarketTab — 상권 분석 탭
 * 1) 상단 풀와이드: Kakao 지도 + vacancy_applied 배지
 * 2) 중단 Bento 2 col: IndicatorGrid (8 지표 + 레이더) + DistrictRankings (16동)
 * 3) 하단 풀와이드: 법률 리스크 (InsightsGrid legalOnly)
 */

import {
  AlertTriangle,
  Layers,
  MapPin,
  BarChart3,
  ShieldAlert,
  Brain,
  Target,
  TrendingUp,
} from 'lucide-react';
import type { SimulationOutput } from '../../../../types';
import type { DetailModalContent } from '../shared/DetailModal';
import { getGuFromDong } from '../../../../data/seoulRegions';
import { MapSection } from '../../sections/MapSection';
import { haversineM } from '../../sections/MarketMap';
import { IndicatorGrid } from '../../sections/IndicatorGrid';
import { DistrictRankings } from '../../sections/DistrictRankings';
import { AgentCard } from '../../shared/AgentCard';
import { calcHHI, hhiToDiversity, formatScore, formatKrw } from '../utils/formatters';
import {
  interpretHHI,
  SATURATION_MAP,
  safeMap,
  HHI_SEGMENTS,
  SATURATION_SEGMENTS,
} from '../utils/mappings';
import { FlowVsRevenueScatter } from '../charts/FlowVsRevenueScatter';
import { DifferentiationCard } from '../charts/DifferentiationCard';
import { CannibalizationDistanceChart } from '../charts/CannibalizationDistanceChart';
import { IndustryClosureTrendCard } from '../charts/IndustryClosureTrendCard';
import { Sparkline } from '../charts/Sparkline';
import { ThresholdBar } from '../charts/ThresholdBar';

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
  // - 동일업종 수: total_competitors > count > samples.length 순. samples 는 top-20 cap 이라
  //   true 매장 수와 다를 수 있어 명시 필드를 항상 우선.
  // - 평균 거리: samples 중 distance_m 유효값만 평균
  // - 경쟁/임대 인덱스: market_report 0~100 정규화 값
  const sameIndustryCount =
    typeof ci?.competition_500m?.total_competitors === 'number'
      ? ci.competition_500m.total_competitors
      : typeof ci?.competition_500m?.count === 'number'
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

  // 주요 경쟁점 — spot 1위 좌표 기준 가까운 순 5개.
  // 데이터 소스 통합: competitor_intel.samples (분석 동 centroid 500m, top 20) +
  //                  all_competitor_locations (4동 centroid 1.5km, 357개)
  // 두 소스 모두 사용해 매장 풀 최대화 + place_name 기준 dedup.
  // spot 1위 좌표 = vacancy_spots 의 score 1위 (winner 우선, 부족 시 top3 동).
  const _winnerForTop = simResult.winner_district || simResult.target_district;
  const _top3 = (simResult.top_3_candidates ?? []).filter(
    (d): d is string => typeof d === 'string',
  );
  const _vacancySpots = ((simResult as SimulationOutput & { vacancy_spots?: unknown[] }).vacancy_spots ?? []) as Array<{
    lat?: unknown;
    lon?: unknown;
    dong_name?: unknown;
    listing_count?: unknown;
    score?: unknown;
  }>;
  const _spot1Info: { lat: number; lng: number; dongName: string } | null = (() => {
    if (!_winnerForTop) return null;
    const valid = (s: { lat?: unknown; lon?: unknown }) =>
      typeof s.lat === 'number' &&
      typeof s.lon === 'number' &&
      Number.isFinite(s.lat) &&
      Number.isFinite(s.lon);
    const winnerSpots = _vacancySpots
      .filter((s) => s.dong_name === _winnerForTop && valid(s))
      .sort((a, b) => {
        const sa = typeof a.score === 'number' ? a.score : Number.NEGATIVE_INFINITY;
        const sb = typeof b.score === 'number' ? b.score : Number.NEGATIVE_INFINITY;
        if (sa !== sb) return sb - sa;
        const la = typeof a.listing_count === 'number' ? a.listing_count : 0;
        const lb = typeof b.listing_count === 'number' ? b.listing_count : 0;
        return lb - la;
      });
    if (winnerSpots[0])
      return {
        lat: winnerSpots[0].lat as number,
        lng: winnerSpots[0].lon as number,
        dongName: String(winnerSpots[0].dong_name ?? _winnerForTop),
      };
    const top3Set = new Set(_top3);
    const top3Spots = _vacancySpots
      .filter((s) => top3Set.has(String(s.dong_name)) && s.dong_name !== _winnerForTop && valid(s))
      .sort((a, b) => {
        const la = typeof a.listing_count === 'number' ? a.listing_count : 0;
        const lb = typeof b.listing_count === 'number' ? b.listing_count : 0;
        return lb - la;
      });
    if (top3Spots[0])
      return {
        lat: top3Spots[0].lat as number,
        lng: top3Spots[0].lon as number,
        dongName: String(top3Spots[0].dong_name ?? _winnerForTop),
      };
    return null;
  })();
  const _spot1 = _spot1Info ? { lat: _spot1Info.lat, lng: _spot1Info.lng } : null;
  // 분석 기준 동 — spot 1위 동(매물 있는 곳) 우선, 없으면 winner.
  // 동 한눈에 / 공실률 등 frontend 가 winner 동 데이터 직접 참조하던 곳에서 사용.
  const analysisDong = _spot1Info?.dongName ?? _winnerForTop ?? null;

  const topCompetitors = (() => {
    if (!_spot1) {
      return [...samples]
        .filter((s) => s.place_name)
        .sort((a, b) => (a.distance_m ?? Infinity) - (b.distance_m ?? Infinity))
        .slice(0, 5);
    }
    type CandidateRaw = {
      place_name?: string | null;
      brand_name?: string | null;
      lat?: number | null;
      lng?: number | null;
      lon?: number | null;
      distance_m?: number | null;
    };
    // samples (lat/lon or lat/lng 둘 다 가능) + all_competitor_locations 통합
    const allLocations = (simResult.all_competitor_locations ?? []) as CandidateRaw[];
    const merged: CandidateRaw[] = [...samples, ...allLocations];
    const seen = new Set<string>();
    const sorted = merged
      .map((m) => {
        const lat = typeof m.lat === 'number' ? m.lat : null;
        const lng = typeof m.lng === 'number' ? m.lng : typeof m.lon === 'number' ? m.lon : null;
        if (lat == null || lng == null) return null;
        const dist = haversineM(_spot1.lat, _spot1.lng, lat, lng);
        return { ...m, lat, lng, distance_m: Math.round(dist) };
      })
      .filter((m): m is CandidateRaw & { lat: number; lng: number; distance_m: number } => m !== null && Boolean(m.place_name))
      .filter((m) => {
        const key = `${m.place_name}_${m.lat.toFixed(5)}_${m.lng.toFixed(5)}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      })
      .sort((a, b) => a.distance_m - b.distance_m);
    return sorted.slice(0, 5);
  })();

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
          analysisDong={analysisDong}
        />
      </div>

      {/* ═══ 중단 Bento 2 col: Indicator + Ranking — '상권 지리 정보' 와 동일 form ═══ */}
      <div className="grid grid-cols-2 gap-6">
        <div className="bg-card border border-border rounded-[40px] p-6 flex flex-col">
          <div className="flex justify-between items-start mb-4">
            <div className="min-w-0">
              <h3 className="text-lg font-black text-foreground flex items-center gap-3 italic text-left">
                <BarChart3 className="text-primary" size={20} /> 8대 핵심 상권 지표
              </h3>
              <p className="text-xs text-muted-foreground mt-1 text-left">
                정량 8지표 동별 비교 + 레이더
              </p>
            </div>
          </div>
          <div className="flex-grow">
            <IndicatorGrid simResult={simResult} />
          </div>
        </div>
        <div className="bg-card border border-border rounded-[40px] p-6 flex flex-col">
          <div className="flex justify-between items-start mb-4">
            <div className="min-w-0">
              <h3 className="text-lg font-black text-foreground flex items-center gap-3 italic text-left">
                <Layers className="text-primary" size={20} />{' '}
                {getGuFromDong(simResult.winner_district ?? simResult.target_district) ?? '서울'}{' '}
                동별 랭킹
              </h3>
              <p className="text-xs text-muted-foreground mt-1 text-left">
                16동 5지표 정량 비교 / winner 선정
              </p>
            </div>
            {winnerDistrict && (
              <div className="flex gap-2 shrink-0">
                <div className="px-3 py-1 bg-primary/10 border border-primary/20 rounded-full text-[0.5625rem] font-black text-primary flex items-center gap-1.5 uppercase">
                  {winnerDistrict} 추천
                </div>
              </div>
            )}
          </div>
          <div className="flex-grow">
            <DistrictRankings simResult={simResult} />
          </div>
        </div>
      </div>

      {/* ═══ 에이전트 분석 요약 — 시장/인구/랭킹 (full-width 3-col) ═══
          IndicatorGrid 내부 좁은 컬럼에서 size="full" 카드 깨지던 것을 분리해 가로 정렬로 해소.
          '상권 지리 정보' 와 동일 form. */}
      {(() => {
        const attrs = simResult.agent_attributions ?? [];
        const market = attrs.find((a) => a.id === 'market_analyst');
        const population = attrs.find((a) => a.id === 'population_analyst');
        const ranking = attrs.find((a) => a.id === 'district_ranking');
        if (!market && !population && !ranking) return null;
        return (
          <div className="bg-card border border-border rounded-[40px] p-6">
            <div className="flex justify-between items-start mb-4">
              <div className="min-w-0">
                <h3 className="text-lg font-black text-foreground flex items-center gap-3 italic text-left">
                  <Brain className="text-primary" size={20} /> 에이전트 분석 요약
                </h3>
                <p className="text-xs text-muted-foreground mt-1 text-left">
                  market · population · ranking 3 에이전트 종합 판단
                </p>
              </div>
            </div>
            {/* 3 카드 세로 stack — 한 줄에 한 에이전트씩 풀폭 사용해 verdict/reasoning 가독성 확보 */}
            <div className="flex flex-col gap-3">
              {market && <AgentCard attribution={market} size="full" />}
              {population && <AgentCard attribution={population} size="full" />}
              {ranking && <AgentCard attribution={ranking} size="full" />}
            </div>
          </div>
        );
      })()}

      {/* ═══ Scatter: 유동인구 × 매출 상관 — '상권 지리 정보' 와 동일 form ═══ */}
      <div className="bg-card border border-border rounded-[40px] p-6">
        <div className="flex justify-between items-start mb-4">
          <div className="min-w-0">
            <h3 className="text-lg font-black text-foreground flex items-center gap-3 italic text-left">
              <TrendingUp className="text-primary" size={20} /> 유동인구 × 매출 상관
              <span className="text-[0.6875rem] font-black text-muted-foreground tracking-widest not-italic truncate">
                16 동
              </span>
            </h3>
            <p className="text-xs text-muted-foreground mt-1 text-left">
              동별 유동인구 ↔ 매출 회귀 산점도 / winner 강조
            </p>
          </div>
        </div>
        <FlowVsRevenueScatter
          rankings={simResult.district_rankings ?? []}
          winnerDistrict={simResult.winner_district}
        />
      </div>

      {/* ═══ Competitor Intel: 차별화 포지션 — '상권 지리 정보' 와 동일 form ═══ */}
      <div className="bg-card border border-border rounded-[40px] p-6">
        <div className="flex justify-between items-start mb-4">
          <div className="min-w-0">
            <h3 className="text-lg font-black text-foreground flex items-center gap-3 italic text-left">
              <Target className="text-primary" size={20} /> 차별화 포지셔닝
              <span className="text-[0.6875rem] font-black text-muted-foreground tracking-widest not-italic truncate">
                competitor_intel
              </span>
            </h3>
            <p className="text-xs text-muted-foreground mt-1 text-left">
              차별화 포지션 + 핵심 기회 / 핵심 리스크 양분
            </p>
          </div>
        </div>
        <DifferentiationCard
          differentiation={ci?.differentiation_position ?? null}
          opportunities={ci?.key_opportunities}
          risks={ci?.key_risks}
        />
      </div>

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

      {/* ═══ 경쟁 집중도 / 다양성 / 포화도 — 4단 구조 (라벨 → 척도 → 수치 → 해석) ═══ */}
      {/* Tailwind purge 안전: 동적 색 concat 금지 → 명시 매핑. */}
      {samples.length > 0 &&
        (() => {
          const HHI_LABEL_TEXT: Record<string, string> = {
            emerald: 'text-emerald-500',
            amber: 'text-amber-500',
            orange: 'text-orange-500',
            rose: 'text-rose-500',
          };
          const hhiTextClass = HHI_LABEL_TEXT[hhiInfo.color] ?? 'text-foreground';
          // 매장 총수 — total_competitors 우선, 없으면 count, 마지막으로 samples.length(top-20 cap).
          // samples.length 만 쓰면 "20" 으로 잘못 보이므로 명시적으로 fallback 우선순위 둠.
          const totalCount =
            ci?.competition_500m?.total_competitors ??
            ci?.competition_500m?.count ??
            samples.length;
          // saturation 임계값은 500m 기준 — 다른 반경이면 면적비율 보정 (backend 와 동일).
          const radiusM = ci?.competition_500m?.radius_m ?? 500;
          const areaRatio = (radiusM / 500) ** 2;
          const scaledCount = areaRatio > 0 ? totalCount / areaRatio : totalCount;
          const SAT_MAX = SATURATION_SEGMENTS[SATURATION_SEGMENTS.length - 1].max;
          // 브랜드 분포 1위 점유율 — 다양성 카드 텍스트용.
          const brandCounts: Record<string, number> = {};
          samples.forEach((s) => {
            const k = s.brand_name || '독립점';
            brandCounts[k] = (brandCounts[k] || 0) + 1;
          });
          const topEntry = Object.entries(brandCounts).sort((a, b) => b[1] - a[1])[0] ?? null;
          const topShare = topEntry ? (topEntry[1] / samples.length) * 100 : 0;
          return (
            <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
              {/* ── 카드 1: HHI 집중도 ── */}
              <div className="rounded-3xl border border-border bg-card p-6">
                <div className="mb-1 text-[0.625rem] font-black uppercase tracking-widest text-muted-foreground">
                  시장 집중도 (HHI)
                </div>
                <div className={`text-xs font-bold ${hhiTextClass}`}>{hhiInfo.label}</div>
                <div className="mt-4">
                  <ThresholdBar
                    value={Math.round(hhi)}
                    max={10000}
                    segments={HHI_SEGMENTS}
                    sourceText="DOJ/FTC Horizontal Merger Guidelines (2010)"
                  />
                </div>
                <div className="mt-3 border-t border-border pt-3">
                  <div className="text-[0.625rem] uppercase tracking-widest text-muted-foreground">
                    HHI 값
                  </div>
                  <div className="font-mono text-lg font-bold tabular-nums text-foreground">
                    {Math.round(hhi).toLocaleString('ko-KR')}
                    <span className="ml-1 text-xs font-normal text-muted-foreground">/ 10,000</span>
                  </div>
                </div>
              </div>

              {/* ── 카드 2: 시장 다양성 — HHI 의 inverse 임을 명시, 가로바 X (자의적 임계값 회피) ── */}
              <div className="rounded-3xl border border-border bg-card p-6">
                <div className="mb-1 text-[0.625rem] font-black uppercase tracking-widest text-muted-foreground">
                  브랜드 다양성
                </div>
                <div className="text-xs font-bold text-muted-foreground">
                  HHI 의 보완 지표 (100 − HHI/100)
                </div>
                <div className="mt-4 flex items-baseline gap-2">
                  <div className="font-mono text-3xl font-black tabular-nums tracking-tighter text-foreground">
                    {diversity.toFixed(1)}
                  </div>
                  <div className="text-sm text-muted-foreground">/ 100</div>
                </div>
                <div className="mt-3 border-t border-border pt-3 text-xs leading-relaxed text-muted-foreground">
                  {topEntry ? (
                    <>
                      반경 내 매장의{' '}
                      <span className="font-bold text-foreground">{topShare.toFixed(0)}%</span> 가{' '}
                      <span className="font-bold text-foreground">&lsquo;{topEntry[0]}&rsquo;</span>
                      , 나머지{' '}
                      <span className="font-bold text-foreground">
                        {(100 - topShare).toFixed(0)}%
                      </span>{' '}
                      는 분산
                    </>
                  ) : (
                    '브랜드 분포 데이터 없음'
                  )}
                </div>
              </div>

              {/* ── 카드 3: 반경 포화도 — backend 산식 임계값 명시 ── */}
              <div className="rounded-3xl border border-border bg-card p-6">
                <div className="mb-1 text-[0.625rem] font-black uppercase tracking-widest text-muted-foreground">
                  반경 포화도
                </div>
                <div className="text-xs font-bold text-foreground">{saturationLabel}</div>
                <div className="mt-4">
                  <ThresholdBar
                    value={Math.min(scaledCount, SAT_MAX)}
                    max={SAT_MAX}
                    segments={SATURATION_SEGMENTS}
                    valueFormat={(v) => `${Math.round(v)}개`}
                    sourceText={`반경 500m 환산 매장 수 기준 (실측 ${Math.round(totalCount)}개${radiusM === 500 ? '' : `, 반경 ${radiusM}m`})`}
                  />
                </div>
                <div className="mt-3 border-t border-border pt-3">
                  <div className="text-[0.625rem] uppercase tracking-widest text-muted-foreground">
                    반경 {radiusM}m 내 동종 매장
                  </div>
                  <div className="font-mono text-lg font-bold tabular-nums text-foreground">
                    {totalCount.toLocaleString('ko-KR')}
                    <span className="ml-1 text-xs font-normal text-muted-foreground">개</span>
                  </div>
                </div>
              </div>
            </div>
          );
        })()}
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
  analysisDong: string | null;
}

function MarketAnalysisSidebar({
  sameIndustryCount,
  avgDistance,
  competitionIntensity,
  rentIndex,
  topCompetitors,
  simResult,
  analysisDong,
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
      <WinnerDistrictSummary simResult={simResult} analysisDong={analysisDong} />
    </aside>
  );
}

/** A + B 묶음 — 분석 기준 동(spot 1위 동, fallback: winner)의 기본 통계 + 분기별 매출 sparkline.
 *  2026-05-06 변경: winner 동 매물 0건 케이스에서도 화면 정보 일관성 — 모든 분석 데이터를
 *  spot 1위 동 기준으로 추출 (PHASE 2 target 변경과 동일 방향).
 *  데이터 출처:
 *  - 핵심 고객층 = demographic_report.core_demographic (PHASE 2 결과 — spot 1위 동 LLM 산출)
 *  - 공실률 = district_rankings[analysisDong].vacancy_rate (winner 직접 참조 → spot 1위 동으로 변경)
 *  - 분기 평균 매출 / 4분기 sparkline = quarterly_projection
 *  데이터 모두 비어있으면 섹션 자체 hide. */
function WinnerDistrictSummary({
  simResult,
  analysisDong,
}: {
  simResult: SimulationOutput;
  analysisDong: string | null;
}) {
  const targetDong = analysisDong ?? simResult.winner_district ?? null;
  const winnerRanking =
    targetDong != null
      ? (simResult.district_rankings ?? []).find((r) => r.district === targetDong)
      : null;
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
              {vacancyRate.toFixed(1)}%
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
