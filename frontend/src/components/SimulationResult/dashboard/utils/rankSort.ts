/**
 * rankSort — 4동 비교 차트의 ranking 정렬 helper.
 *
 * Deep Blue Sequential 4-tier (palette-catalog SoT) 와 idx 매핑이 1:1 정합:
 *   idx 0 = winner (--rank-1 Deep Blue)
 *   idx 1 = top_3_candidates[0] (--rank-2 Electric Blue)
 *   idx 2 = top_3_candidates[1] (--rank-3 Sky Blue)
 *   idx 3 = top_3_candidates[2] or 입력 잔여 (--rank-4 Ice Blue, dashed 권장)
 *
 * 모든 4동 비교 차트는 dpredicts 사용 직전에 sortByRanking 을 통과시켜
 * SERIES_COLORS[idx] 매핑이 ranking 의미와 어긋나지 않도록 한다.
 */
import type { DistrictPredictionResult, SimulationOutput } from '../../../../types';

/**
 * dpredicts 를 simResult 의 ranking 순으로 정렬.
 * 우선순위: winner_district → top_3_candidates 순서 → 그 외 입력 순서 보존.
 *
 * winner 미명시 또는 ranking 미수신 시 dpredicts 그대로 반환 (안전 fallback).
 */
export function sortByRanking(
  dpredicts: DistrictPredictionResult[],
  simResult: SimulationOutput,
): DistrictPredictionResult[] {
  const winner = simResult.winner_district;
  const top3 = simResult.top_3_candidates ?? [];
  if (!winner) return dpredicts;

  const order = [winner, ...top3.filter((d) => d !== winner)];
  const indexed = new Map(dpredicts.map((p) => [p.district, p]));
  const sorted: DistrictPredictionResult[] = [];

  // ranking 순서대로 추가
  for (const district of order) {
    const p = indexed.get(district);
    if (p) {
      sorted.push(p);
      indexed.delete(district);
    }
  }
  // 잔여 (ranking 에 없는 입력) — 입력 순서 보존
  for (const p of dpredicts) {
    if (indexed.has(p.district)) {
      sorted.push(p);
      indexed.delete(p.district);
    }
  }
  return sorted;
}
