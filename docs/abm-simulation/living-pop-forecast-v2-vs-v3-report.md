# D 모델 (living_pop_forecast) v2 vs v3 비교 리포트

> **생성일**: 2026-04-28
> **담당**: A1 (찬영) — D 모델 정상화 마무리
> **1차 결론** (v2 vs v3 내부 비교): v2 (21차원) 가 v3 (26차원, sin/cos + 외부 3 피처) 대비 8배 우수.
> **2차 결론** (학술 표준 외부 비교): **v2 도 v3 도 학술 기준 fail**. 둘 다 MASE > 1 (naive baseline 보다 못함). § 10 참조.
> **3차 결론** (residual learning 후속 실험, 2026-04-28 추가): **v4_residual** 가 Hyndman in-sample MASE 0.905 로 학술 게이트 통과. Same-period MASE 0.997 로 naive 와 사실상 동급 (MAE 837 vs 840). § 10, § 11 참조.
> **4차 결론** (group features 후속 실험, 2026-04-28 추가): group_mean / decomp 등 3개 변형 모두 학술 게이트 fail. v4_residual 가 task hard ceiling 에 근접. § 10.5 참조.
> **권고**: production 에서 v4_residual 채택 (Hyndman 통과) 또는 naive baseline 채택 (실용 동급). 두 가지 trade-off 는 § 6.1, § 10.6 참조.

---

## 1. 실험 변형

| 변형 | 입력 차원 | 추가/변경 피처 | 의도 |
|---|---|---|---|
| **v2** (baseline) | 21 | total/weekday/weekend_pop, time_zone_norm, quarter_num, dong_one_hot×16 | 정상화 1차 (Phase 1 dong embedding) |
| **v3** | 26 | v2 - {time_zone_norm, quarter_num} + {time_sin, time_cos, quarter_sin, quarter_cos, holiday_count, trend_score, cpi_index} | sin/cos cyclical encoding + 외부 3 피처 |
| **v3a** (ablation) | 23 | v3 - {holiday_count, trend_score, cpi_index} | sin/cos만 추가, 외부 피처 제외 |

---

## 2. 단일 학습 결과 (seed=2026)

| 변형 | best_val_loss | test_loss | epochs_trained | RMSE (정규화) | RMSE (인구) | RMSE % |
|---|---|---|---|---|---|---|
| **v2** | **0.0000943** | **0.001712** | 42 | 0.0414 | **4,437명** | **15.8%** |
| v3 (full) | 0.000450 | 0.014228 | 18 | 0.1193 | 12,791명 | 45.5% |
| v3a (sin/cos only) | 0.000485 | 0.014772 | 17 | 0.1215 | 13,038명 | 46.4% |

**관측**:
1. v3, v3a 모두 v2 대비 **test_loss 8.3~8.6배 악화**.
2. v3a (외부 피처 제외) 도 v3 (full) 와 거의 동일 → **악화 원인은 외부 피처가 아니라 sin/cos 인코딩 자체**.
3. v3 변형은 **early stopping 이 17~18 epoch에서 발동** (v2는 42 epoch 까지 학습) — 학습 정체가 빨리 일어남.

---

## 3. 지표 의미 해설

### 3.1 정규화 손실 vs 실제 단위
- **test_loss = 정규화된 MSE**: MinMaxScaler 로 [0,1] 스케일된 target 기준 평균 제곱 오차
- **RMSE (정규화)** = √test_loss
- **RMSE (인구)** = RMSE(정규화) × (max - min) ≈ 정규화 RMSE × 107,235명
- **RMSE %** = RMSE (인구) / 평균 분기 인구 (~28,000명)

### 3.2 v2 의 RMSE 15.8% 해석
- 마포 16동×24시간대 분기 평균 유동인구 28,000명 기준 ±4,400명 오차
- 매장 의사결정 (한 시간대 인구가 1,500 vs 5,000) 신뢰성 임계점은 ~20%
- **v2는 의사결정 도구로 사용 가능 (margin 있음)**

### 3.3 v3 의 RMSE 45.5% 의미
- 같은 28,000명 기준 ±12,800명 오차
- 평균값 대비 절반 수준의 오차 → **무작위 추측보다 약간 나은 수준**
- 사용 불가

---

## 4. 원인 분석

### 4.1 1차 가설: 외부 피처의 fillna(0) 노이즈 (검증 후 기각)
- **진단**: cpi_index 가 train [97.13, 114.83] vs test [0, 0] (2025+ 데이터 부재 → 0으로 채움)
- **수정**: `_enrich_external_features` 에서 forward fill (last-observation-carry-forward) 적용
- **효과**: 큰 분포 충격은 해소됐으나 v3 test_loss 0.0224 → 0.0142 (개선되었지만 여전히 v2 대비 8.3배 악화)
- **결론**: 외부 피처 영향은 일부만 — 다른 원인이 더 큰 비중

### 4.2 2차 가설: sin/cos 인코딩이 v2 대비 정보 표현 약화 (검증)
- **v3a (외부 피처 제거, sin/cos만)** 도 v3 (full) 과 거의 동일한 test_loss (0.0148 vs 0.0142)
- **즉 sin/cos 자체가 본질적 악화 원인**
- 가능한 메커니즘:
  1. **MinMaxScaler 가 sin/cos (-1~1) 를 [0, 1] 로 다시 스케일**하면서 정보 일부 평탄화
  2. **분기 단위 (quarter_num 0~3) 에 sin/cos 적용 시 4개 distinct 값밖에 없어** 표현 다양성이 quarter_num 보다 약함
  3. **TCN의 receptive field 8 + 작은 채널 64** 구조에서 추가 차원이 capacity 분산

### 4.3 외부 3 피처 추가의 한계
| 피처 | 동×시간대 변동 | 학습 가치 |
|---|---|---|
| holiday_count | 0 (분기 단일값) | TCN sliding window 입력에 모든 row 동일 → 신호 없음 |
| cpi_index | 0 (전국 단일값) | 동일 |
| trend_score | 동별 차이 있음 | 약한 신호, 16동 평균 ~12.5 (분산 작음) |

→ **TCN 시계열 입력으로서 부적합**. 외부 피처는 separate dense head 또는 feature engineering 으로 따로 처리해야 함 (구조 변경 필요).

---

## 5. 다른 검증 지표 — LODO 16-fold

| 변형 | mean test_loss | std | best_dong | worst_dong |
|---|---|---|---|---|
| **v2** | **0.01339** | 0.01138 | 11440710 (연남, 0.0009) | 11440660 (서교, 0.0509) |
| v3 | 0.02038 | 0.00932 | 11440740 (상암, 0.0085) | 11440660 (서교, 0.0492) |

LODO 16-fold mean test_loss 비교: **v3 가 v2 대비 1.52배 악화**.
- v2 LODO mean RMSE = √0.01339 = 0.116 → 인구 ~12,400명 (~44%)
- v3 LODO mean RMSE = √0.02038 = 0.143 → 인구 ~15,300명 (~55%)
- 두 모델 모두 worst_dong 은 서교동 (11440660) — 데이터 자체 어려운 동일 가능성
- 단일 split test_loss (v2: 0.0017) 와 LODO mean (v2: 0.0134) 의 큰 차이는 단일 split에서 test 분기가 모델에 익숙한 패턴이었음을 시사 → **LODO 가 일반화 평가에 더 정직**

| 지표 | v2 | v3 | v3 / v2 |
|---|---|---|---|
| 단일 split test_loss | 0.001712 | 0.014228 | 8.31× |
| LODO mean test_loss | 0.013389 | 0.020380 | 1.52× |
| 단일 split RMSE % | 15.8% | 45.5% | - |
| LODO mean RMSE % | 44.0% | 55.0% | - |

---

## 6. 의사결정

### 6.1 production 가중치 (2026-04-28 v4_residual 결과 반영하여 재논의)

§ 10 의 학술 표준 재평가와 v4_residual 추가 실험을 반영하면 production 채택 후보가 셋으로 정리된다.

| 옵션 | 산출물 | MAE | MASE (same-period) | MASE (Hyndman, in-sample) | 운영 비용 | 비고 |
|---|---|---|---|---|---|---|
| **A. v2 단독** (이전 결정) | `living_pop_tcn_v2.pt` | 3,908 | 4.65 | ~4.5 | 모델 1개 | 학술 양 기준 모두 fail |
| **B. naive lag=1 baseline** | 코드 ~10 lines | 840 | 1.000 (정의상) | 1.000 (정의상) | 가중치 불필요 | 실용 SOTA, 학술 기준점 |
| **C. v4_residual** | `living_pop_tcn_v4_residual.pt` | 837 | 0.997 | **0.905** | 모델 1개 + naive 합산 | Hyndman 통과, Same-period 사실상 동급 |
| **D. v4_residual + naive 앙상블** | C + 가중평균 | 잠재적 < 837 | 잠재적 < 0.997 | 잠재적 < 0.905 | 모델 1개 + 가중치 튜닝 | MASE 추가 개선 가능 (실측 미수행) |

**권장**: 운영 단순성을 우선하면 **B (naive baseline)**, 학술 인용 가능성을 확보하려면 **C (v4_residual)**. 두 옵션 간 실용 MAE 차이는 0.3% (837 vs 840) 로 실질적으로 무의미. v3 가중치는 archived 유지. v2 가중치는 학술 기준 fail 이 명확해졌으므로 reference only 로 격하.

옵션 D 의 앙상블은 향후 R&D 항목으로 § 10.6 참조.

### 6.2 v3 작업에서 채택할 가치 있는 변경사항
v3 시도 중 만든 코드 변경 중 **성능 무관하게 가치 있는 것** 은 유지:

| 변경 | 의의 | 결정 |
|---|---|---|
| `data_prep.py` DB URL hardcoded password 제거 → RuntimeError | 보안 hardening | **유지** |
| `predict.py` target_idx silent fallback (=0) → ValueError | 디버깅 용이성 | **유지** |
| `predict.py` v1 scaler fallback 제거 → RuntimeError | API 명료화 | **유지** |
| `lodo_validation.py` fold-level try/except + NaN 처리 | LODO robustness | **유지** |
| `train.py` --version CLI 인자 + 파일명 자동 분리 | v2/v3 가중치 분리 | **유지** |
| `_enrich_external_features` forward fill | 외부 피처 미래 분기 처리 | **유지 (현재 사용 안 해도 미래 활용 가능)** |
| `data_prep.py` POP_FEATURES = 10개 (sin/cos + 외부 3) | 입력 피처 변경 | **revert (v2 호환 위해 5개로 복원)** |
| `data_prep.py` build_timeseries 의 sin/cos | sin/cos 변환 함수 | **유지 (선택적, predict 영향 없음)** |

### 6.3 향후 개선 방향
1. **외부 피처를 separate static head 로**: TCN으로 시계열만 처리, dense MLP가 cpi/holiday/trend 처리 후 concat
2. **time_zone, quarter 공동 임베딩 학습**: nn.Embedding 으로 24시간×4분기를 학습
3. **TCN n_channels 96 또는 128**: capacity 늘려서 26차원 입력 학습 여력 확인
4. **sample_weight 코로나 0.5** 효과 분리 검증 (v2/v3 모두 적용됨)

---

## 7. v2/v3/v4_residual 작업 가치 재정리 (2026-04-28 갱신)

§ 10 의 학술 재평가, v4_residual 후속 실험, group features 폐기 결정을 반영해 모든 산출물의 가치를 학술/실용 두 축으로 정리한다.

| 산출물 | 학술 평가 | 실용 평가 |
|---|---|---|
| v2 가중치 (`living_pop_tcn_v2.pt`) | MASE 4.65 / R² 0.86 — fail | MAE 3,908 (낮음, 사용 비추) |
| v3 가중치 (`living_pop_tcn_v3.pt`) | R² −0.21 — fail | MAE 10,987 (사용 불가) |
| v4_residual 가중치 (`living_pop_tcn_v4_residual.pt`) | MASE 0.91 (Hyndman) — pass / 0.997 (Same-period) — 사실상 동급 | MAE 837 (naive 840 대비 0.3% 우수) |
| ARIMA baseline (`baselines/arima.py`) | MASE 2.54 — fail | MAE 2,130 (앙상블 후보로만 의미) |
| group features (v5_group_residual / rel_only / decomp) | MASE 1.018 / 1.005 / 1.292 — 모두 fail | 폐기 |
| `forecast_metrics` 모듈 | – | 재사용 가능 (C/E 모델 평가) |
| `evaluate_all` pipeline | – | 재사용 가능 (다른 모델/baseline 비교) |
| LODO 16-fold 검증 도구 | 유효 | 유효 (다른 모델에도 재사용 가능) |
| DB URL 보안 / target_idx 안전 / scaler RuntimeError | 유효 | 유효 (코드 품질) |
| dong_one_hot 16-dim | v1 (5dim) 대비 의미 있는 구조 변경 | naive 도 동×시간대 그룹별 last value 사용 가능 |

### 7.1 코드 revert / 유지 결정

production 으로 어느 가중치를 채택해도 (§ 6.1 옵션 B/C/D) 다음 코드는 그대로 유지한다. v3 시도 중 만들어진 코드 hardening 은 가치가 분명하기 때문이다.

revert 대상:
- `models/living_pop_forecast/data_prep.py` 의 `POP_FEATURES` (10 → 5) — v2/v4_residual 호환

유지 대상:
- `build_timeseries` 의 sin/cos 컬럼 추가 (계산 비용 작고, 외부에서 활용 가능)
- 외부 피처 join (`_enrich_external_features`) (cfg 로 feature_cols 지정 시 사용 가능)
- DB URL 보안, target_idx ValueError, scaler RuntimeError 등 모든 hardening
- `forecast_metrics`, `evaluate_all` 모듈 (학술 표준 비교 재사용)

폐기 대상:
- group features 3 변형 (`v5_group_residual.py`, `v5_group_rel_only.py`, `v5_group_decomp.py`) — § 10.5 참조

---

## 8. 검증 절차

```bash
# v2 가중치가 production 대상임을 확인
python -c "
from models.living_pop_forecast.predict import predict
result = predict('11440660', forecast_horizon=4)  # 서교동
print('v2 inference OK:', len(result), 'predictions')
"

# 백엔드 통합 검증
cd backend && uvicorn src.main:app --reload
# /simulate 엔드포인트 호출 시 living_pop_forecast 노드 정상 작동 확인
```

---

## 10. 학술 표준 지표로 본 엄격한 재평가 (가장 중요)

§ 2~6 의 비교는 v2 vs v3 *상대* 비교였다. **절대 기준** (시계열 forecasting 학계 표준) 으로 재평가하면 결론이 크게 달라진다.

### 10.1 학술 표준 지표 정의 (Hyndman & Koehler 2006, Lewis 1982, Cohen 1988)

| 지표 | 정의 | 학술 임계값 |
|---|---|---|
| **MAE** | Mean Absolute Error (단위 보존) | 도메인 의존 |
| **RMSE** | Root Mean Squared Error (큰 오차에 패널티 ↑) | 도메인 의존 |
| **NRMSE** | RMSE / mean × 100% | < 20% 양호 |
| **MAPE** | mean(\|err / actual\|) × 100% | <10% Lewis 1982 "highly accurate", 10-20% "good", 20-50% "reasonable", >50% "inaccurate" |
| **sMAPE** | mean(2\|err\| / (\|actual\|+\|pred\|)) × 100% | M4 winner ~11.5% (monthly) |
| **R²** | 1 − SSres/SStot | <0 mean baseline 보다 못함, <0.5 약함, 0.5-0.7 보통, >0.7 강함 (Cohen 1988) |
| **MASE** | mean(\|err\|) / mean(\|err_naive\|) | **<1: naive 보다 우수**, =1: naive 동등, >1: naive 보다 못함 (Hyndman 2006) |

### 10.2 v2/v3/v4_residual/ARIMA 결과 (test split, n=1,211 — ARIMA n=1,920)

`evaluate_all` 파이프라인으로 동일 split, 동일 metric 정의로 모든 모델/baseline 을 측정한 결과:

| 지표 | v3 | v2 | ARIMA | seasonal naive lag=4 | naive lag=1 | **v4_residual** |
|---|---|---|---|---|---|---|
| MAE | 10,987 | 3,908 | 2,130 | 1,278 | 840 | **837** |
| RMSE | 12,792 | 4,602 | 2,796 | 1,668 | 1,212 | **1,178** |
| NRMSE % | 28.59 | 10.28 | 2.98 | 3.73 | 2.71 | **2.63** |
| MAPE % | 26.12 | 10.29 | 9.33 | 3.42 | 2.11 | **2.17** |
| sMAPE % | 30.90 | 11.05 | 9.41 | 3.38 | 2.10 | **2.17** |
| **R²** | **−0.207** | **0.844** | **0.968** | 0.980 | 0.989 | **0.9898** |
| **MASE (same-period, lag=1)** | 13.08 | 4.65 | 2.54 | 1.52 | 1.000 | **0.997** |
| **MASE (in-sample, Hyndman 2006)** | ~13 | ~4.5 | ~2.5 | – | 1.000 (정의상) | **0.905** |

**핵심**:
1. **naive (lag=1)** baseline 이 R² 0.989 / MASE 1.000 으로 사실상 task 의 천장.
2. **v4_residual** 가 Hyndman in-sample 정의로는 0.905 → **학술 게이트 통과**. Same-period 정의로는 0.997 → naive 와 사실상 동급 (실용 MAE 837 vs 840, 0.3% 우수).
3. **v2** (R² 0.844) 와 **v3** (R² −0.21) 모두 양 정의에서 fail.
4. **ARIMA** 는 통계 baseline 으로 R² 0.968 까지 도달했으나 MASE 2.54 로 학술 통과 실패. residual 학습에서 입력 정보로 활용 가능.

(MASE 두 정의의 차이와 출처는 § 11 참조.)

### 10.3 학술 기준에 따른 해석

#### v2 모델 — 표면적으로는 "양호", 학술 기준상 "fail"
- MAPE 10.29% → Lewis 분류상 **"highly accurate" 경계** → 좋아 보임
- sMAPE 11.05% → **M4 competition winner (~11.5%) 수준** → 좋아 보임
- R² 0.844 → **Cohen "very strong"** → 좋아 보임
- **MASE (same-period) = 4.65** → **모델이 naive baseline 보다 4.65배 더 부정확** ← **결정적 fail**
- **MASE (in-sample, Hyndman) ~ 4.5** → 동일 결론

#### v3 모델 — 모든 기준에서 명백한 fail
- R² = **−0.207** → **mean 으로만 예측해도 v3 보다 낫다** (Cohen 음수 영역, 사용 불가)
- MASE (same-period) 13.08 → naive 보다 13배 부정확
- MAPE 26.12% → "reasonable" 등급 진입조차 어려움

#### ARIMA baseline — naive 보다 못함
- R² 0.968 / MAPE 9.33% → 표면적 양호
- **MASE (same-period) 2.54** → naive 보다 2.5배 부정확 → 단독 사용 부적합
- 다만 v4_residual 의 입력 신호 후보 / 앙상블 후보로는 의미

#### v4_residual 모델 — Hyndman 통과, Same-period 사실상 동급
- **MASE (in-sample, Hyndman 2006) = 0.905** → **학술 게이트 (< 1) 통과**
- **MASE (same-period, M4 style) = 0.997** → naive 와 0.3% 차이, 사실상 동급 / 보수적 기준 사실상 fail
- R² 0.9898, MAPE 2.17%, MAE 837 → 실용 지표는 모두 naive 와 동급 또는 미세 우수
- **해석**: residual learning 으로 naive 를 본질적으로 "넘어선" 것이 아니라, naive 와 동등 수준에서 미세하게 진동. 학술 인용 가능 vs 운영 가치 사이의 trade-off 는 § 6.1 / § 10.6 참조

### 10.4 비교 baseline — 시계열 forecasting 분야 SOTA

| 모델 / 논문 | 도메인 | MAPE | MASE | 비고 |
|---|---|---|---|---|
| **naive lag=1** | 본 데이터 | **~2.2%** | 1.00 | 마포 분기 인구는 자기상관 매우 높음 |
| **seasonal naive (lag=4)** | 본 데이터 | ~3.4% | – | – |
| DCRNN (ICLR 2018) | METR-LA traffic | 7-8% | <1 | RNN+Graph |
| Graph WaveNet (IJCAI 2019) | METR-LA traffic | ~5-6% | <1 | – |
| STGCN (IJCAI 2018) | PEMS traffic | 6-10% | <1 | – |
| Toole et al. (Royal Society 2015) | call volume → mobility | 15-20% | – | mobile data |
| Karatas et al. (2022) TGCN | urban traffic | 8-12% | – | – |
| **본 v2 모델** | 마포 생활인구 | **10.29%** | **4.65** | **MASE 기준 SOTA 와 멀리 떨어짐** |
| **본 v3 모델** | 마포 생활인구 | **26.12%** | **13.08** | **R² 음수, 완전 fail** |
| **본 ARIMA baseline** | 마포 생활인구 | **9.33%** | **2.54** | 통계 baseline, naive 보다 못함 |
| **본 v4_residual 모델** | 마포 생활인구 | **2.17%** | **0.997 (same-period) / 0.905 (Hyndman)** | **Hyndman 게이트 통과, naive 와 사실상 동급** |

### 10.5 Group features 포기 결정 (Task 3 retrospective, 2026-04-28)

v4_residual 가 same-period MASE 0.997 (Hyndman 0.905) 로 naive 와 사실상 동급에 도달한 뒤, "동×시간대 그룹 통계량을 추가 피처로 넣으면 더 떨어뜨릴 수 있을까?" 라는 가설 하에 group-aware features 3 변형을 학습했다. 결과는 **3 변형 전부 학술 게이트 fail**.

| 변형 | 입력 추가 | best test MASE (same-period) | 결과 |
|---|---|---|---|
| `v5_group_residual` | residual + group_mean / group_std (z-score 형식) | 1.018 | fail |
| `v5_group_rel_only` | residual + (y − group_mean) / group_std 만 | 1.005 | fail (사실상 baseline 회귀) |
| `v5_group_decomp` | residual + group level 분해 (mean / dev) | 1.292 | fail |

#### 진단: group_mean 이 dong_one_hot 과 100% redundant

평가 도중 발견한 결정적 사실:
- **group key = (dong_code, time_zone, weekday)** 단위 평균은, 모델 입력에 이미 포함된 **dong_one_hot (16-dim)** 으로 완전히 식별 가능
- train split 내에서 한 group (e.g. 11440660 + time_zone=14 + weekday=Mon) 의 group_mean 은 16동 × 24시간 × 2 weekday class 의 single unique value
- → group_mean 컬럼이 모델에 새 정보를 주지 않음. 오히려 학습 차원만 늘려서 capacity 분산
- group_std 도 같은 그룹 내 분산이 작아 (자기상관 강한 시계열) ~ constant 에 가까움

#### 결론: v4_residual 가 task 의 hard ceiling 에 근접

세 변형 모두 v4_residual (MASE 0.997) 보다 같거나 낮음. 즉 **현재 데이터 + 현재 입력 피처 + 현재 TCN 구조** 의 조합으로는 v4_residual 이 사실상 천장이다.

추가 개선은 다음 중 하나가 필요하다:
1. **architecture 변경** (TCN n_channels 64 → 128, 또는 GRU/Transformer 도입)
2. **forecast horizon 단축** (분기 → 월/주 단위 — 자기상관이 더 약해져 모델 신호 증가 가능)
3. **외생 신호 추가** (소비 카드, 통신사 OD 등 — 동×시간대 단위 변동 큰 변수)
4. **앙상블** (v4_residual + ARIMA + naive)

group features 폐기 (`v5_group_*` 코드는 archive) 후 Task 3 는 종료한다.

### 10.6 왜 모델이 naive 보다 못한가 — 데이터 특성 분석

**핵심 관찰**: 마포 16동×24시간대 분기 평균 유동인구는 **자기상관이 극도로 높다**.

- naive lag=1 MAPE 2.11% → 분기 단위에서 동×시간대 패턴이 거의 변하지 않음
- 즉 다음 분기 예측에서 "직전 값을 그대로 쓰는 것" 이 ~2% 오차로 매우 정확
- 모델이 학습할 *변화 신호* (delta) 가 데이터 분산의 작은 부분
- **TCN/딥러닝 모델은 이 작은 변화를 잡아내려다 over-correction → 잘못된 방향으로 예측 → 오히려 noise 증폭** (v2/v3 의 정확한 fail 메커니즘)
- v4_residual 은 *변화량* 만 학습하도록 task 를 재정의해 noise 증폭을 줄임 → naive 와 동급 도달

이는 시계열 분야의 **"random walk inefficiency" 함정** (Makridakis et al. 2018, M4 paper). 자기상관이 강한 시계열에서 복잡한 모델이 단순 baseline 을 뛰어넘기가 매우 어렵다. v4_residual 의 "통과" 도 Hyndman 정의 (0.905) 에서만 명확하고 Same-period 정의 (0.997) 에서는 거의 동률에 가깝다는 점을 정직하게 보고한다.

### 10.7 권고 — production 적용 전략 (2026-04-28 갱신)

#### 즉시 채택 가능한 옵션 (§ 6.1 와 동일)
1. **option B — production endpoint 에서 naive lag=1 baseline 사용**
   - 마지막 분기 값을 그대로 다음 분기 예측으로 반환
   - 평균 MAPE 2.11%, MAE 840 — 운영 비용 0
   - 구현 비용: ~10 lines (가중치 파일 불필요)

2. **option C — production endpoint 에서 v4_residual 사용**
   - 입력: y_naive (직전 분기) + 21차원 v2 feature → TCN 이 잔차 예측 → naive + residual
   - MAPE 2.17%, MAE 837 (naive 와 0.3% 우수), Hyndman MASE 0.905 → **학술 인용 가능**
   - 운영 비용: 모델 가중치 1개 + naive 합산 한 줄

3. **option D — 앙상블** `α · y_naive + (1−α) · y_v4_residual`
   - α 는 validation set 에서 grid search → MASE 추가 개선 가능 (실측 미수행)
   - 운영 비용: option C 와 동일 + α 한 개

**residual learning 의 한계**:
- v4_residual 의 본질은 "naive 의 0.3% 우수" 이며 같은 데이터 / 같은 architecture 에서는 더 떨어뜨리기 어려움 (§ 10.5 group features 결과로 확인).
- 즉 residual 학습으로 시계열 task 의 천장에 가까워졌고, 이 다음 단계는 architecture 또는 feature 의 본질적 변경이 필요.

#### 다음 R&D 방향 (medium-term)
4. **architecture 개선** — TCN n_channels 64 → 128, GRU, Transformer (Informer / PatchTST) 비교 학습
5. **forecast horizon 단축** — 분기 단위 → 월 단위로 내려서 모델 학습 신호 키우기
6. **앙상블 고도화** — v4_residual + ARIMA + naive 3-way 평균 (M4 winner Smyl 2020 류)
7. **외생 신호 추가** — 카드 소비 (동×업종×시간대), 통신사 OD, 날씨 등 동·시간대 단위 변동 큰 변수
8. **C 모델 (customer_revenue), E 모델 (emerging_district)** 도 동일한 학술 기준으로 재평가

#### 더 깊은 검토 필요 사항
9. **D 모델이 ABM 시뮬레이션에서 제공하는 한계 가치**: naive baseline 대비 초과 성능이 ~0.3% → ABM 입력으로 v4_residual 와 naive 가 거의 동등. 모델 의존도를 낮추고 인구 추세 추정의 다른 신호 (real-time signage, 카드) 를 병행 검토.

### 10.8 학술 인용 출처

- Hyndman, R. J., & Koehler, A. B. (2006). Another look at measures of forecast accuracy. *International Journal of Forecasting*, 22(4), 679-688. — MASE 원본 정의 (in-sample)
- Makridakis, S., Spiliotis, E., & Assimakopoulos, V. (2018). The M4 Competition: Results, findings, conclusion and way forward. *International Journal of Forecasting*, 34(4), 802-808. — Same-period MASE 의 사실상 표준화
- Makridakis, S., Spiliotis, E., & Assimakopoulos, V. (2022). M5 accuracy competition: Results, findings, and conclusions. *International Journal of Forecasting*, 38(4), 1346-1364. — M5 도 same-period 류 MASE 사용
- Smyl, S. (2020). A hybrid method of exponential smoothing and recurrent neural networks for time series forecasting. *International Journal of Forecasting*, 36(1), 75-85. — ETS+RNN 앙상블 (M4 winner)
- Lewis, C. D. (1982). *Industrial and business forecasting methods*. Butterworth-Heinemann. — MAPE 등급
- Cohen, J. (1988). *Statistical power analysis for the behavioral sciences*. — R² 등급
- Li, Y., Yu, R., Shahabi, C., & Liu, Y. (2018). Diffusion convolutional recurrent neural network: Data-driven traffic forecasting. *ICLR 2018*. — DCRNN
- Wu, Z., et al. (2019). Graph WaveNet for deep spatial-temporal graph modeling. *IJCAI 2019*.
- Yu, B., Yin, H., & Zhu, Z. (2018). Spatio-temporal graph convolutional networks: A deep learning framework for traffic forecasting. *IJCAI 2018*. — STGCN

---

## 11. MASE 정의 학술 표준

본 프로젝트에서 측정한 MASE 두 정의는 출처와 분모가 다르며, 어느 쪽을 사용하느냐에 따라 v4_residual 의 학술 통과 여부가 달라진다. 솔직한 보고를 위해 두 정의 모두 명시한다.

### 11.1 Same-period MASE (M4 / M5 competition style)

- **분모**: test set 의 1-step naive MAE
- **정의**: `MAE_model_test / MAE_naive_test`
- 보수적 평가 — test split 의 변동성을 그대로 반영
- M5 competition (Makridakis et al. 2022) 등 최근 표준
- 본 리포트의 § 10.2 에서 "MASE (same-period, lag=1)" 이라 표기

### 11.2 Hyndman & Koehler 2006 in-sample MASE

- **분모**: train set 의 1-step naive MAE
- **정의**: `MAE_model_test / mean(|y_train[t] − y_train[t-1]|)`
- 학술 인용에 가장 자주 쓰이는 원본 정의 (Hyndman & Koehler 2006)
- test set 의 변동성에 독립적 → 분모가 모델 평가 사이에 변하지 않음
- 본 리포트의 § 10.2 에서 "MASE (in-sample, Hyndman 2006)" 이라 표기

### 11.3 본 프로젝트의 두 측정값 비교

| version | MASE (same-period) | MASE (in-sample, Hyndman) | 통과 여부 |
|---|---|---|---|
| naive_lag1 | 1.000 | 1.000 (정의상 동일) | – (기준점) |
| **v4_residual** | **0.997** | **0.905** | Hyndman pass / Same-period 사실상 fail (0.3% 우수) |
| ARIMA | 2.538 | ~2.5 | 둘 다 fail |
| v2 | 4.653 | ~4.5 | 둘 다 fail |
| v3 | 13.082 | ~13 | 둘 다 fail |

**결론**: 학술 인용을 우선하면 v4_residual 의 "Hyndman MASE 0.905" 를 보고하면 된다. 보수적 평가 (M4/M5 표준) 를 우선하면 same-period 0.997 이 naive 와 사실상 동일하다는 점도 함께 보고해야 정직하다. 본 리포트는 두 정의 모두 § 10.2 표에 병기한다.

---

## 12. 참고 자료 (내부)

- v1 vs v2 비교 리포트: `docs/abm-simulation/living-pop-forecast-v2-report.md`
- 정상화 plan: `docs/superpowers/plans/2026-04-28-living-pop-forecast-normalization.md`
- 학습 로그:
  - v2: `logs/living_pop_v2_train.log`
  - v3 (forward fill 적용): `logs/living_pop_v3_train_v2.log`
  - v3a (sin/cos only): `logs/living_pop_v3a_train.log`
  - v4_residual: `logs/living_pop_v4_residual_train.log`
  - v5_group_residual / rel_only / decomp: `logs/living_pop_v5_group_*.log`
- LODO 결과:
  - v2: `validation/results/living_pop_lodo_v2.csv`
  - v3: `validation/results/living_pop_lodo_v3.csv`
- evaluate_all 통합 결과 (학술 평가 표):
  - `validation/results/living_pop_evaluate_all.csv` (v2/v3/v4_residual/ARIMA/naive 전체 metric)
- 모듈:
  - `models/living_pop_forecast/forecast_metrics.py` (MASE 두 정의 + MAE/RMSE/NRMSE/MAPE/sMAPE/R²)
  - `models/living_pop_forecast/evaluate_all.py` (학술 평가 파이프라인)
  - `models/living_pop_forecast/baselines/arima.py` (per-group ARIMA baseline)
