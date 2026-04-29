import { useMemo } from 'react';
import type { AnalysisOutput, DistrictPredictionResult, SimulationOutput } from '../types';
import { useSimulationStore } from '../stores/simulationStore';

/**
 * /predict + /analyze/llm 두 슬라이스를 SimulationOutput 호환 객체로 합성.
 * 기존 컴포넌트가 simResult 받는 prop 인터페이스 보존 → 변경 0.
 *
 * 부분 데이터 케이스:
 * - analysis 만 있음 (prediction 실패): ML 필드는 null, AI 분석 영역만 표시.
 * - prediction 만 있음 (analysis 실패): winner_district 없으므로 사용자 입력 동 기준.
 * - 둘 다 없음: null 반환.
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

  // SimulationOutput.quarterly_projection 은 QuarterlyProjection[] 배열이지만
  // DistrictPredictionResult.quarterly_projection 은 단건. winner 동의 단건을
  // 그대로 노출 (기존 컴포넌트는 배열·단건 양쪽을 안전하게 다루도록 nullable 가드).
  // 타입은 SimulationOutput 와 호환되지 않는 부분이 있어 unknown 경유로 cast.
  return {
    ...(analysis ?? ({} as AnalysisOutput)),
    quarterly_projection: winnerPred?.quarterly_projection ?? null,
    closure_risk: winnerPred?.closure_risk ?? null,
    shap_result: winnerPred?.shap_result ?? null,
    bep_months: winnerPred?.bep_months ?? null,
    predicted_monthly_revenue: winnerPred?.predicted_monthly_revenue ?? null,
    district_predictions: prediction ?? [],
  } as unknown as SimulationOutput;
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
