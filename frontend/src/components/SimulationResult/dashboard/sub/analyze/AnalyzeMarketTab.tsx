/**
 * AnalyzeMarketTab — 분석·상권 분석 (LLM 통합)
 * 2026-04-28 IA 재구조 — MarketTab 의 모든 차트 + ForecastTab 의 trend_forecast 패키지 통합.
 */

import { Globe2, Maximize2 } from 'lucide-react';
import type { SimulationOutput } from '../../../../../types';
import type { DetailModalContent } from '../../shared/DetailModal';
import { MarketTab } from '../../tabs/MarketTab';
import { TrendSparklinesPanel } from '../../charts/TrendSparklinesPanel';
import { TrendDriversRisks } from '../../charts/TrendDriversRisks';
import { formatScore } from '../../utils/formatters';

interface Props {
  simResult: SimulationOutput;
  openModal: (content: DetailModalContent) => void;
}

export function AnalyzeMarketTab({ simResult, openModal }: Props) {
  const trendScore = simResult.trend_forecast?.forecast?.score;
  const trendDir = simResult.trend_forecast?.forecast?.direction;
  const trendNarrative = simResult.trend_forecast?.forecast?.narrative;
  const trendDrivers = simResult.trend_forecast?.forecast?.key_drivers;
  const trendRisks = simResult.trend_forecast?.forecast?.risks;
  const industryTrend = simResult.trend_forecast?.industry_trend;
  const dongTrend = simResult.trend_forecast?.dong_trend;
  const macro = simResult.trend_forecast?.macro;

  const dirLabel = trendDir === 'growth' ? '성장' : trendDir === 'decline' ? '하락' : '유지';
  const hasTrendBlock =
    (industryTrend?.samples && industryTrend.samples.length > 0) ||
    (dongTrend?.samples && dongTrend.samples.length > 0) ||
    (macro?.samples && macro.samples.length > 0) ||
    (trendDrivers && trendDrivers.length > 0) ||
    (trendRisks && trendRisks.length > 0);

  return (
    <div className="space-y-6">
      <MarketTab simResult={simResult} openModal={openModal} />

      {hasTrendBlock && (
        <div className="bg-card/40 border border-border/60 rounded-3xl p-8 space-y-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-xl font-black text-foreground flex items-center gap-3 italic tracking-tight text-left leading-none">
                <Globe2 className="text-primary" size={20} /> 거시·트렌드 환경
              </h3>
              <p className="text-[0.625rem] font-black text-muted-foreground uppercase tracking-[0.2em] mt-3">
                업종 · 지역 · 거시 12개월 시계열 + LLM 요약
              </p>
            </div>
            {trendNarrative && (
              <button
                type="button"
                onClick={() =>
                  openModal({
                    title: `트렌드 분석 상세 (${dirLabel} · ${formatScore(trendScore ?? 0)})`,
                    content: trendNarrative,
                  })
                }
                className="text-[0.625rem] font-bold text-muted-foreground hover:text-primary uppercase tracking-widest flex items-center gap-1 transition-colors shrink-0"
              >
                <Maximize2 size={12} /> 전체 해석
              </button>
            )}
          </div>

          <TrendSparklinesPanel industryTrend={industryTrend} dongTrend={dongTrend} macro={macro} />

          {(trendDrivers || trendRisks) && (
            <TrendDriversRisks drivers={trendDrivers} risks={trendRisks} />
          )}
        </div>
      )}
    </div>
  );
}
