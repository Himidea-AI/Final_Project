/**
 * PredictEmergingDistrictTab — 동별 상권 조기감지 신호
 *
 * /predict 응답의 district_predictions[].emerging_signal 을 동별 카드 grid 로 렌더.
 * 2026-04-29 multi-district visual cycle (M11) — placeholder 해제.
 *
 * backend (수지니 c8ea31f) 는 DistrictPredictionResult.emerging_signal 필드를 아직 미구현 →
 * 모든 동에서 null 인 경우 PlaceholderPanel 안내. mock 절대 금지.
 */

import type { SimulationOutput, EmergingSignal } from '../../../../../types';
import { EmergingSignalCard } from '../../charts/EmergingSignalCard';
import { PlaceholderPanel } from '../../shared/PlaceholderPanel';
import { resolveDongName } from '../../../../../constants/mapoDongs';

interface Props {
  simResult: SimulationOutput;
}

export function PredictEmergingDistrictTab({ simResult }: Props) {
  const dpredicts = (simResult.district_predictions ?? []).filter((p) => !p.is_excluded_combo);

  if (dpredicts.length === 0) {
    return (
      <div className="space-y-6">
        <PlaceholderPanel description="동별 예측 데이터가 도착하면 상권 조기감지 신호가 표시됩니다." />
      </div>
    );
  }

  const anyData = dpredicts.some((p) => p.emerging_signal != null);
  if (!anyData) {
    return (
      <div className="space-y-6">
        <PlaceholderPanel description="동별 상권 조기감지 신호 데이터를 받지 못했습니다. 잠시 후 다시 시도해주세요." />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h4 className="text-xs font-black text-muted-foreground uppercase tracking-widest">
        동별 상권 조기감지 신호
      </h4>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {dpredicts.map((p) => {
          // p.district 가 raw code(11440660)로 올 가능성 대비 한국어 이름으로 휴머나이즈.
          const districtLabel = resolveDongName(p.district) ?? p.district;
          return (
            <div
              key={p.district}
              className="bg-card border border-border rounded-3xl p-4 space-y-3"
            >
              <div className="text-xs font-black text-foreground uppercase tracking-widest">
                {districtLabel}
              </div>
              {p.emerging_signal ? (
                <EmergingSignalCard signal={p.emerging_signal as unknown as EmergingSignal} />
              ) : (
                <div className="rounded-2xl border border-dashed border-border bg-secondary p-4 text-[0.625rem] text-muted-foreground">
                  상권 조기감지 신호 미수신
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
