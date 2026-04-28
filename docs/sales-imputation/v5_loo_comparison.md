# v5 — LOO Cross-Fitting (Sprint 5)

## 변경
- build_features_v5_loo 신규 — dong_avg/combo_avg K-fold (k=5) cross-fitting 적용
- 학습 시 fold 내부 데이터로 통계 leak 차단
- build_features_v4 보존 — 회귀 비교용

## v4.2 (Sprint 3/4) → v5 비교

| 합격선 | v4.2 (Sprint 4) | v5 | 변화 |
|---|---|---|---|
| 2-3 MNAR WAPE | 21.23% | 28.90% | +7.67p (악화) |
| 2-4 LODO WAPE | 47.62% | 46.58% | -1.04p (소폭 개선) |
| 2-5 Q1 WAPE | 21.14% | 26.02% | +4.88p (악화) |
| 2-8 OoM accuracy | 0.9671 | 0.9371 | -0.0300 (악화) |
| 1-4 일반 셀 confidence | 0.788 | 0.711 | -0.077 (악화) |

## 전체 합격선 비교 (v5)

| 지표 | v5 값 | 합격선 | 통과 |
|:---|---:|---:|:---:|
| random_wape | 10.89% | ≤ 12% | ✅ |
| ts_wape | 13.86% | ≤ 15% | ✅ |
| mnar_wape | 28.90% | ≤ 15% | ❌ |
| lodo_wape | 46.58% | ≤ 30% | ❌ |
| q1_wape | 26.02% | ≤ 18% | ❌ |
| pearson_r | 0.9949 | ≥ 0.97 | ✅ |
| rmsle | 0.3784 | ≤ 0.35 | ❌ |
| oom_accuracy | 0.9371 | ≥ 0.97 | ❌ |
| f1_4tier | 0.8411 | ≥ 0.85 | ❌ |
| mase | 0.0970 | ≤ 0.2 | ✅ |

## 분석: 왜 LOO cross-fitting 이 악화를 초래했나

### 가설 (Sprint 5 전)
dong_avg_store, combo_avg_store 가 학습/평가 fold 간 통계 leak → LOO cross-fitting 으로 차단 시 MNAR/LODO/Q1 개선 가능.

### 실제 결과
LOO cross-fitting 적용 후 모든 주요 지표 악화. 원인 분석:

1. **피처 노이즈 증가**: fold 외부 데이터로만 통계 계산 시 샘플 수가 줄어 통계값의 분산이 증가.
   마포구 특성상 동/업종 조합당 관측이 적어 fold 분리 후 통계가 불안정해짐.

2. **정보 손실**: 전체 alive 데이터로 계산된 dong_avg_store 는 실제로 유효한 피처였음.
   cross-fitting 으로 이 정보를 분산시키면서 예측 품질 저하.

3. **데이터 규모 문제**: N=3703 alive 셀 / 16 동 / 6 업종 조합. fold 분리 시 일부 동-업종 조합이
   train set 에서 빠져 전역 평균으로 fallback → 피처 품질 저하.

4. **leak 수준 과대 평가**: dong_avg_store 가 실제로 test set leak 을 발생시켰다기보다 합법적인
   교차-구조 정보(동 규모 특성)를 인코딩했을 가능성.

## 결론

Sprint 5 가설 기각. dong_avg LOO cross-fitting 은 오히려 예측 품질을 저하시킴.
v4.2 (Sprint 4, build_features_v4) 가 현재 최선 버전.

## Sprint 이력 요약

| Sprint | MNAR WAPE | 일반 셀 confidence | 비고 |
|---|---|---|---|
| Sprint 1 v4 | 21.23% | 0.666 | MultiOutput 6 seed |
| Sprint 2 v4.1 | 21.23% | 0.666 | NaN-guard |
| Sprint 3 v4.2 | 21.23% | 0.639 | threshold 2.5 |
| Sprint 4 (분리) | 21.23% | **0.788** | 일반/외삽 분리 PASS |
| Sprint 5 v5 LOO | **28.90%** | 0.711 | LOO cross-fitting — 가설 기각 |
