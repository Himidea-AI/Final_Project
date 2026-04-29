import { describe, it, expect } from 'vitest';
import { buildCombinedResult } from './useCombinedSimResult';

describe('buildCombinedResult', () => {
  it('둘 다 null → null', () => {
    expect(buildCombinedResult(null, null, undefined)).toBeNull();
  });

  it('analysis 만 있음 → ML 필드 null, winner=analysis.winner', () => {
    const result = buildCombinedResult(
      null,
      { winner_district: '공덕동', target_district: '공덕동' } as any,
      undefined,
    );
    expect(result?.winner_district).toBe('공덕동');
    // M4: quarterly_projection 은 QuarterlyProjection[] 로 통일 — 비어있으면 [].
    expect(result?.quarterly_projection).toEqual([]);
    expect(result?.closure_risk).toBeNull();
    expect(result?.district_predictions).toEqual([]);
  });

  it('prediction 만 있음 → winner=fallback, ML 필드는 첫 비-excluded entry', () => {
    // M4: backend 가 bep_months 를 bep dict 안에 보냄 (수지니 c8ea31f).
    const pred = [{ district: '공덕동', is_excluded_combo: false, bep: { bep_months: 12 } } as any];
    const result = buildCombinedResult(pred, null, '공덕동');
    expect(result?.winner_district).toBeUndefined(); // analysis 없음
    expect(result?.bep_months).toBe(12);
    expect(result?.district_predictions).toEqual(pred);
  });

  it('둘 다 있음 → winner=analysis 기준 ML 추출', () => {
    const pred = [
      { district: '공덕동', is_excluded_combo: false, bep: { bep_months: 12 } } as any,
      { district: '합정동', is_excluded_combo: false, bep: { bep_months: 18 } } as any,
    ];
    const analysis = { winner_district: '합정동', target_district: '공덕동' } as any;
    const result = buildCombinedResult(pred, analysis, '공덕동');
    expect(result?.winner_district).toBe('합정동');
    expect(result?.bep_months).toBe(18); // 합정동의 ML 추출
  });

  it('winner 가 excluded → ML 필드 null', () => {
    const pred = [{ district: '공덕동', is_excluded_combo: true, bep: { bep_months: 12 } } as any];
    const analysis = { winner_district: '공덕동' } as any;
    const result = buildCombinedResult(pred, analysis, undefined);
    expect(result?.winner_district).toBe('공덕동');
    expect(result?.bep_months).toBeNull(); // excluded 라 추출 안 됨
  });

  it('district_predictions 다중 동 보존 — 멀티동 차트 활용 가능', () => {
    const pred = [
      {
        district: '공덕동',
        is_excluded_combo: false,
        quarterly_projection: [{ quarter: 1, revenue: 30_000_000, cumulative_profit: 0 } as any],
      } as any,
      {
        district: '합정동',
        is_excluded_combo: false,
        quarterly_projection: [{ quarter: 1, revenue: 60_000_000, cumulative_profit: 0 } as any],
      } as any,
      { district: '망원동', is_excluded_combo: false } as any,
    ];
    const analysis = { winner_district: '공덕동' } as any;
    const result = buildCombinedResult(pred, analysis, undefined);
    expect(result?.district_predictions).toHaveLength(3);
    // predicted_monthly_revenue = winner 동(공덕동) 의 첫 분기 매출 / 3
    expect(result?.predicted_monthly_revenue).toBe(10_000_000);
  });
});
