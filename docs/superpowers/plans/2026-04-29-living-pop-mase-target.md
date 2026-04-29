# D 모델 (living_pop_forecast) MASE < 1 달성 플랜

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans
>
> **Goal:** 학술 표준 (Hyndman & Koehler 2006) 기준 MASE < 1.0 달성. 즉 모델이 naive baseline (lag=1) 보다 우수한 시계열 예측을 한다.
>
> **현재 상태**: v2 MASE = 4.54 (naive 보다 4.54배 부정확), v3 MASE = 13.08 (R² 음수). 두 버전 모두 학술 기준 fail.
>
> **목표 상태**: MASE < 1.0, ideally 0.7~0.9 범위. R² ≥ 0.99 (naive 0.9892 매치/능가).

---

## 0. 근본 원인 분석 (데이터 진단 결과)

### 0.1 시계열 자기상관 (ACF, 384 그룹 평균)

| lag | ACF 평균 | ACF median | 의미 |
|---|---|---|---|
| 1 | **0.77** | **0.86** | 직전 분기와 매우 강한 상관 — naive 가 지배적 |
| 2 | 0.68 | 0.73 | 6개월 전과도 강함 |
| 4 | 0.43 | 0.49 | 1년 전, 보통 상관 (계절성 있음) |
| 8 | 0.14 | 0.18 | 2년 전, 약함 |

→ **lag=1 의존성이 압도적**. 어떤 모델이든 lag=1 baseline 을 자동으로 구현해야 함.

### 0.2 분산 분해 (variance decomposition)

| 분산 source | 값 | 비율 |
|---|---|---|
| **그룹간 분산 (between)** | 236,391,657 | **98.0%** |
| 그룹내 분산 (within) | 5,651,596 | 2.3% |
| total 분산 | 241,254,432 | 100% |

→ **분산의 98% 가 동×시간대 그룹 평균 차이에서 나옴**.
→ naive R² 0.989 의 정체: "그룹 평균을 직전 값으로 기억" 만으로 99% 설명 가능.
→ **모델이 진짜 학습할 task = 2.3% within-variance 의 미세 변동**.

### 0.3 잔차 (Δy = y[t] − y[t−1]) 분포

| 통계 | 값 | 의미 |
|---|---|---|
| 평균 Δy | −69 | 분기당 평균 69명 감소 (코로나 영향) |
| std Δy | 1,412 | 변동 폭 |
| **\|Δy\| 평균** | **852** | **이게 naive MAE 와 정확히 일치 (수학적 검증)** |
| \|Δy\|/y 비율 | 3.06% | 변동 폭이 평균 인구의 3% |
| top 5% \|Δy\| | 4,259 | 큰 변화 outlier 평균 |

→ **변동성 자체가 작음** (분기별 인구 변화가 평균 3%). 모델이 baseline 능가하려면 이 작은 변화를 정확히 예측해야 함.

### 0.4 quarter 단위 trend

| 시점 | 평균 인구 |
|---|---|
| 20191 (시작) | 28,696 |
| 20261 (끝) | 26,755 |
| 변화 | **−6.8%** (long-term decline) |

→ Long-term trend 약함, 자연 감소 코로나 영향 수준.

### 0.5 핵심 진단 결론

**"why model < baseline"** 의 진짜 이유:

1. **그룹 평균이 분산의 98% 차지**: naive 는 그룹 평균을 implicit 하게 기억 (직전 값 = 그룹 평균에 매우 가까움). 모델은 explicit 학습 부담.
2. **lag=1 자기상관 0.86 (median)**: baseline 의 implicit predictor 가 매우 강함.
3. **모델이 raw target 예측**: 모델 출력이 직접 y[t]. baseline 보장 구조 없음 → 작은 noise 학습으로 over-correction.
4. **MinMaxScaler global fit**: 작은 그룹 (새벽 시간대) 의 절대오차 underestimate. 학습 후 inverse transform 시 큰 단위 오차.

이 4가지 원인이 합쳐져서 model MAE 3,816 (naive 840 의 4.5배) 가 발생.

---

## 1. 개선 아키텍처 (Phase별)

```
                                  현재 v2:
   X ──[TCN]──> y_pred (raw)         MASE 4.54 ❌

목표 1단계 (Residual learning):
   X ──[TCN]──> Δy_pred
                  ↓
   y_naive (last) + Δy_pred ──> y_pred_final     기대 MASE 0.85~0.95

목표 2단계 (Group-aware + Residual):
   X (+ group_mean) ──[TCN]──> Δy_pred
                                  ↓
   y_naive + Δy_pred ──> y_pred                  기대 MASE 0.70~0.85

목표 3단계 (Ensemble: TCN + ARIMA per group):
   y_TCN_residual + y_ARIMA + y_naive 가중평균   기대 MASE 0.50~0.75
```

---

## 2. Tasks (subagent-driven-development 권장)

### Task 1: 평가지표 evaluator 모듈 구축

**목적**: 모든 모델/baseline 을 동일 metric pipeline 으로 평가. M4/M5 표준 지표 산출.

**Files:**
- Create: `validation/metrics/forecast_metrics.py`
- Create: `tests/test_forecast_metrics.py`

**구현**:
```python
# validation/metrics/forecast_metrics.py
"""시계열 forecasting 학술 표준 지표 (Hyndman & Koehler 2006).

함수:
- mae(y_true, y_pred)
- rmse(y_true, y_pred)
- mape(y_true, y_pred)         # Lewis 1982
- smape(y_true, y_pred)        # M4 competition
- r2(y_true, y_pred)            # Cohen 1988
- mase(y_true, y_pred, y_naive) # Hyndman & Koehler 2006
- evaluate_all(y_true, y_pred, y_naive=None) -> dict
"""
import numpy as np

def mae(y_true, y_pred):
    return float(np.mean(np.abs(y_true - y_pred)))

def rmse(y_true, y_pred):
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))

def mape(y_true, y_pred, eps=1e-9):
    return float(np.mean(np.abs((y_true - y_pred) / np.where(np.abs(y_true) < eps, eps, y_true))) * 100)

def smape(y_true, y_pred, eps=1e-9):
    denom = np.abs(y_true) + np.abs(y_pred) + eps
    return float(np.mean(2 * np.abs(y_true - y_pred) / denom) * 100)

def r2(y_true, y_pred):
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    return float(1 - ss_res / ss_tot)

def mase(y_true, y_pred, y_naive):
    """y_naive: 같은 test set 의 naive baseline 예측 (예: lag=1)."""
    mae_model = np.mean(np.abs(y_true - y_pred))
    mae_naive = np.mean(np.abs(y_true - y_naive))
    if mae_naive < 1e-9:
        return float('inf')
    return float(mae_model / mae_naive)

def evaluate_all(y_true, y_pred, y_naive=None) -> dict:
    out = {
        'MAE': mae(y_true, y_pred),
        'RMSE': rmse(y_true, y_pred),
        'NRMSE_pct': rmse(y_true, y_pred) / np.mean(y_true) * 100,
        'MAPE_pct': mape(y_true, y_pred),
        'sMAPE_pct': smape(y_true, y_pred),
        'R2': r2(y_true, y_pred),
    }
    if y_naive is not None:
        out['MASE'] = mase(y_true, y_pred, y_naive)
    return out
```

**Test (tests/test_forecast_metrics.py)**:
```python
def test_mase_naive_self():
    """모델 = naive 일 때 MASE = 1.0."""
    import numpy as np
    from validation.metrics.forecast_metrics import mase
    y_true = np.array([10.0, 20.0, 30.0])
    y_naive = np.array([9.0, 19.0, 29.0])
    assert abs(mase(y_true, y_naive, y_naive) - 1.0) < 1e-9

def test_mape_zero_division():
    """y_true=0 인 row 가 있어도 MAPE 가 inf 안 됨."""
    import numpy as np
    from validation.metrics.forecast_metrics import mape
    result = mape(np.array([0.0, 100.0]), np.array([0.5, 95.0]))
    assert np.isfinite(result)
```

**검증**:
```bash
python -m pytest tests/test_forecast_metrics.py -v
```

---

### Task 2: Residual Learning 모델 구조 (가장 중요)

**목적**: 모델 출력 = y[t] − y[t−1] (잔차). 최종 예측 = y_naive + model(x).
**기대 효과**: MASE 4.54 → 0.85~0.95 (가장 큰 단일 개선)

**Files:**
- Create: `models/living_pop_forecast/residual_train.py`
- Create: `models/living_pop_forecast/residual_predict.py`
- Modify: `models/living_pop_forecast/data_prep.py:362-380` (prepare_sequences 에 `mode="residual"` 옵션)

**핵심 코드 (data_prep.py 수정)**:
```python
def prepare_sequences(
    data, window_size=8, target_col="total_avg_pop",
    feature_cols=None, mode: str = "absolute",  # "absolute" | "residual"
):
    """
    mode="absolute": 기존 동작. y[t] 정규화값 직접 예측.
    mode="residual": y[t] - y[t-1] (잔차) 예측. inverse 시 last_value + delta.
    """
    # ... 기존 코드 ...
    if mode == "residual":
        # y_seq[i] = y[i] - X_seq[i, -1, target_idx_in_X]
        # 새 target = delta. baseline 보장 구조.
        y_residual = y_seq - X_seq[:, -1, target_idx_in_X:target_idx_in_X+1]
        # target_scaler 도 잔차 분포로 fit (range ~ ±5,000)
        target_scaler.fit(y_residual)
        y_norm = target_scaler.transform(y_residual)
        return X_norm, y_norm, feature_scaler, target_scaler, weights
    # else: 기존 absolute 동작
```

**residual_train.py**:
```python
"""Residual learning train: 모델 출력 = Δy 정규화값.

학습:
- target = y[t] - y[t-1] (잔차)
- model 이 잔차 분포에 맞춰 학습 (통상 ±5,000 명)
- baseline 은 자동 보장 (model output = 0 이면 = naive)

저장: living_pop_tcn_v4_residual.pt + scalers + metadata.json
"""

def train_residual(config: dict | None = None) -> dict:
    cfg = {**DEFAULT_TRAIN_CONFIG, "version": "v4_residual"}
    if config:
        cfg.update(config)
    cfg["mode"] = "residual"  # data_prep 에 전달

    # 기존 _build_v2_loaders 가 mode 받아서 prepare_sequences 호출
    bundle = _build_loaders(cfg)
    # 학습 루프 동일 (MSE on residual)
    # ...
    # metadata 에 mode="residual" 기록 → predict 시 분기
    metadata["mode"] = "residual"
    return result
```

**residual_predict.py**:
```python
"""Residual model 추론: y_pred = last_value + denormalize(model(x))."""

def predict_residual(dong_name, time_zone, n_quarters=4):
    # 1. 입력 시퀀스 X (window=8) 빌드
    # 2. model(X) → Δy_normalized
    # 3. inverse transform → Δy (실제 단위)
    # 4. last_value = X[-1, target_idx] inverse → y[t-1]
    # 5. y_pred = last_value + Δy
    # 6. autoregressive: 다음 step 의 last_value = y_pred
    # ...
```

**검증 — Step 1 (단위 테스트)**:
```python
def test_residual_zero_delta_equals_naive():
    """Δy_pred = 0 이면 y_pred = y[t-1] = naive."""
    # mock model 이 0 출력 → 최종 예측이 last_value 와 일치
```

**검증 — Step 2 (학습 + 평가)**:
```bash
python -m models.living_pop_forecast.residual_train --epochs 100 --patience 15 --seed 2026
python -m validation.experiments.living_pop.evaluate_all --version v4_residual
# 기대: MASE < 1.0, R² ≥ 0.985
```

---

### Task 3: Group-aware feature 추가

**목적**: 동×시간대 그룹 평균 (분산의 98%) 을 explicit feature 로 제공.
**기대 효과**: MASE 0.85 → 0.75 (추가 10~15% 개선)

**Files:**
- Modify: `models/living_pop_forecast/data_prep.py` (build_timeseries 에 group_mean 컬럼 추가)

**구현**:
```python
def build_timeseries(df: pd.DataFrame, *, add_group_features: bool = False) -> pd.DataFrame:
    # ... 기존 ...
    if add_group_features:
        # train split 의 그룹별 평균을 future row 에 broadcast
        # ⚠️ data leakage 방지 — quarter ≤ train_max_quarter 까지만 사용해서 mean 계산
        train_mask = df["quarter"] <= TRAIN_END_QUARTER  # cfg 로 받음
        group_mean = (
            df[train_mask]
            .groupby(["dong_code", "time_zone"])["total_avg_pop"]
            .mean()
            .rename("group_mean")
        )
        df = df.merge(group_mean, on=["dong_code", "time_zone"], how="left")
        df["group_mean"] = df["group_mean"].fillna(df["total_avg_pop"].mean())

        # group_relative = (y[t] - group_mean) / group_mean
        df["group_relative"] = (df["total_avg_pop"] - df["group_mean"]) / df["group_mean"]
    return df
```

**POP_FEATURES_V4** (Task 2 와 합쳐서):
```python
POP_FEATURES_V4_RESIDUAL = [
    "total_avg_pop", "weekday_avg_pop", "weekend_avg_pop",
    "time_zone_norm", "quarter_num",
    "group_mean",         # ← 추가
    "group_relative",     # ← 추가
]
```

**검증**:
```python
def test_group_mean_no_leakage():
    """group_mean 계산이 train 분기까지만 사용하는지."""
    # test 분기의 group_mean 이 train 분기 평균과 일치
```

---

### Task 4: ARIMA per-group baseline + 앙상블

**목적**: M4 winner 패턴 (statistical + ML 앙상블). 384 그룹별 auto_arima.
**기대 효과**: 앙상블 후 MASE 0.75 → 0.55~0.70

**Files:**
- Create: `models/living_pop_forecast/arima_baseline.py`
- Create: `models/living_pop_forecast/ensemble.py`

**의존성**: pmdarima (auto_arima), 설치 확인 필요
```bash
pip install pmdarima  # 또는 statsforecast (Nixtla, 더 빠름)
```

**arima_baseline.py 핵심**:
```python
"""384 그룹별 ARIMA(p,d,q) auto-fit + 4분기 forecast."""
from pmdarima import auto_arima

def fit_arima_per_group(df, train_quarters):
    models = {}
    for (dong, tz), g in df.groupby(["dong_code", "time_zone"]):
        g_train = g[g["quarter"].isin(train_quarters)].sort_values("quarter")
        ts = g_train["total_avg_pop"].values
        if len(ts) < 8:
            continue
        try:
            m = auto_arima(ts, seasonal=True, m=4, suppress_warnings=True, max_p=3, max_q=3)
            models[(dong, tz)] = m
        except Exception:
            pass
    return models

def forecast_arima(models, dong, tz, n_steps=4):
    if (dong, tz) not in models:
        return None
    return models[(dong, tz)].predict(n_periods=n_steps)
```

**ensemble.py**:
```python
"""앙상블: w_naive · y_naive + w_arima · y_arima + w_tcn · y_tcn_residual.

가중치는 validation set 에서 grid search 또는 sklearn.linear_model.LinearRegression
(stacking) 로 학습.
"""
def ensemble_predict(y_naive, y_arima, y_tcn_residual, weights):
    return weights[0] * y_naive + weights[1] * y_arima + weights[2] * y_tcn_residual
```

**검증**:
```bash
python -m models.living_pop_forecast.arima_baseline --train --save weights/arima_v4.pkl
python -m models.living_pop_forecast.ensemble --eval
```

---

### Task 5: 통합 evaluation pipeline + LODO 16-fold

**목적**: 모든 변형 (v2, v3, v4_residual, v4_residual_group, ensemble) 을 동일 LODO + 학술 metric 으로 비교.

**Files:**
- Create: `validation/experiments/living_pop/evaluate_all.py`

**구현**:
```python
"""모든 모델 변형 + naive baseline 을 동일 test split 에서 평가.

산출:
- per-model: {MAE, RMSE, NRMSE, MAPE, sMAPE, R², MASE}
- table CSV: validation/results/living_pop_metrics_all.csv
- LODO 16-fold mean ± std
"""
def evaluate_all_models():
    versions = ["v2", "v3", "v4_residual", "v4_residual_group", "ensemble"]
    rows = []
    for v in versions:
        for fold in range(16):  # LODO
            # 1. test split inference
            y_true, y_pred, y_naive = inference(v, fold)
            # 2. metrics 계산
            m = evaluate_all(y_true, y_pred, y_naive)
            m["version"] = v
            m["fold"] = fold
            rows.append(m)
    df = pd.DataFrame(rows)
    df.to_csv("validation/results/living_pop_metrics_all.csv", index=False)
    return df
```

**검증**:
```bash
python -m validation.experiments.living_pop.evaluate_all
# 기대 결과:
# v2:                MASE ~4.5
# v4_residual:       MASE ~0.9     ← Task 2 성공 시
# v4_residual_group: MASE ~0.75    ← Task 3 성공 시
# ensemble:          MASE ~0.55    ← Task 4 성공 시
```

---

### Task 6: Stretch goal — Group-wise normalization

**목적**: MinMaxScaler global fit → group (dong×time_zone) 별 fit. 작은 시간대 underweight 해소.
**기대 효과**: MASE 0.55 → 0.45 (조건부)

**Files:**
- Create: `models/living_pop_forecast/group_scaler.py`

**구현**:
```python
"""GroupMinMaxScaler: (dong, time_zone) 별로 fit/transform.

inverse_transform 도 같은 group key 로 복원.
모델은 group-relative 정규화 [-1, 1] 입력 받음.
"""
from sklearn.preprocessing import MinMaxScaler

class GroupMinMaxScaler:
    def __init__(self):
        self.scalers = {}  # (dong, tz) -> MinMaxScaler

    def fit(self, df, target_col, group_keys=("dong_code", "time_zone")):
        for keys, g in df.groupby(list(group_keys)):
            s = MinMaxScaler()
            s.fit(g[[target_col]].values)
            self.scalers[keys] = s

    def transform(self, df, target_col, group_keys=("dong_code", "time_zone")):
        out = np.zeros((len(df), 1))
        for keys, g in df.groupby(list(group_keys)):
            if keys in self.scalers:
                out[g.index] = self.scalers[keys].transform(g[[target_col]].values)
        return out

    def inverse_transform(self, normalized, group_keys_arr):
        # ...
```

---

## 3. 검증 절차 (각 Task 후)

```bash
# 1) 단위 테스트
python -m pytest tests/test_forecast_metrics.py tests/test_living_pop_forecast_v2.py -v

# 2) 학습 + 평가 sanity
python -m models.living_pop_forecast.residual_train --epochs 50 --seed 2026
python -m validation.experiments.living_pop.evaluate_all --filter v4_residual

# 3) 학술 기준 게이트 (각 Task 후 필수)
# - MASE < 5.0   (Task 2 후)  → v2 4.54 보다 개선
# - MASE < 2.0   (Task 3 후)
# - MASE < 1.0   (Task 4 후)  ← 학술 표준 통과 ✅
# - MASE < 0.85  (Task 5 후)  → 의미있는 모델
# - MASE < 0.70  (Task 6 후, stretch) → SOTA 근접

# 4) Production 통합 테스트
cd backend && uvicorn src.main:app --reload
# /simulate 호출 시 v4 가중치 사용 → response 정상
```

---

## 4. Risk & Mitigation

| Risk | 가능성 | 영향 | Mitigation |
|---|---|---|---|
| Residual learning 으로도 MASE > 1 | 중간 | 큼 | naive baseline 직접 production 적용 (10 lines, MAPE 2.11%) |
| ARIMA 384 그룹 fit 시간 폭발 | 중간 | 보통 | statsforecast (Nixtla) 사용 — pmdarima 보다 10배 빠름 |
| Group-aware feature data leakage | 높음 | 큼 | TRAIN_END_QUARTER cutoff 명시 + leakage test |
| TCN architecture 자체 한계 | 낮음 | 큼 | N-BEATS, NHITS 같은 SOTA forecasting 모델 시도 |
| 작은 표본 (~7,684 시퀀스) | 높음 | 보통 | M4 winner 처럼 통계 모델 비중 ↑ |

---

## 5. 예상 일정

| Phase | Task | 예상 소요 | 담당 |
|---|---|---|---|
| Phase 1 | Task 1 (metrics) | 0.5일 | A1 |
| Phase 1 | Task 2 (residual learning) | 1.5일 | A1 |
| Phase 2 | Task 3 (group features) | 1일 | A1 |
| Phase 2 | Task 4 (ARIMA + ensemble) | 2일 | A1 |
| Phase 3 | Task 5 (eval pipeline) | 1일 | A1 |
| Phase 3 | Task 6 (group scaler, optional) | 1일 | A1 |
| 합계 | – | **6~7일** | – |

---

## 6. 의사결정 기준

각 Task 종료 시 **MASE 게이트 통과** 여부로 다음 단계 진입 결정:

```
Task 2 종료 → MASE < 5.0 ?  YES → Task 3 진입
                            NO → naive baseline production 적용 (모델 폐기)

Task 3 종료 → MASE < 2.0 ?  YES → Task 4 진입
                            NO → Task 2+3 결과로 production 결정

Task 4 종료 → MASE < 1.0 ?  YES → 학술 기준 통과, production 가능
                            NO → naive baseline + ARIMA 앙상블만 적용

Task 5 종료 → 학술 리포트 갱신 + 최종 결정
```

---

## 7. Out-of-Scope (별도 ticket)

- **N-BEATS / NHITS / TFT** 같은 SOTA 시계열 모델 도입 → 별도 R&D 프로젝트
- **C 모델 (customer_revenue) MASE 평가** → 별도 plan (D 완료 후 동일 패턴 적용)
- **E 모델 (emerging_district)** → 별도 plan
- **외부 데이터 (서울 25개구 pretrain)** → 데이터 수집 작업 별도

---

## 8. 참고 자료

- 학술 인용:
  - Hyndman & Koehler (2006) — MASE
  - Lewis (1982) — MAPE 등급
  - Cohen (1988) — R² 등급
  - Makridakis et al. (2018) — M4 winner
  - Smyl (2020) — M4 winner architecture (ETS+ARIMA+RNN)
- 본 프로젝트 문서:
  - 진단 결과: `docs/abm-simulation/living-pop-forecast-v2-vs-v3-report.md` § 10
  - 현재 v2 가중치: `models/living_pop_forecast/weights/living_pop_tcn_v2.pt` (MASE 4.54)
- 외부 라이브러리:
  - `pmdarima` (auto_arima): https://alkaline-ml.com/pmdarima/
  - `statsforecast` (Nixtla, faster): https://nixtla.github.io/statsforecast/
