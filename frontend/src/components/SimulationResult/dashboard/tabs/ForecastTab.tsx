/**
 * ForecastTab — 매출 예측 탭
 * 1) TCN-v2 분기별 매출 예측 (Confidence Band P10-P90)
 * 2) BEP 누적이익 회수 곡선
 * 3) 시나리오 비교 (낙관/기본/비관)
 * 4) SHAP 피처 기여도 — 텍스트 인사이트 카드
 * 5) 거시·트렌드 환경 (samples 3종 + drivers/risks + narrative 모달)
 *
 * 이관됨: 폐업 위험도 Bullet → FinancialTab
 */

import { TrendingUp, Zap, Maximize2, GitCompareArrows, Globe2 } from 'lucide-react';
import type { SimulationOutput } from '../../../../types';
import type { DetailModalContent } from '../shared/DetailModal';
import { QuarterlyProjectionChart } from '../../QuarterlyProjectionChart';
import { formatScore } from '../utils/formatters';
import { ShapInsightCard } from '../charts/ShapInsightCard';
import { BepCumulativeProfitChart } from '../charts/BepCumulativeProfitChart';
import { ScenariosComparisonChart } from '../charts/ScenariosComparisonChart';
import { TrendSparklinesPanel } from '../charts/TrendSparklinesPanel';
import { TrendDriversRisks } from '../charts/TrendDriversRisks';

interface Props {
  simResult: SimulationOutput;
  openModal: (content: DetailModalContent) => void;
}

export function ForecastTab({ simResult, openModal }: Props) {
  const qp = simResult.quarterly_projection ?? [];
  const shap = simResult.shap_result;
  const trendScore = simResult.trend_forecast?.forecast?.score;
  const trendDir = simResult.trend_forecast?.forecast?.direction;
  const trendNarrative = simResult.trend_forecast?.forecast?.narrative;
  const trendDrivers = simResult.trend_forecast?.forecast?.key_drivers;
  const trendRisks = simResult.trend_forecast?.forecast?.risks;
  const scenarios = simResult.scenarios;
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
  const hasScenarios = scenarios?.base && scenarios.base.length > 0;

  return (
    <div className="space-y-6">
      <div className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-8 relative overflow-hidden">
        <div className="flex items-start justify-between mb-8 gap-6">
          <div>
            <h3 className="text-xl font-black text-stone-100 flex items-center gap-3 italic tracking-tight text-left leading-none">
              <TrendingUp className="text-indigo-400" /> TCN-v2 분기별 매출 예측 모델
            </h3>
            <p className="text-[10px] font-black text-stone-500 uppercase tracking-[0.2em] mt-3">
              Temporal Convolutional Network · P10~P90 신뢰 구간
            </p>
          </div>
          {/* 범례 미니 카드 — Linear/Vercel 스타일 분리 범례 */}
          <div className="flex gap-5 items-center bg-stone-950/50 px-4 py-3 rounded-2xl border border-stone-800/60 shrink-0">
            <div className="flex items-center gap-2">
              <div className="w-4 h-[2px] bg-indigo-400 rounded-full shadow-[0_0_6px_rgba(129,140,248,0.8)]" />
              <span className="text-[10px] font-black text-stone-500 uppercase tracking-widest">
                P50 Expected
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-indigo-500/10 border border-indigo-500/30 rounded-sm" />
              <span className="text-[10px] font-black text-stone-500 uppercase tracking-widest">
                P10~P90 Range
              </span>
            </div>
          </div>
        </div>

        {/* TCN 차트 영역 */}
        <div className="relative bg-stone-950/50 border border-stone-800 rounded-2xl p-6 mb-8">
          {qp.length > 0 ? (
            <QuarterlyProjectionChart data={qp} />
          ) : (
            <div className="aspect-[21/9] flex flex-col items-center justify-center">
              <TrendingUp size={48} className="text-stone-700 mb-3" />
              <p className="text-stone-500 font-black uppercase tracking-widest text-xs">
                분기 매출 데이터 없음
              </p>
              <p className="text-stone-600 text-[10px] mt-1">시뮬레이션 실행 후 표시됩니다</p>
            </div>
          )}
          {trendScore != null && (
            <div className="absolute top-6 right-6 p-4 bg-stone-900/90 border border-stone-700 rounded-2xl shadow-2xl text-left pointer-events-none">
              <div className="text-[10px] font-bold text-stone-500 mb-1 uppercase tracking-tighter">
                트렌드 스코어
              </div>
              <div className="text-2xl font-black text-indigo-400 tracking-tighter tabular-nums">
                {formatScore(trendScore)}
                <span className="text-xs font-bold text-stone-600 ml-1 uppercase tracking-widest">
                  {dirLabel}
                </span>
              </div>
              {trendNarrative && (
                <p className="mt-2 text-[10px] text-stone-500 max-w-[200px] leading-relaxed">
                  {trendNarrative.slice(0, 80)}
                  {trendNarrative.length > 80 ? '…' : ''}
                </p>
              )}
            </div>
          )}
        </div>

        {/* SHAP 피처 기여도 — 텍스트 인사이트 (2026-04-27 Waterfall 제거) */}
        <div className="space-y-4">
          <div className="flex items-center justify-between border-b border-stone-800 pb-3">
            <h4 className="text-xs font-black text-stone-500 uppercase tracking-widest flex items-center gap-2 italic">
              <Zap className="text-amber-400" size={14} /> 매출 기여 요인 분석
              <span className="text-[10px] font-black text-stone-500 normal-case tracking-normal not-italic">
                shap_result
              </span>
            </h4>
            {shap && (
              <button
                type="button"
                onClick={() =>
                  openModal({
                    title: 'SHAP 해석 상세',
                    content: `SHAP (SHapley Additive exPlanations)은 각 피처가 예측값에 얼마나 기여했는지 정량화합니다.\n\nbase_value: ${shap.base_value.toLocaleString('ko-KR')}원\npredicted_value: ${shap.predicted_value.toLocaleString('ko-KR')}원\n\n양수 피처는 매출을 밀어올리고, 음수는 낮춥니다.${shap.is_mock ? '\n\n⚠️ 현재 SHAP 데이터는 mock 상태입니다.' : ''}`,
                  })
                }
                className="text-[10px] font-bold text-stone-500 hover:text-indigo-400 uppercase tracking-widest flex items-center gap-1 transition-colors"
              >
                <Maximize2 size={12} /> 해석 상세
              </button>
            )}
          </div>

          <ShapInsightCard shap={shap} />
        </div>

        {/* BEP 투자 회수 곡선 */}
        {qp.length > 0 && (
          <div className="space-y-4 mt-8">
            <div className="flex items-center justify-between border-b border-stone-800 pb-3">
              <h4 className="text-xs font-black text-stone-500 uppercase tracking-widest flex items-center gap-2 italic">
                <TrendingUp className="text-emerald-400" size={14} /> 투자 회수 곡선
                <span className="text-[10px] font-black text-stone-500 normal-case tracking-normal not-italic">
                  cumulative_profit
                </span>
              </h4>
            </div>
            <BepCumulativeProfitChart data={qp} />
          </div>
        )}
      </div>

      {/* 시나리오 비교 패널 */}
      {hasScenarios && (
        <div className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-8">
          <div className="flex items-start justify-between mb-6 gap-6">
            <div>
              <h3 className="text-xl font-black text-stone-100 flex items-center gap-3 italic tracking-tight text-left leading-none">
                <GitCompareArrows className="text-indigo-400" size={20} /> 시나리오 비교
              </h3>
              <p className="text-[10px] font-black text-stone-500 uppercase tracking-[0.2em] mt-3">
                낙관 · 기본 · 비관 · 4분기 매출 envelope
              </p>
            </div>
            <div className="flex gap-4 items-center bg-stone-950/50 px-4 py-3 rounded-2xl border border-stone-800/60 shrink-0">
              <div className="flex items-center gap-2">
                <div className="w-3 h-[2px] bg-emerald-400 rounded-full" />
                <span className="text-[10px] font-black text-stone-500 uppercase tracking-widest">
                  낙관
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-[2px] bg-indigo-400 rounded-full shadow-[0_0_4px_rgba(129,140,248,0.6)]" />
                <span className="text-[10px] font-black text-stone-500 uppercase tracking-widest">
                  기본
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-[2px] bg-rose-400 rounded-full" />
                <span className="text-[10px] font-black text-stone-500 uppercase tracking-widest">
                  비관
                </span>
              </div>
            </div>
          </div>
          <ScenariosComparisonChart scenarios={scenarios} />
        </div>
      )}

      {/* 거시·트렌드 환경 패널 */}
      {hasTrendBlock && (
        <div className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-8 space-y-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-xl font-black text-stone-100 flex items-center gap-3 italic tracking-tight text-left leading-none">
                <Globe2 className="text-cyan-400" size={20} /> 거시·트렌드 환경
              </h3>
              <p className="text-[10px] font-black text-stone-500 uppercase tracking-[0.2em] mt-3">
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
                className="text-[10px] font-bold text-stone-500 hover:text-indigo-400 uppercase tracking-widest flex items-center gap-1 transition-colors shrink-0"
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
