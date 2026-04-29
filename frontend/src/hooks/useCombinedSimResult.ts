import { useMemo } from 'react';
import type {
  AnalysisOutput,
  ClosureRisk,
  DistrictPredictionResult,
  SimulationOutput,
} from '../types';
import { useSimulationStore } from '../stores/simulationStore';

/**
 * /predict + /analyze/llm 두 슬라이스를 SimulationOutput 호환 객체로 합성.
 * 기존 컴포넌트가 simResult 받는 prop 인터페이스 보존 → 변경 0.
 *
 * 부분 데이터 케이스:
 * - analysis 만 있음 (prediction 실패): ML 필드는 null, AI 분석 영역만 표시.
 * - prediction 만 있음 (analysis 실패): winner_district 없으므로 사용자 입력 동 기준.
 * - 둘 다 없음: null 반환.
 *
 * 2026-04-29 multi-district cycle (M4):
 * - district_predictions 배열을 그대로 보존하여 멀티동 차트가 활용 가능.
 * - DistrictPredictionResult 11 필드 스키마 적용 — bep_months / predicted_monthly_revenue 는
 *   winner 동의 bep dict / quarterly_projection 첫 분기에서 파생 (legacy 호환용).
 */
export function buildCombinedResult(
  prediction: DistrictPredictionResult[] | null,
  analysis: AnalysisOutput | null,
  fallbackTargetDistrict: string | undefined,
): SimulationOutput | null {
  if (!analysis && !prediction) return null;

  // winner 동 결정 — analysis 우선, 없으면 prediction 의 첫 비-excluded entry, 그 외 fallback
  const winner =
    analysis?.winner_district ??
    prediction?.find((p) => !p.is_excluded_combo)?.district ??
    fallbackTargetDistrict ??
    null;

  // winner 동의 ML 필드 추출 (없거나 excluded 면 null)
  const winnerPred = prediction?.find((p) => p.district === winner && !p.is_excluded_combo);

  // bep_months: backend bep dict 의 bep_months 또는 (legacy 평면 필드) 에서 추출.
  // backend (수지니 c8ea31f) 는 bep: Record<string, unknown> 으로 보내며, 내부에
  // bep_quarters / bep_months / quarterly_simulation 등이 들어올 수 있음.
  const bepRecord = (winnerPred?.bep ?? null) as Record<string, unknown> | null;
  const bepMonthsRaw = bepRecord?.bep_months;
  const bepMonths = typeof bepMonthsRaw === 'number' ? bepMonthsRaw : null;

  // predicted_monthly_revenue: winner 동의 첫 분기 매출 / 3 (분기 → 월 추정).
  // backend 가 별도 필드로 안 보내므로 quarterly_projection 에서 파생.
  const firstQuarter = winnerPred?.quarterly_projection?.[0];
  const predictedMonthlyRevenue =
    typeof firstQuarter?.revenue === 'number' ? firstQuarter.revenue / 3 : null;

  // SimulationOutput / DistrictPredictionResult 모두 quarterly_projection 은 QuarterlyProjection[]
  // 으로 통일됨 (M1). winner 동의 배열을 그대로 노출, 없으면 빈 배열.
  return {
    ...(analysis ?? ({} as AnalysisOutput)),
    quarterly_projection: winnerPred?.quarterly_projection ?? [],
    closure_risk: (winnerPred?.closure_risk as ClosureRisk | null | undefined) ?? null,
    shap_result: winnerPred?.shap_result ?? null,
    bep_months: bepMonths,
    predicted_monthly_revenue: predictedMonthlyRevenue,
    district_predictions: prediction ?? [],
  } as SimulationOutput;
}

/**
 * Combined SimulationOutput selector hook. zustand subscribe + useMemo.
 *
 * 기존 패턴 `useSimulationStore((s) => s.result)` 의 직접 대체.
 */
export function useCombinedSimResult(): SimulationOutput | null {
  const prediction = useSimulationStore((s) => s.prediction.data);
  const analysis = useSimulationStore((s) => s.analysis.data);
  const params = useSimulationStore((s) => s.params);

  return useMemo(
    () => buildCombinedResult(prediction, analysis, params?.target_district ?? undefined),
    [prediction, analysis, params],
  );
}
