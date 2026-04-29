# D 모델 일별 Task — Day-level (date × dong × time_zone) 인구 예측

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development
>
> **Goal:** 일별 단위 (date × dong × time_zone) 활동량 예측으로 task 변경. naive_lag7 대비 MASE < 0.85 달성.
>
> **분기/주별 fail 이유**: naive R² 0.99 (stationary 너무 강함). 일별은 R² 0.97 → 학습 여지 있음.

---

## 0. 진단 데이터 (이미 측정됨)

| 단위 | naive_lag1 R² | naive_lag7 R² | rows | 학습 가치 |
|---|---|---|---|---|
| 분기 평균 | 0.9917 | – | 11,136 | ❌ |
| 주별 평균 | 0.9906 | – | 139,392 | ❌ |
| **일별** | 0.9558 | **0.9716** | **968,064** | **✅** |

→ 일별 task 의 강력 baseline 은 **naive_lag7** (1주 전 같은 요일).

---

## 1. Task 정의

**입력**: 과거 N일의 (date, dong, time_zone, total_pop) 시계열
**출력**: 다음 N일의 인구 예측

### 시퀀스 단위
- 그룹: (dong_code, time_zone) — 16 × 24 = 384 그룹
- 그룹당 시계열 길이: ~2,521 일
- window_size = 14 (2주, lag=7 + lag=14 패턴 둘 다 봄)
- 그룹당 시퀀스: ~2,507개
- 총 시퀀스: ~963K (충분히 많음)

### Baseline (학술 비교 기준)
- **naive_lag7** = y[t-7] (가장 강력, primary baseline)
- naive_lag1 = y[t-1] (보조)

### MASE 게이트
- **MASE_lag7 < 0.85** (vs naive_lag7) → 학습 모델 가치 있음, production 권장
- MASE_lag7 < 1.0 → naive_lag7 보다 우수 (학술 통과)
- MASE_lag7 > 1.0 → 모델 가치 없음, naive_lag7 baseline 채택

---

## 2. Architecture

**TCN + Residual learning (vs naive_lag7)**:
- 입력 차원: total_pop + day_of_week_one_hot(7) + time_zone_norm + dong_one_hot(16) = 25
- window_size = 14
- n_channels = 64, dilations = [1, 2, 4, 8] (RF=15)
- target: y[t] − y[t−7] (잔차 vs lag=7)
- 최종 예측: y_pred = y[t-7] + model_output

이 구조는 baseline 자동 보장 (model=0 → naive_lag7 동급).

---

## 3. Tasks

### Task 1+2: 데이터 prep + baseline 측정 (병합)

**Files:**
- Create: `models/living_pop_forecast/data_prep_daily.py`
- Create: `data/processed/living_pop_daily.csv` (캐시)
- Create: `validation/experiments/living_pop/baseline_daily.py`
- Create: `tests/test_data_prep_daily.py`

**핵심**:
1. raw csv 로드 → (date, dong_code, time_zone, total_pop, day_of_week)
2. 캐시 csv 저장 (parquet 도 OK)
3. 시간순 70/15/15 split (그룹 내, 진정한 시간순)
4. naive_lag1, naive_lag7, naive_lag365 학술 metric 측정
5. 게이트: naive_lag7 R² < 0.98 (학습 여지 확인)

**검증 게이트**: naive_lag7 R² < 0.98 통과 시 Task 3 진입.

### Task 3: 모델 학습

**Files:**
- Create: `models/living_pop_forecast/data_prep_daily.py` (Task 1+2 와 합치거나 분리)
- Create: `models/living_pop_forecast/train_daily_residual.py`

**핵심**:
- TCN residual learning (target = y[t] − y[t−7])
- 가중치: `living_pop_tcn_v7_daily_residual.pt`
- 학습 시간 추정: CUDA 약 30분~1시간 (968K rows / batch=128)

### Task 4: evaluate_all 통합 + 리포트

**Files:**
- Modify: `validation/experiments/living_pop/evaluate_all.py` (`_evaluate_v7_daily_residual` 추가)

---

## 4. Risk & Mitigation

| Risk | Mitigation |
|---|---|
| 일별 raw 로드 너무 느림 (302MB) | 캐시 csv (parquet) 저장 후 재사용 |
| 968K rows 학습 시간 ↑ | batch_size 128~256, mixed precision |
| naive_lag7 도 R² 0.97 → 모델 개선 폭 작음 | 외부 신호 (공휴일, 요일 효과 강화) 추가 가능 |
| v4_residual 가중치 손상 | version 명시 + save_path 분리 |

---

## 5. 검증

```bash
# Task 1+2
python -m models.living_pop_forecast.data_prep_daily --rebuild
python -m validation.experiments.living_pop.baseline_daily

# Task 3
python -m models.living_pop_forecast.train_daily_residual --epochs 30 --patience 5 --seed 2026

# Task 4
python -m validation.experiments.living_pop.evaluate_all --filter v7_daily
```
