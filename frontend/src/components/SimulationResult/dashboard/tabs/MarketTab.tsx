/**
 * MarketTab — 상권 분석 탭
 * 1) 상단 풀와이드: Kakao 지도 + vacancy_applied 배지
 * 2) 중단 Bento 2 col: IndicatorGrid (8 지표 + 레이더) + DistrictRankings (16동)
 * 3) 하단 풀와이드: 법률 리스크 (InsightsGrid legalOnly)
 */

import { AlertTriangle, Layers, MapPin, BarChart3, ShieldAlert } from 'lucide-react';
import type { SimulationOutput } from '../../../../types';
import type { DetailModalContent } from '../shared/DetailModal';
import { MapSection } from '../../sections/MapSection';
import { IndicatorGrid } from '../../sections/IndicatorGrid';
import { DistrictRankings } from '../../sections/DistrictRankings';
import { calcHHI, hhiToDiversity, formatScore } from '../utils/formatters';
import { interpretHHI, SATURATION_MAP, safeMap } from '../utils/mappings';
import { FlowVsRevenueScatter } from '../charts/FlowVsRevenueScatter';

interface Props {
  simResult: SimulationOutput;
  openModal?: (content: DetailModalContent) => void;
}

export function MarketTab({ simResult }: Props) {
  const ci = simResult.competitor_intel as Record<string, any> | null | undefined;
  const samples = (ci?.competition_500m?.samples as Array<MarketCompetitorSample>) ?? [];
  const hhi = calcHHI(samples);
  const diversity = hhiToDiversity(hhi);
  const hhiInfo = interpretHHI(hhi);
  const saturationRaw = ci?.competition_500m?.saturation_level as string | undefined;
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
      ? (ci?.competition_500m?.count as number)
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
        <div className="col-span-2 bg-[#111113] border border-stone-800/60 rounded-[40px] p-6 relative">
          <div className="flex justify-between items-start mb-4">
            <div className="min-w-0">
              <h3 className="text-lg font-black text-stone-100 flex items-center gap-3 italic text-left">
                <MapPin className="text-indigo-400" size={20} /> 상권 지리 정보
                <span className="text-[11px] font-black text-stone-500 tracking-widest not-italic truncate">
                  {winnerDistrict ?? '—'} · 반경 500m
                </span>
              </h3>
              <p className="text-xs text-stone-500 mt-1 text-left">
                반경 500m 경쟁 매장 / 16동 choropleth / winner 하이라이트
              </p>
            </div>
            <div className="flex gap-2 shrink-0">
              {vacancyApplied && (
                <div className="px-3 py-1 bg-amber-500/10 border border-amber-500/20 rounded-full text-[9px] font-black text-amber-500 flex items-center gap-1.5 uppercase">
                  <AlertTriangle size={10} /> 공실 페널티 반영
                </div>
              )}
              <div className="px-3 py-1 bg-indigo-500/10 border border-indigo-500/20 rounded-full text-[9px] font-black text-indigo-500 flex items-center gap-1.5">
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
        />
      </div>

      {/* ═══ 중단 Bento 2 col: Indicator + Ranking ═══ */}
      <div className="grid grid-cols-2 gap-6">
        <div className="bg-stone-900/40 border border-stone-800/60 p-8 rounded-3xl flex flex-col">
          <h4 className="text-sm font-black text-stone-100 mb-6 flex items-center gap-2 uppercase tracking-tight">
            <BarChart3 size={16} className="text-indigo-400" /> 8대 핵심 상권 지표
          </h4>
          <div className="flex-grow">
            <IndicatorGrid simResult={simResult} />
          </div>
        </div>
        <div className="bg-stone-900/40 border border-stone-800/60 p-8 rounded-3xl flex flex-col">
          <h4 className="text-sm font-black text-stone-100 mb-6 flex items-center gap-2 uppercase tracking-tight">
            <Layers size={16} className="text-indigo-400" /> 마포구 동별 랭킹
            {winnerDistrict && (
              <span className="ml-auto text-[10px] font-bold text-indigo-400 normal-case tracking-normal">
                {winnerDistrict} 추천
              </span>
            )}
          </h4>
          <div className="flex-grow">
            <DistrictRankings simResult={simResult} />
          </div>
        </div>
      </div>

      {/* ═══ Scatter: 유동인구 × 매출 상관 (가이드 #8) ═══ */}
      <div className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-8">
        <h4 className="text-sm font-black text-stone-100 mb-6 flex items-center gap-2 uppercase tracking-tight">
          유동인구 × 매출 상관 (16 동)
        </h4>
        <FlowVsRevenueScatter
          rankings={simResult.district_rankings ?? []}
          winnerDistrict={simResult.winner_district}
        />
      </div>

      {/* ═══ HHI 경쟁 집중도 카드 (실데이터 기반) ═══ */}
      {samples.length > 0 && (
        <div className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-6 grid grid-cols-3 gap-6">
          <div className="text-left">
            <div className="text-[10px] font-black text-stone-500 uppercase tracking-widest mb-2">
              HHI 집중도 지수
            </div>
            <div className="text-3xl font-black text-stone-100 tabular-nums tracking-tighter">
              {Math.round(hhi).toLocaleString('ko-KR')}
            </div>
            <div className={`text-xs font-bold mt-1 text-${hhiInfo.color}-400`}>
              {hhiInfo.label}
            </div>
          </div>
          <div className="text-left">
            <div className="text-[10px] font-black text-stone-500 uppercase tracking-widest mb-2">
              시장 다양성 지수
            </div>
            <div className="text-3xl font-black text-stone-100 tabular-nums tracking-tighter">
              {diversity.toFixed(1)}%
            </div>
            <div className="w-full bg-stone-800 h-1 rounded-full overflow-hidden mt-2">
              <div
                className="bg-indigo-500 h-full transition-all"
                style={{ width: `${diversity}%` }}
              />
            </div>
          </div>
          <div className="text-left">
            <div className="text-[10px] font-black text-stone-500 uppercase tracking-widest mb-2">
              반경 포화도
            </div>
            <div className="text-3xl font-black text-stone-100 tabular-nums tracking-tighter">
              {saturationLabel}
            </div>
            <div className="text-xs font-bold text-stone-500 mt-1">
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
}

function MarketAnalysisSidebar({
  sameIndustryCount,
  avgDistance,
  competitionIntensity,
  rentIndex,
  topCompetitors,
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
    <aside className="col-span-1 bg-[#141210]/60 border border-stone-800/40 rounded-[32px] p-6 flex flex-col gap-5 min-w-0">
      {/* ─ 섹션 1: 분석 결과 ─ */}
      <section>
        <h4 className="text-[10px] font-black text-stone-600 uppercase tracking-[0.2em] mb-4">
          분석 결과
        </h4>
        <ul className="space-y-3">
          {metrics.map((m) => (
            <li key={m.label} className="flex items-center justify-between gap-3 min-w-0">
              <span className="text-[11px] font-bold text-stone-500 truncate">{m.label}</span>
              <span className="text-sm font-black text-stone-100 tabular-nums tracking-tight shrink-0">
                {m.value}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <div className="border-t border-stone-800/40" />

      {/* ─ 섹션 2: 분석 근거 ─ */}
      <section>
        <h4 className="text-[10px] font-black text-stone-600 uppercase tracking-[0.2em] mb-3">
          분석 근거
        </h4>
        <div className="flex items-center gap-3">
          <div className="flex -space-x-2">
            <div className="w-7 h-7 rounded-full bg-stone-900 border-2 border-blue-500/60 flex items-center justify-center shadow-md">
              <BarChart3 size={12} className="text-blue-400" />
            </div>
            <div className="w-7 h-7 rounded-full bg-stone-900 border-2 border-amber-500/60 flex items-center justify-center shadow-md">
              <ShieldAlert size={12} className="text-amber-400" />
            </div>
          </div>
          <span className="text-[9px] font-bold text-stone-500 leading-snug">
            Python 집계 + 상권 데이터
          </span>
        </div>
      </section>

      <div className="border-t border-stone-800/40" />

      {/* ─ 섹션 3: 주요 경쟁점 ─ */}
      <section className="flex-1 min-h-0">
        <h4 className="text-[10px] font-black text-stone-600 uppercase tracking-[0.2em] mb-3">
          주요 경쟁점
        </h4>
        {topCompetitors.length === 0 ? (
          <p className="text-[11px] text-stone-600 font-medium leading-snug">
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
                  className="text-[12px] font-bold text-stone-300 truncate"
                  title={c.place_name ?? ''}
                >
                  {c.place_name ?? '—'}
                </span>
                <span className="text-[11px] font-mono text-stone-500 tabular-nums shrink-0">
                  {c.distance_m != null ? `${Math.round(c.distance_m)}m` : '—'}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </aside>
  );
}
