/**
 * ForecastTab — 매출 예측 탭
 * 1) TCN-v2 분기별 매출 예측 (Confidence Band P10-P90)
 * 2) SHAP 피처 기여도 분석 (상위 4개 raw value)
 * 3) 시나리오 낙관/기본/비관 (선택 표시)
 */

import { TrendingUp, Zap, Maximize2 } from 'lucide-react';
import type { SimulationOutput } from '../../../../types';
import type { DetailModalContent } from '../shared/DetailModal';
import { QuarterlyProjectionChart } from '../../QuarterlyProjectionChart';
import { formatShapValue, shapBarWidth, formatScore } from '../utils/formatters';

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

  const dirLabel = trendDir === 'growth' ? '성장' : trendDir === 'decline' ? '하락' : '유지';

  // SHAP 상위 4개 (abs_shap 기준 이미 정렬됨)
  const shapTop4 = (shap?.feature_importance ?? []).slice(0, 4);

  return (
    <div className="space-y-6">
      <div className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-8 relative overflow-hidden">
        <div className="flex items-center justify-between mb-8">
          <h3 className="text-xl font-black text-stone-100 flex items-center gap-3 italic tracking-tight text-left">
            <TrendingUp className="text-indigo-400" /> TCN-v2 분기별 매출 예측 모델
          </h3>
          <div className="flex items-center gap-2 text-stone-500">
            <div className="w-3 h-3 bg-indigo-500/20 border border-indigo-500/50 rounded" />
            <span className="text-[10px] font-bold tracking-widest">신뢰 구간 표시</span>
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

        {/* SHAP 피처 기여도 */}
        <div className="space-y-4">
          <div className="flex items-center justify-between border-b border-stone-800 pb-3">
            <h4 className="text-xs font-black text-stone-500 uppercase tracking-widest flex items-center gap-2 italic">
              <Zap className="text-amber-400" size={14} /> 피처 기여도 분석 (SHAP)
            </h4>
            {shap && (
              <button
                type="button"
                onClick={() =>
                  openModal({
                    title: 'SHAP 해석 상세',
                    content: `SHAP (SHapley Additive exPlanations)는 각 피처가 예측값에 얼마나 기여했는지를 정량화하는 기법입니다.\n\nbase_value (평균 예측): ${shap.base_value.toLocaleString('ko-KR')}원\nfinal_value (최종 예측): ${shap.predicted_value.toLocaleString('ko-KR')}원\n\n양수 (+) 피처는 매출을 밀어올리고, 음수 (-) 피처는 매출을 낮추는 방향으로 작동합니다.${shap.is_mock ? '\n\n⚠️ 현재 SHAP 데이터는 mock 상태입니다. 실제 모델 예측값이 아닙니다.' : ''}`,
                  })
                }
                className="text-[10px] font-bold text-stone-500 hover:text-indigo-400 uppercase tracking-widest flex items-center gap-1 transition-colors"
              >
                <Maximize2 size={12} /> 해석 상세
              </button>
            )}
          </div>

          {shapTop4.length > 0 ? (
            <div className="grid grid-cols-2 gap-4">
              {shapTop4.map((item, i) => {
                const pos = item.shap_value >= 0;
                const label = item.feature_ko || item.feature;
                return (
                  <div
                    key={`${label}-${i}`}
                    className="flex items-center gap-4 p-4 bg-stone-950/40 border border-stone-800/40 rounded-2xl hover:border-stone-700 transition-colors"
                  >
                    <span className="text-[11px] font-bold text-stone-400 w-28 tracking-tighter text-left">
                      {label}
                    </span>
                    <div className="flex-1 bg-stone-800 h-2.5 rounded-full overflow-hidden flex justify-center shadow-inner">
                      <div
                        className={`h-full ${pos ? 'bg-indigo-500 ml-auto' : 'bg-rose-500 mr-auto'}`}
                        style={{ width: `${shapBarWidth(item.shap_value)}%` }}
                      />
                    </div>
                    <span
                      className={`text-[11px] font-black w-14 text-right tabular-nums ${pos ? 'text-indigo-400' : 'text-rose-400'}`}
                    >
                      {formatShapValue(item.shap_value)}
                    </span>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-stone-800 bg-stone-950/40 p-8 text-center text-xs text-stone-500">
              SHAP 해석 데이터 없음 — 모델 예측 신뢰도가 확정되면 표시됩니다
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
