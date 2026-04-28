/**
 * PredictSalesForecastTab — 예측·매출 예측
 * 2026-04-28 IA 재구조 — ForecastTab 의 TCN/Scenarios/SHAP 섹션 분해.
 * trend_forecast 는 LLM 출처라 AnalyzeMarketTab 으로 이동.
 */

import { TrendingUp, Zap, Maximize2, GitCompareArrows } from 'lucide-react';
import type { SimulationOutput } from '../../../../../types';
import type { DetailModalContent } from '../../shared/DetailModal';
import { QuarterlyProjectionChart } from '../../../QuarterlyProjectionChart';
import { ScenariosComparisonChart } from '../../charts/ScenariosComparisonChart';
import { ShapInsightCard } from '../../charts/ShapInsightCard';

interface Props {
  simResult: SimulationOutput;
  openModal: (content: DetailModalContent) => void;
}

export function PredictSalesForecastTab({ simResult, openModal }: Props) {
  const qp = simResult.quarterly_projection ?? [];
  const shap = simResult.shap_result;
  const scenarios = simResult.scenarios;
  const hasScenarios = scenarios?.base && scenarios.base.length > 0;

  return (
    <div className="space-y-6">
      <div className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-8">
        <div className="flex items-start justify-between mb-8 gap-6">
          <div>
            <h3 className="text-xl font-black text-stone-100 flex items-center gap-3 italic tracking-tight text-left leading-none">
              <TrendingUp className="text-indigo-400" /> TCN-v2 분기별 매출 예측
            </h3>
            <p className="text-[10px] font-black text-stone-500 uppercase tracking-[0.2em] mt-3">
              Temporal Convolutional Network · P10~P90 신뢰 구간
            </p>
          </div>
        </div>

        <div className="relative bg-stone-950/50 border border-stone-800 rounded-2xl p-6 mb-8">
          {qp.length > 0 ? (
            <QuarterlyProjectionChart data={qp} />
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
                className="text-[10px] font-bold text-stone-500 hover:text-indigo-400 uppercase tracking-widest flex items-center gap-1"
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
              <p className="text-[10px] font-black text-stone-500 uppercase tracking-[0.2em] mt-3">
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
