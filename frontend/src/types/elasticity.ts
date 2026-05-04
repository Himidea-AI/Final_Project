/**
 * Elasticity (TCN v3 시나리오 시뮬레이터) 응답 타입.
 *
 * 백엔드 엔드포인트: GET /predict/sensitivity?dong_code=&industry_code=
 *
 * v3 schema (Phase 1 + sensitivity_cache.json 적용):
 *   - elasticity[slider][level] = list[float] 4분기 시계열 (분기별 % 변화)
 *   - baseline_sales = 점포당 분기 매출(원), 길이 4
 *   - 매출 식: baseline[q] × (1 + Σ(elasticity[slider][level][q]/100))
 *   - quarter_num 은 categorical → 합산 대상 제외 (별도 분기 비교 차트)
 *
 * level 키 형식 — JSON 명세 그대로:
 *   - vacancy_rate / trend_score / cpi_index / opr_sale_mt_avg:
 *       "-30" | "-20" | "-10" | "0" | "+10" | "+20" | "+30"  (양수 + prefix)
 *   - quarter_num: "Q1" | "Q2" | "Q3" | "Q4"
 *
 * correlations 키 형식: "{from}__{to}" 또는 "{from}↔{to}" — 둘 다 매칭 (parseCorrelationKey 참조).
 */

export type SliderKey =
  | 'vacancy_rate'
  | 'trend_score'
  | 'cpi_index'
  | 'opr_sale_mt_avg'
  | 'quarter_num';

/** /predict/sensitivity 응답 (v3) */
export interface SensitivityResponse {
  /** 슬라이더별 4분기 % 변화율
   *  - vacancy_rate / trend_score / cpi_index / opr_sale_mt_avg:
   *      key = "-30" | "-20" | "-10" | "0" | "+10" | "+20" | "+30" (string)
   *      value = [Q1, Q2, Q3, Q4] 분기별 % 변화 (예: 21.22 = +21.22%)
   *  - quarter_num:
   *      key = "Q1" | "Q2" | "Q3" | "Q4"
   *      value = [Q1, Q2, Q3, Q4] 분기별 절댓값 % (categorical)
   */
  elasticity: Record<SliderKey, Record<string, number[]>>;

  /** 슬라이더 페어 상관관계 (Pearson r, -1~1) */
  correlations: Record<string, number>;

  /**
   * 동×업종 합계 분기 매출 (원) — 길이 4.
   * 점포당 표시는 baseline_per_store 또는 ÷ store_count 사용 권장 (selectPerStoreBaseline 헬퍼 참조).
   */
  baseline_sales: number[];

  /**
   * 점포당 분기 매출 (원) — 길이 4.
   * backend v3+ 에서만 제공, 미존재 캐시 호환 위해 optional.
   */
  baseline_per_store?: number[] | null;

  /** 동×업종 최근 분기 점포 수 — baseline_per_store 미존재 시 baseline_sales / store_count 폴백. */
  store_count?: number | null;
}

export const SLIDER_LABELS: Record<SliderKey, string> = {
  vacancy_rate: '공실률',
  trend_score: '트렌드 점수',
  cpi_index: '물가지수(CPI)',
  opr_sale_mt_avg: '상권 활성도',
  quarter_num: '분기',
};

/** 슬라이더 ⓘ 툴팁 (명세서 §4.2) */
export const SLIDER_TOOLTIPS: Record<SliderKey, string> = {
  vacancy_rate: '주변 공실률이 변할 때 매출 영향 — 단기 영향이 큼',
  trend_score: '트렌드 변수는 단기 매출 영향이 작아 그래프가 거의 평행하게 보일 수 있습니다',
  cpi_index: '물가 변동의 매출 영향 — 영향 강도 큼',
  opr_sale_mt_avg: '상권 운영매출 평균 변화 — 분기 spread 명확',
  quarter_num: '관측 시작 분기 — Q1~Q4 4개 라인 비교',
};

/** %섭동 슬라이더 4종 (선형 합산 대상). quarter_num 은 별도 categorical 처리. */
export const PCT_SLIDER_KEYS: ReadonlyArray<Exclude<SliderKey, 'quarter_num'>> = [
  'vacancy_rate',
  'trend_score',
  'cpi_index',
  'opr_sale_mt_avg',
] as const;

export type PctSliderKey = (typeof PCT_SLIDER_KEYS)[number];
export type QuarterKey = 'Q1' | 'Q2' | 'Q3' | 'Q4';
