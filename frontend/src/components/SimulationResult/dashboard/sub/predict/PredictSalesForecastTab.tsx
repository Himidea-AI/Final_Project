/**
 * PredictSalesForecastTab — 예측·매출 예측
 * 2026-04-28 IA 재구조 — ForecastTab 의 TCN/Scenarios/SHAP 섹션 분해.
 * trend_forecast 는 LLM 출처라 AnalyzeMarketTab 으로 이동.
 */

import { TrendingUp, Zap, Maximize2 } from 'lucide-react';
import type { QuarterlyProjection, SimulationOutput } from '../../../../../types';
import type { DetailModalContent } from '../../shared/DetailModal';
import { QuarterlyProjectionChart, type ChartSeries } from '../../../QuarterlyProjectionChart';
import { QuarterlyStatStrip } from '../../../QuarterlyStatStrip';
import { ShapInsightCard } from '../../charts/ShapInsightCard';
import { sortByRanking } from '../../utils/rankSort';

interface Props {
  simResult: SimulationOutput;
  openModal: (content: DetailModalContent) => void;
}

export function PredictSalesForecastTab({ simResult, openModal }: Props) {
  // /predict 응답의 district_predictions 우선. 비어있거나 없으면 winner 단일 동 fallback.
  // (B4 다중 동 라인) — 4개 동 비교를 차트 한 장에서 보여주기 위해.
  // ranking 정렬 (winner→4위) 후 SERIES_COLORS[idx] 매핑이 Deep Blue Sequential 4-tier 와 정합.
  const districtPredsRaw = (simResult.district_predictions ?? []).filter(
    (p) => !p.is_excluded_combo,
  );
  const districtPreds = sortByRanking(districtPredsRaw, simResult);
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
  // 시나리오 비교 차트 제거 (2026-05-01) — 분기별 예상 매출의 CI band 와 동일 데이터(95% 신뢰구간)라 중복.
  // 시나리오 범위 한줄평 패널도 제거 (2026-05-03 사용자 요청) — QuarterlyStatStrip 정량 row + 합계/평균 만 유지.

  return (
    <div className="space-y-6">
      <div className="rounded-3xl border border-border bg-card p-8">
        <div className="flex items-start justify-between mb-8 gap-6">
          <div>
            <h3 className="text-xl font-black text-foreground flex items-center gap-3 italic tracking-tight text-left leading-none">
              <TrendingUp className="text-primary" /> 분기별 예상 매출
            </h3>
          </div>
        </div>

        {/* Chart + Stat Strip 좌우 분할 — 평탄 시계열에서 차트는 trend 시각, strip 은 분기별 정량 진실.
            mobile/tablet 에서는 위아래 stack, lg 이상에서 좌:우 = 1fr : 280px. */}
        <div className="mb-8 grid grid-cols-1 gap-4 lg:grid-cols-[1fr_280px]">
          <div className="relative flex flex-col justify-center rounded-2xl border border-border bg-secondary p-6">
            {series.length > 0 ? (
              <QuarterlyProjectionChart
                series={series}
                winnerDistrict={simResult.winner_district}
              />
            ) : (
              <div className="flex aspect-[21/9] flex-col items-center justify-center">
                <TrendingUp size={48} className="mb-3 text-muted-foreground" />
                <p className="text-xs font-black uppercase tracking-widest text-muted-foreground">
                  분기 매출 데이터 없음
                </p>
              </div>
            )}
          </div>
          {series.length > 0 && (
            <div className="rounded-2xl border border-border bg-secondary p-4">
              <QuarterlyStatStrip series={series} winnerDistrict={simResult.winner_district} />
            </div>
          )}
        </div>
      </div>

      {/* 매출 기여 요인 분석 — 별도 Layer 2 outer card. 헤더 위계는 분기별 예상 매출과 동일 (h3 text-xl font-black). */}
      <div className="rounded-3xl border border-border bg-card p-8">
        <div className="mb-8 flex items-start justify-between gap-6">
          <h3 className="flex items-center gap-3 text-left text-xl font-black italic leading-none tracking-tight text-foreground">
            <Zap className="text-primary" /> 매출 기여 요인 분석
          </h3>
          {districtPreds.length === 0 && shap && (
            <button
              type="button"
              onClick={() =>
                openModal({
                  title: 'SHAP 해석 상세',
                  content: `SHAP (SHapley Additive exPlanations)은 각 피처가 예측값에 얼마나 기여했는지 정량화합니다.\n\nbase_value: ${(shap.base_value ?? 0).toLocaleString('ko-KR')}원\npredicted_value: ${(shap.predicted_value ?? 0).toLocaleString('ko-KR')}원${shap.is_mock ? '\n\n⚠️ 현재 SHAP 데이터는 mock 상태입니다.' : ''}`,
                })
              }
              className="flex items-center gap-1 text-[0.625rem] font-bold uppercase tracking-widest text-muted-foreground hover:text-primary"
            >
              <Maximize2 size={12} /> 해석 상세
            </button>
          )}
        </div>
        {districtPreds.length > 0 && districtPreds.some((p) => p.shap_result !== null) ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {districtPreds.map((p) => (
              <ShapInsightCard key={p.district} district={p.district} shap={p.shap_result} />
            ))}
          </div>
        ) : (
          <ShapInsightCard shap={shap} />
        )}
      </div>
    </div>
  );
}
