# 폐업 위험도 모델 검증 layer fix — Design Spec

> **상태**: 브레인스토밍 완료, 사용자 승인 후 spec 자체 self-review 완료, 사용자 검토 대기.
> **작업 영역**: `models/closure_risk/` (B2 — 수지니 영역, A1 찬영이 cross-team contribution).
> **Plan 단계**: 본 spec 통과 후 `writing-plans` skill 으로 implementation plan 작성.

## Goal

폐업 위험도 모델 (LightGBM + TCNClassifier 앙상블) 의 검증 layer 의 **temporal leakage 위험** 을 제거. 시계열 random split 을 time-based holdout 3분할로 교체 + validation metric 5종 추가. 학술 논문 standard (Bergmeir & Benítez 2012) 부합 + 사용자 (창업주) 의사결정에 직관적인 metric 노출.

## Background

`train.py:39` `DEFAULT_CONFIG = {"val_ratio": 0.2, "random_state": 42}` + sklearn random split → 시계열 데이터 (분기별 dong×industry) 에 부적절. 미래 분기가 train, 과거가 val 로 섞여 들어가 **temporal leakage** 발생, val_AUC 부풀림 가능.

학술적으로 ABM/시계열 모델은 time-based holdout 또는 walk-forward validation 표준 (Bergmeir & Benítez 2012, "On the use of cross-validation for time series predictor evaluation"). 본 프로젝트의 핵심 학술 자산인 Pearson r=0.95 (Brussels ABM 0.96 천장) 를 보호하려면 검증 layer 가 underlying assumption 을 만족해야 함.

추가로 현재 metric 은 `roc_auc_score` 만. 폐업률 ~20% imbalanced data 에서 AUC 만으론:
- 임계값 0.65/0.40 적정성 검증 X
- 출력 확률이 실제 빈도와 일치 (calibration) 검증 X
- 사용자 의사결정 (위험 top N 매장 추천) 에 직관적 metric 부재

## Architecture

```
data_prep.build_closure_risk_dataset()
    ↓
sort by quarter
    ↓
_time_based_split(df, train_ratio=0.70, val_ratio=0.15)
    ├── train (≤ train_end_quarter)
    ├── val (> train_end, ≤ val_end_quarter)
    └── test (> val_end_quarter)
    ↓
TCN sequence 생성 시 window_size 만큼 buffer (val 의 lookback 이 train 데이터 사용 OK,
                                                 단 label 은 val period 에서만)
    ↓
train_lgbm + train_tcn (val set 으로 hyperparam tuning, early stopping)
    ↓
ensemble weight 결정 (val_AUC 비례)
    ↓
evaluate.py — test set 1회 측정 (unbiased final 성능)
    ↓
weights/metrics.json + calibration_curve.png 저장
```

## Components

### 1. `_time_based_split()` helper (`data_prep.py`)

```python
def _time_based_split(
    df: pd.DataFrame,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """quarter 기준 시간순 train/val/test 3분할.

    - 같은 quarter 데이터는 한 split 에만 들어감 (boundary 명확)
    - train + val + test 합 = 100% (남은 부분 = test)
    - 분기 수가 적으면 (n < 7) ValueError raise

    Returns:
        train_df, val_df, test_df
    """
    quarters = sorted(df["quarter"].unique())
    n_q = len(quarters)
    if n_q < 7:
        raise ValueError(f"분기 수 부족 ({n_q}). 최소 7분기 필요 (train 5 / val 1 / test 1)")

    train_end_idx = int(n_q * train_ratio) - 1
    val_end_idx = int(n_q * (train_ratio + val_ratio)) - 1
    train_end = quarters[train_end_idx]
    val_end = quarters[val_end_idx]

    train = df[df["quarter"] <= train_end].copy()
    val = df[(df["quarter"] > train_end) & (df["quarter"] <= val_end)].copy()
    test = df[df["quarter"] > val_end].copy()

    return train, val, test
```

### 2. `train.py` 갱신

`DEFAULT_CONFIG` 변경:
```python
DEFAULT_CONFIG = {
    # ... (기존 필드 유지)
    "split_strategy": "time",       # "time" (default) | "random" (legacy)
    "train_ratio": 0.70,
    "val_ratio": 0.15,
    # test_ratio = 1 - train_ratio - val_ratio = 0.15
    # 기존 val_ratio: 0.2 는 split_strategy="random" 시에만 사용 (deprecated 경고)
}
```

`train_model()` 분기:
```python
if cfg["split_strategy"] == "time":
    train_df, val_df, test_df = _time_based_split(df, cfg["train_ratio"], cfg["val_ratio"])
    logger.info(
        "time-based split: train=%d (≤%s), val=%d (≤%s), test=%d (>%s)",
        len(train_df), train_df["quarter"].max(),
        len(val_df), val_df["quarter"].max(),
        len(test_df), val_df["quarter"].max(),
    )
elif cfg["split_strategy"] == "random":
    logger.warning("⚠️ random split — temporal leakage 위험 (deprecated). split_strategy='time' 권장")
    # 기존 random_state 분할 로직
```

### 3. TCN sequence buffer 처리

train period 의 마지막 4분기 (window_size) 가 val 의 첫 sequence lookback 으로 사용되어도 leakage X (input은 train 데이터, label 은 val 의 분기 → 미래 정보 X). 단 implementation 시 boundary 명확하게:

```python
# val set 의 첫 sequence: lookback 은 train 끝 4분기 + val 시작 분기. label 은 val 분기.
# test set 도 동일 패턴.
# (dong, industry) 그룹별로 sliding window 생성 시 quarter 정렬 보장
```

### 4. `evaluate.py` (신규)

```python
def evaluate_model(
    model_lgbm,
    model_tcn,
    X_lgbm: pd.DataFrame,
    X_tcn_seq: np.ndarray,
    y: np.ndarray,
    ensemble_w: dict,
    set_name: str = "val",
) -> dict:
    """5 metric + calibration 측정.

    Returns:
        {
            "auc": float, "pr_auc": float,
            "p@10": float, "r@10": float,
            "brier": float,
            "calibration": {"bin_centers": [...], "actual_freq": [...]},
        }
    """
    # 모델 별 + ensemble 예측
    # 5 metric 계산 (sklearn.metrics)
    # 10 bin reliability diagram 데이터
    pass


def save_metrics_and_plot(metrics: dict, output_dir: Path) -> None:
    """metrics.json + calibration_curve.png 저장."""
    # JSON dump + matplotlib reliability diagram
    pass
```

### 5. `metrics.json` schema

```json
{
  "split_strategy": "time",
  "train_quarters": ["2020Q1", "...", "2023Q3"],
  "val_quarters": ["2023Q4", "2024Q1", "2024Q2"],
  "test_quarters": ["2024Q3", "2024Q4"],
  "lgbm": {
    "val":  {"auc": 0.78, "pr_auc": 0.55, "p@10": 0.42, "r@10": 0.28, "brier": 0.13},
    "test": {"auc": 0.76, "pr_auc": 0.54, "p@10": 0.41, "r@10": 0.27, "brier": 0.13}
  },
  "tcn": {
    "val":  {"auc": 0.74, "pr_auc": 0.51, "p@10": 0.38, "r@10": 0.25, "brier": 0.15},
    "test": {"auc": 0.72, "pr_auc": 0.50, "p@10": 0.37, "r@10": 0.24, "brier": 0.15}
  },
  "ensemble": {
    "val":  {"auc": 0.81, "pr_auc": 0.60, "p@10": 0.46, "r@10": 0.32, "brier": 0.12},
    "test": {"auc": 0.79, "pr_auc": 0.58, "p@10": 0.45, "r@10": 0.31, "brier": 0.12}
  },
  "ensemble_weights": {"w_lgbm": 0.51, "w_tcn": 0.49}
}
```

### 6. `predict.py` 영향

변경 X. 기존 `_load_models()` + `RISK_LEVELS` 그대로. 단 추후 사용자에게 `metrics.json` 노출하려면 별도 endpoint (별도 spec).

## Data Flow

1. `train.py` 시작 → `build_closure_risk_dataset()` 로 df 생성 (분기 정렬)
2. `_time_based_split()` 으로 train/val/test 분할 (quarter boundary 기반)
3. **LightGBM**: train_df 로 fit → val_df 예측 → AUC 등 metric
4. **TCN**: train sequence 생성 (window_size buffer) → val 시퀀스 예측 → metric, early stopping
5. ensemble weight = lgbm_val_auc / (lgbm_val_auc + tcn_val_auc) 비례
6. `evaluate.py.evaluate_model(set_name="val")` → val metrics 5종
7. `evaluate.py.evaluate_model(set_name="test")` → **final unbiased test metrics 1회**
8. `save_metrics_and_plot()` → `weights/metrics.json` + `weights/calibration_curve.png`

## Error Handling

- **분기 수 부족** (`n_q < 7`): `_time_based_split()` 가 ValueError raise. 사용자가 CLI 옵션 `--split-strategy random` 으로 명시적 fallback 가능 (자동 fallback 아님 — 학술 정직성 위해 사용자 의식적 선택 강제).
- **train/val/test 모두 빈 set**: train.py 가 raise (분기 수 부족 + 그룹 분할로 한 split 이 비는 경우).
- **TCN sequence 생성 실패**: 기존 동작 (`raise ValueError("TCN 시퀀스 생성 실패")`) 유지. log 강화.
- **calibration plot 생성 실패** (matplotlib 미설치): warning + JSON 만 저장.

## Testing

신규 단위 테스트 (~9 test):

`tests/test_closure_risk_split.py`:
1. `test_time_based_split_correct_boundaries` — 20분기 → 14/3/3 분할 정확성
2. `test_time_based_split_no_overlap` — train/val/test quarter 교집합 0
3. `test_time_based_split_raises_on_small_data` — n_q < 7 → ValueError
4. `test_time_based_split_preserves_dong_industry_grouping` — 같은 (dong, industry) 가 여러 split 에 들어가도 OK (시계열 정상)

`tests/test_closure_risk_metrics.py`:
1. `test_evaluate_model_returns_5_metrics` — auc/pr_auc/p@10/r@10/brier 모두 [0,1] 범위
2. `test_evaluate_model_handles_imbalanced` — y 가 모두 0 또는 1 일 때 graceful 처리
3. `test_save_metrics_creates_json_and_png`
4. `test_calibration_bins_match_predicted_distribution` — 10 bin 의 실제 빈도가 monotonic
5. `test_metrics_json_schema_complete` — 필수 필드 모두 존재

회귀 테스트:
- 기존 train 호출 (`split_strategy="random"` legacy) → 회귀 X 검증
- predict.py inference 인터페이스 변경 X 확인

## Risks

| Risk | Mitigation |
|---|---|
| time-based split 후 AUC 큰 폭 하락 (0.85 → 0.70) | 학술적 정직성 ⭐. README 에 학습 metric 변화 이유 명시 |
| 분기 수 부족 시 학습 실패 | split_strategy="random" fallback CLI 옵션 + ValueError 메시지로 사용자 안내 |
| 기존 weights 재학습 시간 (1~2 시간) | mock data 로 unit test 가능, production retrain 은 별도 작업 |
| Calibration plot 의존성 (matplotlib) | warning + JSON 만 저장, plot skip |

## Out of Scope

- E2 (TimeSeriesSplit 5-fold): 본 fix 후 보강 가능, 별도 spec
- E3 (Walk-forward): 학술 논문용, 별도 spec
- C (레이블 정의 fix), D (임계값), B (피처 추가), A (모델 구조): 별도 spec, 본 fix 후 순차 진행
- 사용자 UI (metrics.json 노출 endpoint): backend 별도 작업
- 모델 retraining 자동화 (CI/CD): infra 영역

## 참고 학술 자료

- Bergmeir, C., & Benítez, J. M. (2012). "On the use of cross-validation for time series predictor evaluation." *Information Sciences*, 191, 192-213.
- Cawley, G. C., & Talbot, N. L. (2010). "On over-fitting in model selection and subsequent selection bias in performance evaluation." *Journal of Machine Learning Research*, 11, 2079-2107.
- Niculescu-Mizil, A., & Caruana, R. (2005). "Predicting good probabilities with supervised learning." *Proceedings of the 22nd International Conference on Machine Learning*. (Calibration 표준)
