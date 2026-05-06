/**
 * PredictEmergingDistrictTab — 동별 상권 조기감지 신호
 *
 * /predict 응답의 district_predictions[].emerging_signal 을 동별 카드 grid 로 렌더.
 * 2026-04-29 multi-district visual cycle (M11) — placeholder 해제.
 *
 * backend (수지니 c8ea31f) 는 DistrictPredictionResult.emerging_signal 필드를 아직 미구현 →
 * 모든 동에서 null 인 경우 PlaceholderPanel 안내. mock 절대 금지.
 */

import { Sparkles } from 'lucide-react';
import type { SimulationOutput } from '../../../../../types';
import { EmergingSignalCard } from '../../charts/EmergingSignalCard';
import { PlaceholderPanel } from '../../shared/PlaceholderPanel';
import { resolveDongName } from '../../../../../constants/mapoDongs';
import { SERIES_COLORS } from '../../../QuarterlyProjectionChart';
import { sortByRanking } from '../../utils/rankSort';

interface Props {
  simResult: SimulationOutput;
}

export function PredictEmergingDistrictTab({ simResult }: Props) {
  // sortByRanking 으로 winner→4위 순 정렬 → SERIES_COLORS[idx] 가 다른 탭들과 동일 색 매핑.
  const dpredicts = sortByRanking(
    (simResult.district_predictions ?? []).filter((p) => !p.is_excluded_combo),
    simResult,
  );

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

  // 4동 비교 — anomaly_score 최댓값 동 1개에만 "변화 1위" 배지. 0 이하는 의미 없어 강조 안 함.
  const topDistrict =
    dpredicts.reduce<{ district: string; score: number } | null>((acc, p) => {
      const s = p.emerging_signal?.anomaly_score ?? -1;
      if (s <= 0) return acc;
      if (!acc || s > acc.score) return { district: p.district, score: s };
      return acc;
    }, null)?.district ?? null;

  return (
    <div className="space-y-6">
      <h3 className="flex items-center gap-3 text-xl font-black italic leading-none tracking-tight text-foreground">
        <Sparkles className="text-primary" /> 동별 상권 조기감지 신호
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {dpredicts.map((p, idx) => {
          // p.district 가 raw code(11440660)로 올 가능성 대비 한국어 이름으로 휴머나이즈.
          const districtLabel = resolveDongName(p.district) ?? p.district;
          const seriesColor = SERIES_COLORS[idx % SERIES_COLORS.length];
          return (
            <div key={p.district} className="bg-card border border-border rounded-3xl p-5">
              {p.emerging_signal ? (
                <EmergingSignalCard
                  signal={p.emerging_signal}
                  district={districtLabel}
                  isTopChange={topDistrict === p.district}
                  seriesColor={seriesColor}
                />
              ) : (
                <div className="space-y-3">
                  <div className="text-sm font-black text-foreground tracking-tight">
                    {districtLabel}
                  </div>
                  <div className="rounded-2xl border border-dashed border-border bg-secondary p-4 text-[0.625rem] text-muted-foreground">
                    상권 조기감지 신호 미수신
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
