/**
 * PredictCustomerFlowTab — 고객·유동인구 예측 서브탭
 *
 * 2026-04-29 (Task B5): DemographicTab 에 있던 PeakHourCard (living_pop_forecast)
 * 를 [예측] - [고객·유동인구] 탭으로 이동. 유동인구는 예측 영역에 더 자연스러움.
 */

import { Activity } from 'lucide-react';
import type { SimulationOutput } from '../../../../../types';
import { PeakHourCard } from '../../charts/PeakHourCard';
import { PlaceholderPanel } from '../../shared/PlaceholderPanel';

interface Props {
  simResult: SimulationOutput;
}

export function PredictCustomerFlowTab({ simResult }: Props) {
  // [D] 유동인구 피크 시간 예측 (TCN)
  const livingPop = simResult.living_pop_forecast ?? null;
  const hasLivingPop = Boolean(livingPop && livingPop.quarters && livingPop.quarters.length > 0);

  if (!hasLivingPop) {
    return (
      <div className="space-y-6">
        <div className="rounded-3xl border border-dashed border-stone-800 bg-stone-950/40 p-6 text-center">
          <Activity className="mx-auto text-stone-600 mb-2" size={22} />
          <p className="text-xs text-stone-500">유동인구 피크 시간 예측 데이터 없음</p>
          <p className="mt-1 text-[0.625rem] text-stone-600">
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
