/**
 * PredictCustomerFlowTab — 고객·유동인구 예측 서브탭
 *
 * 2026-04-29 (Task B5): DemographicTab 에 있던 PeakHourCard (living_pop_forecast)
 * 를 [예측] - [고객·유동인구] 탭으로 이동. 유동인구는 예측 영역에 더 자연스러움.
 *
 * 2026-04-29 (Task M10): multi-district visual cycle.
 *   - district_predictions 도착 시 동별 grid (PeakHourCard + CustomerSegmentCard).
 *   - backend (수지니 c8ea31f) 는 customer_segment / living_pop_forecast 미구현 →
 *     항상 null. UI guard 로 null 시 hide + 안내. 단일 동 fallback (B5 케이스) 보존.
 *
 * 2026-05-03 (재구조 — 강민): 동별 grid → 섹션별 4동 통합 차트 2개.
 *   - 섹션 1: CustomerFlowPeakHourChart (24시간 grouped bar)
 *   - 섹션 2: CustomerFlowSegmentChart (매출 3종 + 차원별 비율 가로 grouped bar)
 *   - 단일 동 fallback (B5) 변경 없음.
 */

import { Activity, Users } from 'lucide-react';
import type {
  CustomerSegment,
  DistrictPredictionResult,
  LivingPopForecast,
  SimulationOutput,
} from '../../../../../types';
import { CustomerFlowPeakHourChart } from '../../charts/CustomerFlowPeakHourChart';
import { CustomerFlowSegmentChart } from '../../charts/CustomerFlowSegmentChart';
import { humanizeProfileSummary } from '../../charts/CustomerSegmentCard';
import { PeakHourCard } from '../../charts/PeakHourCard';
import { PlaceholderPanel } from '../../shared/PlaceholderPanel';

interface Props {
  simResult: SimulationOutput;
}

export function PredictCustomerFlowTab({ simResult }: Props) {
  const dpredicts = (simResult.district_predictions ?? []).filter(
    (p) => !p.is_excluded_combo,
  ) as DistrictPredictionResult[];

  // 다중 동 (district_predictions) 모드
  if (dpredicts.length > 0) {
    const anyPeak = dpredicts.some((p) => {
      const lp = p.living_pop_forecast as LivingPopForecast | null;
      return lp != null && Array.isArray(lp.quarters) && lp.quarters.length > 0;
    });
    const anySegment = dpredicts.some((p) => p.customer_segment != null);

    if (!anyPeak && !anySegment) {
      return (
        <div className="space-y-6">
          <PlaceholderPanel
            modelName="customer_revenue + living_pop_forecast"
            description="동별 고객 세그먼트 + 유동인구 피크 데이터는 backend /predict 응답에서 미수신 상태입니다. 백엔드 추가 후 활성화."
          />
        </div>
      );
    }

    // winner 동 (없으면 첫 동) 의 customer_segment 헤더 보강용
    const winnerDistrict = simResult.winner_district ?? dpredicts[0]!.district;
    const winnerPred = dpredicts.find((p) => p.district === winnerDistrict) ?? dpredicts[0]!;
    const winnerSegment = winnerPred.customer_segment as CustomerSegment | null;

    return (
      <div className="space-y-6">
        {/* 섹션 1 — 유동인구 피크시간 예측 (4동 통합) */}
        {anyPeak && (
          <div className="rounded-3xl border border-border bg-card p-6 space-y-6">
            <h3 className="flex items-center gap-3 text-xl font-black italic leading-none tracking-tight text-foreground">
              <Activity className="text-primary" /> 유동인구 피크시간 예측
            </h3>
            <CustomerFlowPeakHourChart dpredicts={dpredicts} />
            <div className="pt-4 border-t border-border space-y-1">
              <p className="text-[0.625rem] text-muted-foreground leading-relaxed">
                ※ 코로나 시기(2020~2021) 가중치 0.5 보정 적용.
              </p>
              <p className="text-[0.625rem] text-muted-foreground leading-relaxed">
                ※ 마포구 16동 × 24시간대 단일 학습. 다른 조합/시간대는 외삽 결과로 신뢰도 하락 가능.
              </p>
            </div>
          </div>
        )}

        {/* 섹션 2 — 타겟 고객 매출 기여 (4동 통합) */}
        {anySegment && (
          <div className="rounded-3xl border border-border bg-card p-6 space-y-6">
            <div className="flex items-center justify-between gap-4">
              <h3 className="flex items-center gap-3 text-xl font-black italic leading-none tracking-tight text-foreground">
                <Users className="text-primary" /> 타겟 고객 매출 기여
              </h3>
              {winnerSegment && (
                <div className="rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-[0.6875rem] font-black tabular-nums text-primary">
                  {winnerDistrict} 전체의 {(winnerSegment.segment_ratio * 100).toFixed(1)}%
                </div>
              )}
            </div>
            {winnerSegment && (
              <p className="text-[0.8125rem] text-foreground leading-relaxed">
                <span className="font-bold">{winnerDistrict}:</span>{' '}
                {humanizeProfileSummary(winnerSegment.profile_summary)}
              </p>
            )}
            <CustomerFlowSegmentChart dpredicts={dpredicts} mode="sales" />
            <CustomerFlowSegmentChart dpredicts={dpredicts} mode="dimensions" />
            <div className="pt-4 border-t border-border/50 space-y-1">
              <p className="text-[0.625rem] text-muted-foreground leading-relaxed">
                ※ 4차원(연령·성별·시간대·요일) 독립 가정(곱셈)으로 산출됩니다 — 실제 분포와 차이
                가능, 유동인구 실측치로 일부 보정.
              </p>
              <p className="text-[0.625rem] text-muted-foreground leading-relaxed">
                ※ 학습 데이터는 마포구 16동 × 10업종 · 2019~2024 4분기 기준. 다른 조합/연도는 외삽
                결과.
              </p>
            </div>
          </div>
        )}
      </div>
    );
  }

  // 단일 동 fallback (B5 결과 — top-level living_pop_forecast)
  const livingPop = simResult.living_pop_forecast ?? null;
  const hasLivingPop = Boolean(livingPop && livingPop.quarters && livingPop.quarters.length > 0);

  if (!hasLivingPop) {
    return (
      <div className="space-y-6">
        <div className="rounded-3xl border border-dashed border-border bg-card p-6 text-center">
          <Activity className="mx-auto text-muted-foreground mb-2" size={22} />
          <p className="text-xs text-muted-foreground">유동인구 피크 시간 예측 데이터 없음</p>
          <p className="mt-1 text-[0.625rem] text-muted-foreground">
            living_pop_forecast (TCN) 모델 호출 실패 시 표시됩니다
          </p>
        </div>
        <PlaceholderPanel
          modelName="customer_revenue"
          description="타겟 고객 매출 기여 endpoint 연동 후 활성화됩니다."
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* [D — living_pop_forecast P1-D] 유동인구 피크 시간 예측 (TCN) */}
      <PeakHourCard data={livingPop} />
    </div>
  );
}
