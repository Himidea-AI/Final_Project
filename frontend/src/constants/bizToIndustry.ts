/**
 * business_type → industry_code 매핑.
 *
 * SoT: backend `src/agents/tools.py` `_MarketDataTool._SALES_CODE_MAP`.
 * backend 변경 시 이 dict 도 같이 갱신해야 함 (drift 위험).
 *
 * 사용처: TCN 시나리오 시뮬레이터 — `/predict/sensitivity` 호출 인자.
 */
export const BIZ_TO_INDUSTRY_CODE: Record<string, string> = {
  // CS100001 한식
  한식: 'CS100001',
  한식음식점: 'CS100001',
  음식점: 'CS100001',
  restaurant: 'CS100001',
  // CS100002 중식
  중식: 'CS100002',
  중식음식점: 'CS100002',
  // CS100003 일식
  일식: 'CS100003',
  일식음식점: 'CS100003',
  // CS100004 양식
  양식: 'CS100004',
  양식음식점: 'CS100004',
  // CS100005 제과/베이커리
  제과점: 'CS100005',
  베이커리: 'CS100005',
  // CS100006 패스트푸드
  패스트푸드: 'CS100006',
  버거: 'CS100006',
  // CS100007 치킨
  치킨: 'CS100007',
  치킨전문점: 'CS100007',
  chicken: 'CS100007',
  // CS100008 분식
  분식: 'CS100008',
  분식전문점: 'CS100008',
  // CS100009 호프/주점
  호프: 'CS100009',
  주점: 'CS100009',
  // CS100010 카페/음료
  카페: 'CS100010',
  커피: 'CS100010',
  cafe: 'CS100010',
  coffee: 'CS100010',
  // 편의점
  편의점: 'CS200009',
  convenience: 'CS200009',
};

export function resolveBizToIndustry(biz: string | undefined | null): string | null {
  if (!biz) return null;
  return BIZ_TO_INDUSTRY_CODE[biz.toLowerCase()] ?? BIZ_TO_INDUSTRY_CODE[biz] ?? null;
}
