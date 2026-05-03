/**
 * Elasticity (TCN 시나리오 시뮬레이터) 응답 타입.
 *
 * 백엔드 엔드포인트: GET /predict/sensitivity?dong_code=&industry_code=
 *
 * elasticity[feature][level] = 해당 피처를 level(%) 변동시켰을 때 연 매출 변화율(%).
 * 매출 식: baseline_sales × (1 + Σ(slider_pct/100)) — sliders 4개 선형 결합.
 * quarter_num 은 별도 정보 (기준선에 이미 반영, 표시용).
 *
 * level 키 형식 — JSON 명세 그대로:
 *   "-30", "-20", "-10", "0", "+10", "+20", "+30"  (양수에 + prefix)
 *
 * correlations 키 형식: "{from}→{to}"  (peer 매칭에 사용).
 */

export interface ElasticityResponse {
  elasticity: {
    rent_1f: Record<string, number>;
    vacancy_rate: Record<string, number>;
    floating_pop: Record<string, number>;
    trend_score: Record<string, number>;
    quarter_num: Record<'Q1' | 'Q2' | 'Q3' | 'Q4', number>;
  };
  correlations: Record<string, number>;
  baseline_sales: number[];
}

export type ElasticityFeature = 'rent_1f' | 'vacancy_rate' | 'floating_pop' | 'trend_score';
