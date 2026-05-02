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
  const trendConfidence = simResult.trend_forecast?.forecast?.confidence;
  const industryTrend = simResult.trend_forecast?.industry_trend;
  const dongTrend = simResult.trend_forecast?.dong_trend;
  const macro = simResult.trend_forecast?.macro;

  // forecast_confidence 칩 — Tailwind dynamic class 컴파일 회피 위해 조건부 className.
  const CONF_LABEL: Record<string, string> = {
    high: '신뢰도 높음',
    medium: '신뢰도 보통',
    low: '신뢰도 낮음',
  };
  const CONF_CLASSES: Record<string, string> = {
    high: 'border-success/30 bg-success/10 text-success',
    medium: 'border-primary/30 bg-primary/10 text-primary',
    low: 'border-warning/30 bg-warning/10 text-warning',
  };

  // §3.7: 알 수 없는 direction 값은 임의 default 가 아니라 placeholder.
  const DIR_LABEL: Record<string, string> = {
    strong_growth: '강한 성장',
    growth: '성장',
    stable: '유지',
    decline: '하락',
    strong_decline: '강한 하락',
  };
  const dirLabel = trendDir ? (DIR_LABEL[trendDir] ?? '—') : '—';
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
        <div className="rounded-3xl border border-border bg-card p-8 space-y-5">
          <div className="flex flex-wrap items-start gap-4">
            <div>
              <h3 className="text-2xl font-black text-foreground flex items-center gap-3 italic tracking-tight text-left leading-tight">
                <Globe2 className="text-primary" size={22} /> 거시·트렌드 환경
              </h3>
              <p className="text-[0.6875rem] font-bold text-muted-foreground mt-3">
                업종 · 지역 · 거시 시계열 + LLM 요약
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3 ml-auto">
              {trendScore != null && (
                <span className="rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-[0.75rem] font-bold tabular-nums text-primary">
                  {Math.round(trendScore)}/100 · {dirLabel}
                </span>
              )}
              {trendConfidence && CONF_LABEL[trendConfidence] && (
                <span
                  className={`rounded-full border px-3 py-1 text-[0.75rem] font-bold ${
                    CONF_CLASSES[trendConfidence] ??
                    'border-muted-foreground/30 bg-muted/10 text-muted-foreground'
                  }`}
                >
                  {CONF_LABEL[trendConfidence]}
                </span>
              )}
              {trendNarrative && (
                <button
                  type="button"
                  onClick={() =>
                    openModal({
                      title: `트렌드 분석 상세 (${dirLabel} · ${formatScore(trendScore ?? 0)})`,
                      content: trendNarrative,
                    })
                  }
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-xs font-bold text-foreground hover:bg-secondary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1 transition-colors"
                >
                  <Maximize2 size={14} /> 전체 해석
                </button>
              )}
            </div>
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
