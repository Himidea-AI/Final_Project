# v4 → v4.1 비교 (Sprint 2)

## Sprint 2 변경
- Task 6 fix (acaf089): NaN-guard 순서 수정, 타입 힌트, CI 동기화
- Phase 1 재학습 + Phase 2 재감사

## 합격선 결과 비교

| 합격선 | v4 (Sprint 1) | v4.1 (Sprint 2) | 변화 |
|---|---|---|---|
| 1-1 std/mean | 0.0746 | 0.0746 | 0.00p |
| 1-2 CI 폭 | 0.2924 | 0.2924 | 0.00p |
| 1-3 외삽 셀 수 | 57/137 (41.6%) | 57/137 (41.6%) | 0% |
| 1-4 confidence 평균 | 0.666 (FAIL) | 0.666 (FAIL) | 0.00p |
| 2-1 Random WAPE | 9.48% | 9.48% | 0.00p |
| 2-2 TS WAPE | 12.76% | 12.76% | 0.00p |
| 2-3 MNAR WAPE | 21.23% (FAIL) | 21.23% (FAIL) | 0.00p |
| 2-4 LODO WAPE | 47.62% (FAIL) | 47.62% (FAIL) | 0.00p |
| 2-5 Q1 WAPE | 21.14% (FAIL) | 21.14% (FAIL) | 0.00p |
| 2-6 Pearson r | 0.9957 | 0.9957 | 0.0000p |
| 2-7 RMSLE | 0.3067 | 0.3067 | 0.0000p |
| 2-8 OoM | 0.9671 (FAIL) | 0.9671 (FAIL) | 0.0000p |
| 2-9 F1_4tier | 0.8697 | 0.8697 | 0.0000p |
| 2-10 MASE | 0.0849 | 0.0849 | 0.0000p |

## 해석

### NaN-guard fix의 영향

Task 6 fix(acaf089)에서 수정된 NaN-guard는 **dead code** 였다. 즉, Sprint 1 시점에 `df_alive`는 이미 `monthly_sales.notna()` 조건으로 필터된 행만 포함했기 때문에, "전체-NaN 행"이 실제로 존재하지 않았다. 결과적으로 fix 적용 전후 학습 데이터 구성이 동일하고, 모든 지표가 v4와 v4.1에서 bit-for-bit 동일하다.

- 합격선 1-1~1-3: 변화 없음 (std/mean, CI 폭, 외삽 셀)
- 합격선 1-4 confidence: 0.666 유지 (FAIL)
- audit 10개 지표 모두 변화 없음

### production_ready 변화

`production_ready = False` 유지. 실패 지표 4개:
- MNAR WAPE 21.23% (기준 15%) — 결측 복원 신뢰성 부족
- LODO WAPE 47.62% (기준 30%) — dong fixed effect 과의존
- Q1 WAPE 21.14% (기준 18%) — 소규모 셀 예측 불량
- OoM Accuracy 0.9671 (기준 0.97) — 크기 등급 정확도 미달

### 다음 sprint 권장

NaN-guard fix는 코드 품질 개선에는 기여하지만 모델 성능에는 영향 없음이 확인됨. 근본 문제는 dong-level feature 과의존(LODO 47.6%)과 소규모 셀의 낮은 신뢰도이다.

**Sprint 3 권장 방향:**
1. `dong_avg_store`, `combo_avg_store` 피처를 LOO(Leave-One-Out) 인코딩으로 교체 → LODO WAPE 개선
2. Q1 셀 전용 보정(별도 회귀 또는 가중치 부여) → Q1 WAPE 18% 이하 목표
3. 위 두 조치 후 OoM accuracy 자연 개선 기대
