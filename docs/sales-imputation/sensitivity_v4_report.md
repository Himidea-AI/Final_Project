# Sensitivity v4 ABM Report

**합격선 4-1 (sensitivity ≥ 8%):** ❌ 0.00%
**v4 신규 popularity 셀 (결측 보강 효과):** 0

## 결과
- v4 적용 popularity 평균: 0.557 (1649 cells)
- baseline popularity 평균: 0.557 (1649 cells)
- 공통 cell 의 popularity 평균 변화: 0.00%

## 진단: 0% 원인 분석

| 항목 | 값 |
|------|-----|
| `district_sales_seoul` 최신 분기 | 20254 (2025 Q4) |
| `seoul_district_sales_imputed_v4` 최신 분기 | 20244 (2024 Q4) |
| `world_loader` 기준 분기 (`MAX(quarter) - 1`) | 20253 |
| v4 총 rows | 137 |
| v4 distinct (dong_code, industry_code) | 13 |
| 두 테이블 간 quarter 공통 교집합 (JOIN 성공) | 0 rows |

`_load_dong_industry_weight()` SQL 은 `district_sales_seoul` 에서 최신 2개 분기(20253, 20254)를 필터한다. v4 는 2024Q4(20244) 까지만 적재되어 있어 LEFT JOIN 매칭이 전혀 발생하지 않는다. `COALESCE(v.monthly_sales, s.monthly_sales)` 는 항상 `s.monthly_sales` 를 반환하고 `COALESCE(v.confidence, 1.0)` 는 항상 1.0 을 반환한다.

## 근본 원인

v4 imputed 데이터는 **결측 셀**(특정 (dong, industry, quarter) 조합이 `district_sales_seoul` 에 아예 없는 경우)을 채우기 위해 설계되었다. 그런데 `world_loader` 쿼리는 **존재하는** 최신 분기 데이터를 기준으로 LEFT JOIN 을 수행하므로, v4 가 덮어쓸 수 있는 행이 없다.

즉, v4 적재가 정상적으로 완료되었더라도 `world_loader` popularity 계산에 미치는 영향은 구조적으로 0이다.

## 해석

v4 도입 영향이 미미 (0.0% < 8%) — 정직 명시.

이 결과는 스크립트 오류가 아닌 **데이터 범위 불일치**로 인한 것임. v4 테이블(137 rows, 2019–2024 결측 셀)이 world_loader 가 참조하는 2025 Q3/Q4 최신 데이터와 분기가 겹치지 않는다.

## 후속 권고

1. **단기 (sprint 내):** `_load_dong_industry_weight()` 에서 `quarter >= MAX - 1` 을 좀 더 넓은 범위로 변경하거나, 별도 쿼리로 v4 데이터(결측 셀 보강)를 직접 조회하는 경로 추가 검토.
2. **중기:** v4 imputed 결과를 최신 분기 데이터가 없는 (dong, industry) 조합에 대한 popularity fallback 으로 활용하는 방식으로 world_loader 개선.
3. **정직 기록:** Phase 4 sensitivity 합격 기준 미달 — v4 sprint 가치는 DB 데이터 정합성(137 결측 셀 복원) 에서 입증되며, ABM popularity 전파는 아직 미완.
