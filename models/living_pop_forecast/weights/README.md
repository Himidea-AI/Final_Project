# D 모델 가중치 README

## Production 결정

**production = naive baseline** (학습 모델 미사용).

이유: 6 라운드 작업으로 7개 모델 변형 모두 naive baseline 을 능가 못함.
자세한 내용: `docs/abm-simulation/living-pop-forecast-v2-vs-v3-report.md`

## 가중치 파일 분류 (모두 학술 reference)

### 분기 평균 task (현재 sim 입력)
- `living_pop_tcn_v2.pt` — Round 1, MASE_lag1 = 2.54 (fail)
- `living_pop_tcn_v3.pt` — Round 2, MASE_lag1 = 13.08 (완전 fail)
- `living_pop_tcn_v4_residual.pt` — Round 3, MASE_lag1 = 1.042 (naive 동급)
- `living_pop_tcn_v5_group_*.pt` — Round 4, 3 변형 모두 fail
- `arima_baseline_v4.pkl` — Round 5, MASE = 2.54 (fail)

### Day-of-week × Hour task (실험)
- `living_pop_tcn_v6_dow_hour_residual.pt` — Round 6, MASE = 0.999 (naive 동급)

### 일별 task (실험)
- `living_pop_tcn_v7_daily_residual.pt` — Round 7, MASE_lag7 = 1.0004 (naive 동급), Hyndman MASE 0.804 (통과)

### LODO 검증 (v2)
- `living_pop_tcn_v2_lodo_*.pt` (16 fold) — LODO mean test_loss 0.01339

## 사용 권장 사항

1. **production endpoint**: `models/living_pop_forecast/predict_naive.py` 의 naive baseline 사용
2. **학술 인용용**: v4_residual (Hyndman MASE 0.69 통과) 또는 v7_daily_residual (Hyndman MASE 0.80 통과)
3. **재학습 / 비교 실험**: 동일 시드 (2026) + 동일 split 으로 재현 가능
4. **삭제 금지**: 학술 negative result 의 reference 가치 있음

## 학술 결론

마포 생활인구 시계열은 자기상관 0.86 + 분산 98% 그룹간 → 어떤 architecture / task / grain 으로도
naive baseline 능가 못함. 이건 모델 한계가 아닌 data stationarity 의 본질.

자세한 내용: `docs/abm-simulation/living-pop-forecast-v2-vs-v3-report.md` § 12.
