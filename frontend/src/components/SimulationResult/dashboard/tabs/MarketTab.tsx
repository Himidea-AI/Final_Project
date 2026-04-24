/**
 * MarketTab — 상권 분석 탭
 * 1) 상단 풀와이드: Kakao 지도 + vacancy_applied 배지
 * 2) 중단 Bento 2 col: IndicatorGrid (8 지표 + 레이더) + DistrictRankings (16동)
 * 3) 하단 풀와이드: 법률 리스크 (InsightsGrid legalOnly)
 */

import { AlertTriangle, Layers, MapPin, Maximize2, BarChart3 } from 'lucide-react';
import type { SimulationOutput } from '../../../../types';
import type { DetailModalContent } from '../shared/DetailModal';
import { MapSection } from '../../sections/MapSection';
import { IndicatorGrid } from '../../sections/IndicatorGrid';
import { DistrictRankings } from '../../sections/DistrictRankings';
import { InsightsGrid } from '../../sections/InsightsGrid';
import { calcHHI, hhiToDiversity } from '../utils/formatters';
import { interpretHHI, SATURATION_MAP, safeMap } from '../utils/mappings';
import { FlowVsRevenueScatter } from '../charts/FlowVsRevenueScatter';
import { LegalDistributionBar } from '../charts/LegalDistributionBar';

interface Props {
  simResult: SimulationOutput;
  openModal: (content: DetailModalContent) => void;
}

export function MarketTab({ simResult, openModal }: Props) {
  const ci = simResult.competitor_intel as Record<string, any> | null | undefined;
  const samples = (ci?.competition_500m?.samples as Array<{ brand_name?: string | null }>) ?? [];
  const hhi = calcHHI(samples);
  const diversity = hhiToDiversity(hhi);
  const hhiInfo = interpretHHI(hhi);
  const saturationRaw = ci?.competition_500m?.saturation_level as string | undefined;
  const saturationLabel = saturationRaw
    ? safeMap(SATURATION_MAP, saturationRaw, SATURATION_MAP.medium)
    : '—';

  const vacancyApplied = Boolean(simResult.vacancy_applied);
  const winnerDistrict = simResult.winner_district || simResult.target_district;

  return (
    <div className="space-y-6">
      {/* ═══ 상단 풀와이드: Kakao 지도 ═══ */}
      <div className="bg-stone-900/20 border border-stone-800 rounded-3xl p-6 relative">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h3 className="text-lg font-black text-stone-100 flex items-center gap-3 italic text-left">
              <MapPin className="text-indigo-400" size={20} /> 상권 지리 정보
              <span className="text-[11px] font-black text-stone-500 tracking-widest not-italic">
                반경 500m · 16개 동 분석
              </span>
            </h3>
            <p className="text-xs text-stone-500 mt-1 text-left">
              반경 500m 경쟁 매장 / 16동 choropleth / winner 하이라이트
            </p>
          </div>
          <div className="flex gap-2">
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

      {/* ═══ 하단 풀와이드: 법률 리스크 ═══ */}
      <div className="bg-stone-900/40 border border-stone-800/60 p-8 rounded-3xl">
        <div className="flex justify-between items-center mb-6">
          <h4 className="text-sm font-black text-stone-100 flex items-center gap-2 uppercase tracking-tight">
            <AlertTriangle size={16} className="text-rose-400" /> 법률 규제 및 리스크 검토
            <span className="text-[10px] font-black text-stone-500 normal-case tracking-normal">
              ({(simResult.legal_risks ?? []).length}건 검토)
            </span>
          </h4>
          <button
            type="button"
            onClick={() =>
              openModal({
                title: '법률 리스크 종합 검토',
                content: (simResult.legal_risks ?? [])
                  .map(
                    (r, i) =>
                      `${i + 1}. [${r.risk_level}] ${r.type}\n   ${r.detail || r.recommendation || ''}`,
                  )
                  .join('\n\n'),
              })
            }
            className="text-[10px] font-black text-stone-500 hover:text-indigo-400 flex items-center gap-1 uppercase transition-colors"
          >
            <Maximize2 size={12} /> 전체 리포트 보기
          </button>
        </div>
        {/* 법률 리스크 등급 분포 (가이드 #11) */}
        <div className="bg-stone-950/40 border border-stone-800/60 rounded-2xl p-6 mb-4">
          <h5 className="text-xs font-black text-stone-500 uppercase tracking-widest mb-3">
            법률 리스크 등급 분포
          </h5>
          <LegalDistributionBar risks={simResult.legal_risks} />
        </div>
        <InsightsGrid simResult={simResult} legalOnly />
      </div>
    </div>
  );
}
