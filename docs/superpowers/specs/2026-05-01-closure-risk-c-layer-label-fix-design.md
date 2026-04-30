# 폐업 위험도 모델 C layer (label) fix — Design Spec

> **상태**: 브레인스토밍 완료, 사용자 승인 (2026-05-01).
> **작업 영역**: `models/closure_risk/` (B2 — 수지니 영역, A1 찬영 cross-team contribution).
> **선행 작업**: `2026-04-29-closure-risk-validation-fix-design.md` (E layer fix 완료, test AUC 0.5142 진단).
> **Plan 단계**: 본 spec 통과 후 `writing-plans` skill 으로 implementation plan 작성.

## Goal

폐업 위험도 모델의 label 정의를 **3중 OR (closure / store / sales) → 단일 quantile 조건** 으로 단순화 + leakage 차단.

`label = (next_closure_rate > industry_p75_train)` — 이때 `industry_p75_train` 은 **train split 전용** 분기들의 closure_rate 75 percentile.

## Background

E layer fix 후 정직한 metric 측정 가능해졌고, ensemble test AUC=0.5142 (사실상 random) 가 확정됐다. 진단 결과 5 layer 중 **C (label) 의 비중이 가장 큼**:

1. **Label 모호함** — `data_prep.py:189` 의 3중 OR (closure_rate spike / store_count 2분기 연속 감소 / sales YoY -25%) 가 무엇을 예측하는지 불분명. pos_ratio 0.27~0.32 의 출처가 어떤 조건인지 분해 불가.
2. **약한 leakage 가능성** — `industry_avg = df.groupby("industry_code")["closure_rate"].transform("mean")` (`data_prep.py:177`) 가 train+val+test 통합 평균. 검증 시 미래 분기의 closure_rate 가 평균에 들어가 있어 약한 leakage.
3. **Macro 신호** — row 단위가 (dong × industry × quarter) 매크로. 개별 매장 폐업이 아니라 동×업종 평균 closure_rate spike 를 예측 — 본 spec 에서는 row 단위 변경하지 않음 (별도 spec C-C 영역).

본 spec 은 row 단위는 그대로 두고 **label 의미 명확화 + leakage 차단** 만 수행. 결과로 모델의 진짜 한계가 더 깨끗하게 보이게 된다.

## Architecture

### 변경 전 pipeline

```
build_closure_risk_dataset()
    ├── load_base_data()
    ├── _engineer_lag_features()      # lag feature
    ├── _make_labels()                # 3중 OR + 전체 industry mean
    └── return df, X_lgbm, y
                ↓
        _time_based_split()           # split (label 이미 생성된 후)
                ↓
            train
```

### 변경 후 pipeline

```
build_closure_risk_dataset()
    ├── load_base_data()
    ├── _engineer_lag_features()      # lag feature only (label 무관)
    └── return df_unlabeled            # label 미생성 상태로 반환
                ↓
        _time_based_split(df_unlabeled)
                ↓
        _make_labels(df, train_quarters)   # train rows 의 industry_p75 fit + broadcast
                ↓
            train
```

핵심: **split 이 label 생성 전에** 일어나야 train-only quantile fit 가능.

## Components

### 1. `_compute_industry_p75_train()` 신규 helper

```python
def _compute_industry_p75_train(
    df: pd.DataFrame,
    train_quarters: set[int],
    min_samples: int = 4,
) -> tuple[pd.Series, float]:
    """Train rows 의 industry 별 closure_rate 75 percentile 계산.

    Args:
        df: 전체 dataset (lag feature 까지 적용된 상태).
        train_quarters: train split 분기 set (e.g. {20191, 20192, ..., 20224}).
        min_samples: industry 별 최소 sample 수. 미만 시 global p75 fallback.

    Returns:
        (industry_p75 Series indexed by industry_code, global_p75 float).
        Sample 부족한 industry 는 industry_p75 에 NaN, lookup 시 fallback 사용.

    Raises:
        ValueError: train_quarters 에 해당하는 row 가 0건.
    """
    train_df = df[df["quarter"].isin(train_quarters)]
    if len(train_df) == 0:
        raise ValueError(f"train_quarters={train_quarters} 에 해당 row 0건")

    global_p75 = float(train_df["closure_rate"].quantile(0.75))

    counts = train_df.groupby("industry_code")["closure_rate"].size()
    p75 = train_df.groupby("industry_code")["closure_rate"].quantile(0.75)
    # min_samples 미만 industry 는 NaN → fallback
    p75 = p75.where(counts >= min_samples, np.nan)

    return p75, global_p75
```

### 2. `_make_labels()` 시그니처 변경

```python
def _make_labels(
    df: pd.DataFrame,
    train_quarters: set[int],
    *,
    drop_unseen_industry: bool = True,
) -> pd.DataFrame:
    """단일 quantile 기반 label 생성 (C-B1).

    label = 1 ⟺ next_closure_rate > industry_p75_train (or global_p75 fallback).

    Args:
        df: lag feature 까지 적용된 dataset.
        train_quarters: train split 분기 set.
        drop_unseen_industry: True 이면 train 에 없는 industry row drop.
                              False 이면 global_p75 fallback 사용.

    Returns:
        df with columns: ["label", "industry_p75"] 추가, 마지막 분기 row drop.

    Raises:
        ValueError: train_quarters 가 None 또는 빈 set.
    """
    if not train_quarters:
        raise ValueError("train_quarters 필수 — leakage 차단 위해 None 호출 금지")

    df = df.copy().sort_values(["dong_code", "industry_code", "quarter"])
    gk = ["dong_code", "industry_code"]

    df["next_closure_rate"] = df.groupby(gk)["closure_rate"].shift(-1)

    p75_series, global_p75 = _compute_industry_p75_train(df, train_quarters)

    # broadcast — train 에 없는 industry 는 NaN
    df["industry_p75"] = df["industry_code"].map(p75_series)

    if drop_unseen_industry:
        unseen_count = int(df["industry_p75"].isna().sum())
        if unseen_count > 0:
            logger.warning("train 에 없는 industry %d row drop", unseen_count)
        df = df[df["industry_p75"].notna()].copy()
    else:
        df["industry_p75"] = df["industry_p75"].fillna(global_p75)

    df["label"] = (df["next_closure_rate"] > df["industry_p75"]).astype(int)

    df = df[df["next_closure_rate"].notna()].copy()
    df = df.drop(columns=["next_closure_rate"])

    return df
```

### 3. `build_closure_risk_dataset()` 시그니처 변경

```python
def build_closure_risk_dataset(
    db_url: str = DB_URL,
    dong_prefix: str = "11440",
) -> pd.DataFrame:
    """전처리 + lag feature 까지만 수행 — label 은 split 이후 별도 호출.

    Returns:
        df_unlabeled: load + lag feature 적용 데이터. label 컬럼 없음.

    Note:
        기존 `(df_full, X_lgbm, y)` 반환 → label 미포함 단일 df 반환으로 변경.
        호출자 (`train.py`) 에서 split → `_make_labels(train_quarters=...)` →
        X_lgbm/y 추출 순으로 처리.
    """
    df = load_base_data(db_url=db_url, dong_prefix=dong_prefix)
    df = _engineer_lag_features(df)
    return df
```

### 4. `train.py` pipeline 재구성

```python
def train(config: dict | None = None) -> None:
    cfg = {**DEFAULT_CONFIG, **(config or {})}

    # 1. load + feature (label 미생성)
    df_unlabeled = build_closure_risk_dataset(db_url=cfg["db_url"], dong_prefix=cfg["dong_prefix"])

    # 2. split (label 없이) — quarter 기준
    if cfg["split_strategy"] == "time":
        train_df_raw, val_df_raw, test_df_raw = _time_based_split(
            df_unlabeled, cfg["train_ratio"], cfg["val_ratio"]
        )
    else:
        # random fallback (기존 로직 유지)
        ...

    train_quarters = set(train_df_raw["quarter"].unique())
    val_quarters = set(val_df_raw["quarter"].unique())
    test_quarters = set(test_df_raw["quarter"].unique())

    # 3. label 생성 (train_quarters 만으로 industry_p75 fit)
    df_labeled = _make_labels(df_unlabeled, train_quarters=train_quarters)

    # 4. label 적용 후 split 재추출
    train_df = df_labeled[df_labeled["quarter"].isin(train_quarters)].copy()
    val_df = df_labeled[df_labeled["quarter"].isin(val_quarters)].copy()
    test_df = df_labeled[df_labeled["quarter"].isin(test_quarters)].copy()

    # 5. X_lgbm / y 추출
    X_cols = LGBM_FEATURES
    X_tr, y_tr = train_df[X_cols].fillna(0).values, train_df["label"].values
    X_val, y_val = val_df[X_cols].fillna(0).values, val_df["label"].values
    X_test, y_test = test_df[X_cols].fillna(0).values, test_df["label"].values

    # ... 나머지 LGBM/TCN 학습 + evaluate (기존 logic)
```

### 5. `predict.py` 영향

`predict.py:357` 에서 `_engineer_lag_features` 만 사용 — label 미생성. **변경 없음**.

단 `_engineer_lag_features` 의 출력 column 변화 X 확인 필요 (기존 column 유지).

## Data Flow

1. `train.py` → `build_closure_risk_dataset()` → `df_unlabeled` (lag feature 까지 적용, label 없음)
2. `_time_based_split(df_unlabeled)` → `(train_df_raw, val_df_raw, test_df_raw)`
3. `train_quarters = {q1, q2, ...}` 추출
4. `_make_labels(df_unlabeled, train_quarters)` 내부:
   - `_compute_industry_p75_train(train rows)` → `(industry_p75: Series, global_p75: float)`
   - `df["industry_p75"] = df["industry_code"].map(p75_series)`
   - 미존재 industry → drop (default) 또는 global fallback
   - `label = next_closure_rate > industry_p75`
5. label 적용된 `df_labeled` 에서 split 별 row 재추출 (label 있는 상태)
6. LGBM / TCN 학습 → evaluate → metrics.json 저장

## Error Handling

| case | 처리 | 위치 |
|---|---|---|
| `train_quarters` None / 빈 set | ValueError ("leakage 차단 위해 필수") | `_make_labels` 진입점 |
| `train_quarters` 에 해당 row 0건 | ValueError | `_compute_industry_p75_train` |
| industry train sample < 4 | NaN → drop (default) or global p75 fallback | `_make_labels` |
| `next_closure_rate` NaN (마지막 분기) | row drop (기존 동작 유지) | `_make_labels` |
| `closure_rate` 자체 NaN | 기존 `fillna(0)` 동작 유지 (data_prep load 단계에서 처리됨) | `load_base_data` |

## Testing

### 신규 단위 테스트 (4개) — `tests/test_closure_risk_label.py`

```python
def test_compute_industry_p75_uses_only_train_rows():
    """train_quarters 의 closure_rate 만으로 p75 계산. val/test 분기 미반영."""

def test_compute_industry_p75_falls_back_for_thin_industry():
    """sample < 4 인 industry → NaN → global_p75 fallback 작동."""

def test_make_labels_drops_unseen_industry_by_default():
    """val/test 에만 있는 industry → row drop, warning log."""

def test_make_labels_label_definition():
    """label=1 ⟺ next_closure_rate > industry_p75. boundary 정확."""
```

### 회귀 테스트

- 기존 17 test 모두 통과 (`test_closure_risk_split.py` 6, `test_closure_risk_metrics.py` 8, `test_closure_risk_regression.py` 3).
- `test_closure_risk_regression.py:test_predict_interface_unchanged` 가 `predict()` 출력 schema 검증 → 영향 없어야 함.

### Production retrain 1회

- `python -m models.closure_risk.train` 실행
- `weights/metrics.json` 갱신 → 변화 비교
- 산출물: `weights/calibration_curve.png`, `closure_risk_lgbm.pkl`, `closure_risk_tcn.pt`, `closure_risk_tcn_scaler.pkl`, `ensemble_weights.pkl` 갱신

## Risks

| Risk | Mitigation |
|---|---|
| label 단순화 후 AUC 더 떨어짐 | 정직한 진단이 deliverable. metrics.json 비교 + 회고에 명시. 다음 sprint (D/B/A) 우선순위 도출 자료 |
| `predict.py` 가 의존하는 column 변화 | `_engineer_lag_features` 의 out column 그대로 유지. 회귀 test 로 검증 |
| `build_closure_risk_dataset` 시그니처 변경 (3-tuple → df 단일) | 호출자 1곳 (`train.py`) 만 영향. 다른 모듈 grep 으로 confirm |
| train_quarters 부족으로 industry coverage 낮음 | `min_samples=4` fallback + drop_unseen_industry=True default. 학술 정직성 우선 |
| pos_ratio 가 너무 낮거나 높음 (0.10 / 0.50) | val pos_ratio 모니터링. 0.20~0.30 벗어나면 spec 재검토 |

## Out of Scope

- **D layer (threshold 재정의)** — 0.65 / 0.40 hard threshold 폐기 + top-K decision 검토. 별도 spec.
- **B layer (feature 추가)** — 카드매출 lag, 검색 trend granularity. 별도 spec.
- **A layer (구조 변경)** — LGBM/TCN proba inner-join, hierarchical / GNN. 별도 spec.
- **Store-level row 재정의 (C-C)** — (store_id × quarter) ground-truth label. 별도 spec.
- **C-B2 / C-B3 (sales 신호 결합)** — closure + YoY OR / composite score. 본 fix 후 ablation 으로 별도 spec.
- **Quantile 임계값 sensitivity (p70 / p75 / p80 비교)** — 학술 보강. 별도 spec.

## 참고 학술 자료

- Bergmeir & Benítez (2012) "On the use of cross-validation for time series predictor evaluation." *Information Sciences*, 191. — train-only quantile fit 의 시계열 leakage 차단 근거.
- 본 spec 은 binary classification 의 label 정의 단순화 — 해석 가능성 우선 (Doshi-Velez & Kim 2017 "Towards a Rigorous Science of Interpretable Machine Learning" 의 single-condition 권장).
