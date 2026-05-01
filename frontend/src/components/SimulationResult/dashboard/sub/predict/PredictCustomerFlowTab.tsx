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
 */

import { Activity } from 'lucide-react';
import type { CustomerSegment, LivingPopForecast, SimulationOutput } from '../../../../../types';
import { CustomerSegmentCard } from '../../charts/CustomerSegmentCard';
import { PeakHourCard } from '../../charts/PeakHourCard';
import { PlaceholderPanel } from '../../shared/PlaceholderPanel';

interface Props {
  simResult: SimulationOutput;
}

export function PredictCustomerFlowTab({ simResult }: Props) {
  const dpredicts = (simResult.district_predictions ?? []).filter((p) => !p.is_excluded_combo);

  // 다중 동 (district_predictions) 모드
  if (dpredicts.length > 0) {
    // backend 미구현 → 모든 동에서 두 필드 모두 null 가능. anyData false 면 안내.
    const anyData = dpredicts.some(
      (p) => p.living_pop_forecast != null || p.customer_segment != null,
    );

    if (!anyData) {
      return (
        <div className="space-y-6">
          <PlaceholderPanel
            modelName="customer_revenue + living_pop_forecast"
            description="동별 고객 세그먼트 + 유동인구 피크 데이터는 backend /predict 응답에서 미수신 상태입니다. 백엔드 추가 후 활성화."
          />
        </div>
      );
    }

    return (
      <div className="space-y-6">
        <h4 className="text-xs font-black text-muted-foreground uppercase tracking-widest">
          동별 유동인구 피크 / 고객 세그먼트
        </h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {dpredicts.map((p) => {
            const livingPop = p.living_pop_forecast as LivingPopForecast | null;
            const segment = p.customer_segment as CustomerSegment | null;
            return (
              <div
                key={p.district}
                className="bg-card/40 border border-border/60 rounded-3xl p-4 space-y-3"
              >
                <div className="text-xs font-bold text-foreground">{p.district}</div>
                {livingPop ? (
                  <PeakHourCard data={livingPop} />
                ) : (
                  <div className="text-[0.625rem] text-muted-foreground">
                    유동인구 데이터 미수신
                  </div>
                )}
                {segment ? (
                  <CustomerSegmentCard segment={segment} />
                ) : (
                  <div className="text-[0.625rem] text-muted-foreground">
                    고객 세그먼트 데이터 미수신
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // 단일 동 fallback (B5 결과 — top-level living_pop_forecast)
  const livingPop = simResult.living_pop_forecast ?? null;
  const hasLivingPop = Boolean(livingPop && livingPop.quarters && livingPop.quarters.length > 0);

  if (!hasLivingPop) {
    return (
      <div className="space-y-6">
        <div className="rounded-3xl border border-dashed border-border bg-card/40 p-6 text-center">
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
