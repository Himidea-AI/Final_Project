/**
 * baseline.ts — SensitivityResponse → 점포당 분기 매출(원, 길이 4) 선택 헬퍼.
 *
 * 명세서 §2 SoT: scenario 시뮬레이터 모든 표시 단위는 "점포당 분기 매출(원)".
 * backend (sensitivity.py:65-73) 가 baseline_sales(합계) 와 baseline_per_store(점포당) 를
 * 분리 제공하므로, frontend 는 항상 점포당 값을 선택해야 한다.
 *
 * IM3-144 회귀 차단 — baseline_sales 직접 참조 시 store_count 만큼 부풀려진 합계를
 * "점포당 분기 매출" 라벨로 표시하는 단위 mismatch 가 발생.
 */

import type { SensitivityResponse } from '../../../../types/elasticity';

/**
 * SensitivityResponse 에서 "점포당 분기 매출(원, 길이 4)" 를 선택하는 정통 헬퍼.
 * 우선순위:
 *  1. backend v3+ 가 제공한 baseline_per_store (이미 ÷ store_count 적용됨)
 *  2. store_count > 0 일 때 baseline_sales / store_count 폴백
 *  3. (legacy) baseline_sales 그대로 — 단위 mismatch 표시이지만 crash 회피
 */
export function selectPerStoreBaseline(data: SensitivityResponse): number[] {
  if (data.baseline_per_store && data.baseline_per_store.length === 4) {
    return data.baseline_per_store;
  }
  if (data.store_count && data.store_count > 0) {
    return data.baseline_sales.map((v) => v / data.store_count!);
  }
  return data.baseline_sales;
}
