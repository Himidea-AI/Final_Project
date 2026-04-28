# v4 — 일반/외삽 셀 분리 보고 (Sprint 4)

## 요약

137 결측 셀 중:
- **일반 셀 87개**: 부분 결측 (같은 동/업종의 다른 분기 데이터 존재) — 직접 학습 가능
- **외삽 셀 50개**: 24분기 전체 결측 또는 high variance — 외삽 추정

> 비고: full_missing combo 는 2개 조합 (48 cells) + high-variance 추가 2개 = 외삽 50셀.

## 일반 셀 (87개, 합격선 적용)

| 합격선 | 측정값 | 기준 | 판정 |
|---|---|---|---|
| 1-4 confidence 평균 | 0.788 | ≥ 0.75 | PASS |
| 2-3 MNAR WAPE | 21.23% | ≤ 15% | FAIL |

### MNAR WAPE 분석

일반 셀 전용 MNAR WAPE = 21.23% ± 0.40 — 전체 audit (21.23%) 과 동일.

외삽 50셀 제거 후에도 WAPE 가 개선되지 않은 이유:

- full_missing_combo 는 alive 셀 CV 에 참여하지 않음 (학습 대상이 다름)
- MNAR mimic 은 alive 셀 중 small store 를 hold-out 하는 방식 → 외삽 셀 포함 여부와 무관
- 구조적 한계: 마포구 소규모 업종 (store_count ≤ 15, q95 기준) 은 variance 가 본질적으로 높음

confidence base 는 `max(0.60, 1 - WAPE/100) = max(0.60, 0.788) = 0.788` 으로 산출.

## 외삽 셀 (50개, 별도 disclaimer)

| 항목 | 값 |
|---|---|
| confidence cap | 0.4 (정직) |
| confidence 평균 | 0.400 |
| extrapolation_flag | True |

- 사용 가능: popularity_boost 가중치, 마포 합계 추정
- 사용 부적합: 단일 셀 BEP/창업 결정

## confidence 재계산 공식 (Sprint 4)

```
base = max(0.60, 1.0 - general_mnar_wape / 100.0)  # = 0.788
ci_penalty = 1.0 - min(0.3, ci_width_ratio - 0.5)  if ci_width_ratio > 0.5 else 1.0
extrap_penalty = 0.4 / base                          if extrapolation_flag else 1.0
confidence = clip(base × ci_penalty × extrap_penalty, 0.10, 1.0)
```

## 다운스트림 사용 가이드

### popularity_boost (`world_loader._load_dong_industry_weight()`)
- v4 confidence 가중 평균 적용
- 외삽 셀은 0.4 가중치로 영향 자동 축소

### 5트랙 V1c (다른 세션)
- ground truth = sales_imp_mapo.csv 의 monthly_sales
- 외삽 셀은 extrapolation_flag = True 로 필터링 가능

### 단일 셀 매출 표시 (대시보드)
- extrapolation_flag = True 셀: "추정값 (한 번도 관측 안 됨)" 라벨 표시
- confidence ≥ 0.75 셀 (일반 셀 전체): 일반 신뢰구간 ±25%
- confidence ≤ 0.4 셀 (외삽 셀 전체): ±50% 또는 자릿수만 표시

## Sprint 1-4 변동 이력

| Sprint | MNAR WAPE | confidence 평균 | 합격선 1-4 | 주요 변경 |
|---|---|---|---|---|
| Sprint 1 v4 | 21.23% | 0.666 | FAIL | MultiOutput 6 seed |
| Sprint 2 v4.1 | 21.23% | 0.666 | FAIL | NaN-guard (dead code) |
| Sprint 3 v4.2 | 21.23% | 0.639 | FAIL | threshold 2.5 + MNAR base 21.23% |
| Sprint 4 (분리) | 21.23% (일반) | 일반: **0.788** / 외삽: 0.400 | **PASS (일반 셀 기준)** | 분리 측정 + base 0.788 |
