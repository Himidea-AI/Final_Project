/**
 * PredictSalesForecastTab — 예측·매출 예측
 * 2026-04-28 IA 재구조 — ForecastTab 의 TCN/Scenarios/SHAP 섹션 분해.
 * trend_forecast 는 LLM 출처라 AnalyzeMarketTab 으로 이동.
 */

import { TrendingUp, Zap, Maximize2, GitCompareArrows } from 'lucide-react';
import type { QuarterlyProjection, SimulationOutput } from '../../../../../types';
import type { DetailModalContent } from '../../shared/DetailModal';
import { QuarterlyProjectionChart, type ChartSeries } from '../../../QuarterlyProjectionChart';
import { ScenariosComparisonChart } from '../../charts/ScenariosComparisonChart';
import { ShapInsightCard } from '../../charts/ShapInsightCard';

interface Props {
  simResult: SimulationOutput;
  openModal: (content: DetailModalContent) => void;
}

export function PredictSalesForecastTab({ simResult, openModal }: Props) {
  // /predict 응답의 district_predictions 우선. 비어있거나 없으면 winner 단일 동 fallback.
  // (B4 다중 동 라인) — 4개 동 비교를 차트 한 장에서 보여주기 위해.
  const districtPreds = (simResult.district_predictions ?? []).filter((p) => !p.is_excluded_combo);
  // DistrictPredictionResult.quarterly_projection 은 단건이므로 배열로 wrap.
  // 단, 일부 환경에서 backend 가 array 로 보낼 수도 있으므로 양쪽 처리 (안전 가드).
  const seriesFromPredictions: ChartSeries[] = districtPreds
    .map((p) => {
      const proj = p.quarterly_projection;
      if (!proj) return null;
      const projection = (Array.isArray(proj) ? proj : [proj]) as QuarterlyProjection[];
      return projection.length > 0 ? { district: p.district, projection } : null;
    })
    .filter((s): s is ChartSeries => s !== null);

  // fallback — district_predictions 없을 때 simResult.quarterly_projection (단일 동) 사용
  // SimulationOutput.quarterly_projection 타입은 array 지만 useCombinedSimResult 에서 단건 cast 가능 → Array.isArray 가드
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fallbackQp = simResult.quarterly_projection as any;
  const fallbackProjection: QuarterlyProjection[] = Array.isArray(fallbackQp)
    ? (fallbackQp as QuarterlyProjection[])
    : fallbackQp
      ? [fallbackQp as QuarterlyProjection]
      : [];

  const series: ChartSeries[] =
    seriesFromPredictions.length > 0
      ? seriesFromPredictions
      : fallbackProjection.length > 0
        ? [
            {
              district: simResult.winner_district ?? simResult.target_district ?? '단일',
              projection: fallbackProjection,
            },
          ]
        : [];

  const shap = simResult.shap_result;
  const scenarios = simResult.scenarios;
  const hasScenarios = scenarios?.base && scenarios.base.length > 0;

  return (
    <div className="space-y-6">
      <div className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-8">
        <div className="flex items-start justify-between mb-8 gap-6">
          <div>
            <h3 className="text-xl font-black text-stone-100 flex items-center gap-3 italic tracking-tight text-left leading-none">
              <TrendingUp className="text-indigo-400" /> 분기별 예상 매출
            </h3>
            <p className="text-[0.625rem] font-black text-stone-500 uppercase tracking-[0.2em] mt-3">
              Temporal Convolutional Network · P10~P90 신뢰 구간
            </p>
          </div>
        </div>

        <div className="relative bg-stone-950/50 border border-stone-800 rounded-2xl p-6 mb-8">
          {series.length > 0 ? (
            <QuarterlyProjectionChart series={series} winnerDistrict={simResult.winner_district} />
          ) : (
            <div className="aspect-[21/9] flex flex-col items-center justify-center">
              <TrendingUp size={48} className="text-stone-700 mb-3" />
              <p className="text-stone-500 font-black uppercase tracking-widest text-xs">
                분기 매출 데이터 없음
              </p>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between border-b border-stone-800 pb-3">
            <h4 className="text-xs font-black text-stone-500 uppercase tracking-widest flex items-center gap-2 italic">
              <Zap className="text-amber-400" size={14} /> 매출 기여 요인 분석
            </h4>
            {shap && (
              <button
                type="button"
                onClick={() =>
                  openModal({
                    title: 'SHAP 해석 상세',
                    content: `SHAP (SHapley Additive exPlanations)은 각 피처가 예측값에 얼마나 기여했는지 정량화합니다.\n\nbase_value: ${shap.base_value.toLocaleString('ko-KR')}원\npredicted_value: ${shap.predicted_value.toLocaleString('ko-KR')}원${shap.is_mock ? '\n\n⚠️ 현재 SHAP 데이터는 mock 상태입니다.' : ''}`,
                  })
                }
                className="text-[0.625rem] font-bold text-stone-500 hover:text-indigo-400 uppercase tracking-widest flex items-center gap-1"
              >
                <Maximize2 size={12} /> 해석 상세
              </button>
            )}
          </div>
          <ShapInsightCard shap={shap} />
        </div>
      </div>

      {hasScenarios && (
        <div className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-8">
          <div className="flex items-start justify-between mb-6 gap-6">
            <div>
              <h3 className="text-xl font-black text-stone-100 flex items-center gap-3 italic tracking-tight text-left leading-none">
                <GitCompareArrows className="text-indigo-400" size={20} /> 시나리오 비교
              </h3>
              <p className="text-[0.625rem] font-black text-stone-500 uppercase tracking-[0.2em] mt-3">
                낙관 · 기본 · 비관 · 4분기 매출 envelope
              </p>
            </div>
          </div>
          <ScenariosComparisonChart scenarios={scenarios} />
        </div>
      )}
    </div>
  );
}
