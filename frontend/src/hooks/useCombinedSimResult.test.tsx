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
    expect(result?.quarterly_projection).toBeNull();
    expect(result?.closure_risk).toBeNull();
    expect(result?.district_predictions).toEqual([]);
  });

  it('prediction 만 있음 → winner=fallback, ML 필드는 첫 비-excluded entry', () => {
    const pred = [{ district: '공덕동', is_excluded_combo: false, bep_months: 12 } as any];
    const result = buildCombinedResult(pred, null, '공덕동');
    expect(result?.winner_district).toBeUndefined(); // analysis 없음
    expect(result?.bep_months).toBe(12);
    expect(result?.district_predictions).toEqual(pred);
  });

  it('둘 다 있음 → winner=analysis 기준 ML 추출', () => {
    const pred = [
      { district: '공덕동', is_excluded_combo: false, bep_months: 12 } as any,
      { district: '합정동', is_excluded_combo: false, bep_months: 18 } as any,
    ];
    const analysis = { winner_district: '합정동', target_district: '공덕동' } as any;
    const result = buildCombinedResult(pred, analysis, '공덕동');
    expect(result?.winner_district).toBe('합정동');
    expect(result?.bep_months).toBe(18); // 합정동의 ML 추출
  });

  it('winner 가 excluded → ML 필드 null', () => {
    const pred = [{ district: '공덕동', is_excluded_combo: true } as any];
    const analysis = { winner_district: '공덕동' } as any;
    const result = buildCombinedResult(pred, analysis, undefined);
    expect(result?.winner_district).toBe('공덕동');
    expect(result?.bep_months).toBeNull(); // excluded 라 추출 안 됨
  });
});
