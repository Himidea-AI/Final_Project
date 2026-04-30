# 폐업 위험도 모델 C layer (label) fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 폐업 위험도 모델 label 을 단일 quantile 기반 (`next_closure_rate > industry_p75_train`) 으로 단순화 + train-only fit 으로 leakage 차단.

**Architecture:** label 생성을 `build_closure_risk_dataset` 안에서 빼서 split 후 별도 호출 단계로 이동. `_compute_industry_p75_train` helper 신규 + `_make_labels` 시그니처 변경. `predict.py` 영향 없음 (`_engineer_lag_features` 만 사용).

**Tech Stack:** Python, pandas (groupby quantile), pytest, LightGBM, PyTorch (TCN, 기존).

**선행 spec:** `docs/superpowers/specs/2026-05-01-closure-risk-c-layer-label-fix-design.md`

---

## File Structure

| 파일 | 변경 유형 |
|---|---|
| `models/closure_risk/data_prep.py` | Modify (`_compute_industry_p75_train` 신규, `_make_labels` 재작성, `build_closure_risk_dataset` 시그니처 변경) |
| `models/closure_risk/train.py` | Modify (pipeline 순서 재구성: load → split → label → train) |
| `models/closure_risk/predict.py` | Verify only — 변경 없어야 함 |
| `tests/test_closure_risk_label.py` | Create (4 신규 unit test) |
| `tests/test_closure_risk_regression.py` | Modify (회귀 보강 — predict schema 변화 X 검증) |
| `models/closure_risk/weights/metrics.json` | Update (production retrain) |
| `models/closure_risk/weights/calibration_curve.png` | Update (production retrain) |
| `models/closure_risk/weights/closure_risk_lgbm.pkl` | Update (production retrain) |
| `models/closure_risk/weights/closure_risk_tcn.pt` | Update (gitignored) |
| `models/closure_risk/weights/closure_risk_tcn_scaler.pkl` | Update (production retrain) |
| `models/closure_risk/weights/ensemble_weights.pkl` | Update (production retrain) |
| `docs/retrospective/2026-05-01.md` | Create |

---

## Task 1: `_compute_industry_p75_train` helper + 단위 test

**Files:**
- Modify: `models/closure_risk/data_prep.py` (top of file, 다른 helper 들과 함께)
- Test: `tests/test_closure_risk_label.py` (신규)

- [ ] **Step 1: 신규 test 파일 생성 + p75 helper test 2종**

Create `tests/test_closure_risk_label.py`:

```python
"""C layer (label) fix 단위 test.

`_compute_industry_p75_train` 의 train-only fit + min_samples fallback 검증.
`_make_labels` 의 quantile 기반 label 정의 + unseen industry drop 검증.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from models.closure_risk.data_prep import (
    _compute_industry_p75_train,
    _make_labels,
)


def _make_synthetic_df(quarters_per_industry: dict[str, list[int]], closure_rates_seed: int = 0) -> pd.DataFrame:
    """(industry, quarter) 별 closure_rate 분포 합성."""
    rng = np.random.default_rng(closure_rates_seed)
    rows = []
    for ind, qs in quarters_per_industry.items():
        for q in qs:
            # dong_code 5개 × industry × quarter
            for d in range(5):
                rows.append({
                    "dong_code": f"114403{d:02d}",
                    "industry_code": ind,
                    "quarter": q,
                    "closure_rate": float(rng.uniform(0, 0.5)),
                    "store_count": 10,
                    "monthly_sales": 1_000_000.0,
                })
    return pd.DataFrame(rows)


def test_compute_industry_p75_uses_only_train_rows():
    """val/test 분기의 closure_rate 가 p75 계산에 안 들어가야 함."""
    quarters = {
        "I001": [20191, 20192, 20193, 20194, 20201, 20202, 20203, 20204],
        "I002": [20191, 20192, 20193, 20194, 20201, 20202, 20203, 20204],
    }
    df = _make_synthetic_df(quarters, closure_rates_seed=42)

    train_quarters = {20191, 20192, 20193, 20194}
    p75_series, global_p75 = _compute_industry_p75_train(df, train_quarters, min_samples=4)

    train_only = df[df["quarter"].isin(train_quarters)]
    expected_p75_i001 = train_only[train_only["industry_code"] == "I001"]["closure_rate"].quantile(0.75)
    assert abs(p75_series["I001"] - expected_p75_i001) < 1e-9
    assert isinstance(global_p75, float)


def test_compute_industry_p75_fallback_for_thin_industry():
    """sample < min_samples 인 industry → NaN → global_p75 사용 가능."""
    quarters = {
        "I001": [20191, 20192, 20193, 20194],
        "I_thin": [20191],  # train 에 1 분기 × 5 dong = 5 rows (min_samples=8 이면 fallback)
    }
    df = _make_synthetic_df(quarters, closure_rates_seed=7)

    train_quarters = {20191, 20192, 20193, 20194}
    p75_series, global_p75 = _compute_industry_p75_train(df, train_quarters, min_samples=8)

    assert pd.isna(p75_series.get("I_thin"))
    assert not pd.isna(p75_series["I001"])
    assert global_p75 > 0
```

- [ ] **Step 2: test 실행 → fail 확인**

Run: `python -m pytest tests/test_closure_risk_label.py::test_compute_industry_p75_uses_only_train_rows tests/test_closure_risk_label.py::test_compute_industry_p75_fallback_for_thin_industry -v`
Expected: FAIL — `ImportError: cannot import name '_compute_industry_p75_train'`.

- [ ] **Step 3: helper 구현**

Edit `models/closure_risk/data_prep.py` — `_time_based_split` 바로 아래 (line 83 직후) 에 추가:

```python
def _compute_industry_p75_train(
    df: pd.DataFrame,
    train_quarters: set[int],
    min_samples: int = 4,
) -> tuple[pd.Series, float]:
    """Train rows 의 industry 별 closure_rate 75 percentile 계산.

    Args:
        df: 전체 dataset (lag feature 까지 적용된 상태).
        train_quarters: train split 분기 set (e.g. {20191, ...}).
        min_samples: industry 별 최소 sample 수. 미만 시 NaN (fallback 대상).

    Returns:
        (industry_p75 Series indexed by industry_code, global_p75 float).

    Raises:
        ValueError: train_quarters 에 해당 row 0건.
    """
    train_df = df[df["quarter"].isin(train_quarters)]
    if len(train_df) == 0:
        raise ValueError(f"train_quarters={train_quarters} 에 해당 row 0건")

    global_p75 = float(train_df["closure_rate"].quantile(0.75))

    counts = train_df.groupby("industry_code")["closure_rate"].size()
    p75 = train_df.groupby("industry_code")["closure_rate"].quantile(0.75)
    p75 = p75.where(counts >= min_samples, np.nan)

    return p75, global_p75
```

상단 import 에 `import numpy as np` 추가 (없으면).

- [ ] **Step 4: test 통과 확인**

Run: `python -m pytest tests/test_closure_risk_label.py -v`
Expected: 2 passed.

- [ ] **Step 5: ruff + commit**

```bash
ruff check --fix models/closure_risk/data_prep.py
ruff format models/closure_risk/data_prep.py
git add models/closure_risk/data_prep.py tests/test_closure_risk_label.py
git commit -m "feat(closure_risk): _compute_industry_p75_train helper (C layer fix T1)"
```

---

## Task 2: `_make_labels` 재작성 (단일 quantile + train_quarters 인자)

**Files:**
- Modify: `models/closure_risk/data_prep.py` (`_make_labels` 함수 — line 155-198)
- Test: `tests/test_closure_risk_label.py` (보강)

- [ ] **Step 1: test 추가**

Append to `tests/test_closure_risk_label.py`:

```python
def _make_synthetic_df_with_next(quarters: list[int], rng_seed: int = 0) -> pd.DataFrame:
    """(industry, quarter) 데이터 + next_closure_rate 계산 가능한 형태."""
    rng = np.random.default_rng(rng_seed)
    rows = []
    for ind in ["I001", "I002"]:
        for d in range(5):
            for q in quarters:
                rows.append({
                    "dong_code": f"114403{d:02d}",
                    "industry_code": ind,
                    "quarter": q,
                    "closure_rate": float(rng.uniform(0, 0.5)),
                    "store_count": 10,
                    "monthly_sales": 1_000_000.0,
                })
    return pd.DataFrame(rows)


def test_make_labels_requires_train_quarters():
    """train_quarters None / 빈 set → ValueError (leakage 차단)."""
    df = _make_synthetic_df_with_next([20191, 20192, 20193, 20194])
    with pytest.raises(ValueError, match="train_quarters"):
        _make_labels(df, train_quarters=None)
    with pytest.raises(ValueError, match="train_quarters"):
        _make_labels(df, train_quarters=set())


def test_make_labels_drops_unseen_industry_by_default():
    """val/test 에만 있는 industry → drop."""
    rng = np.random.default_rng(11)
    rows = []
    # I001: train+val, I_unseen: val only
    for q in [20191, 20192, 20193, 20194, 20201, 20202]:
        for d in range(5):
            rows.append({"dong_code": f"114403{d:02d}", "industry_code": "I001", "quarter": q,
                         "closure_rate": float(rng.uniform(0, 0.5)),
                         "store_count": 10, "monthly_sales": 1_000_000.0})
    for q in [20201, 20202]:
        for d in range(5):
            rows.append({"dong_code": f"114403{d:02d}", "industry_code": "I_unseen", "quarter": q,
                         "closure_rate": float(rng.uniform(0, 0.5)),
                         "store_count": 10, "monthly_sales": 1_000_000.0})
    df = pd.DataFrame(rows)

    train_quarters = {20191, 20192, 20193, 20194}
    labeled = _make_labels(df, train_quarters=train_quarters)
    assert "I_unseen" not in labeled["industry_code"].unique()
    assert "I001" in labeled["industry_code"].unique()


def test_make_labels_label_boundary():
    """label=1 ⟺ next_closure_rate > industry_p75. boundary 정확성."""
    quarters = [20191, 20192, 20193, 20194, 20201]
    rng = np.random.default_rng(99)
    rows = []
    for d in range(5):
        for q in quarters:
            rows.append({"dong_code": f"114403{d:02d}", "industry_code": "I001", "quarter": q,
                         "closure_rate": float(rng.uniform(0, 0.5)),
                         "store_count": 10, "monthly_sales": 1_000_000.0})
    df = pd.DataFrame(rows)

    train_quarters = {20191, 20192, 20193, 20194}
    labeled = _make_labels(df, train_quarters=train_quarters)
    # 모든 row 의 label 이 (next_closure_rate > industry_p75) 와 일치
    p75_series, _ = _compute_industry_p75_train(df, train_quarters)
    expected_p75 = p75_series["I001"]
    # next_closure_rate 재계산 후 비교
    df_sorted = df.sort_values(["dong_code", "industry_code", "quarter"]).copy()
    df_sorted["next_cr"] = df_sorted.groupby(["dong_code", "industry_code"])["closure_rate"].shift(-1)
    df_sorted = df_sorted[df_sorted["next_cr"].notna()].copy()
    df_sorted["expected_label"] = (df_sorted["next_cr"] > expected_p75).astype(int)
    merged = labeled.merge(
        df_sorted[["dong_code", "industry_code", "quarter", "expected_label"]],
        on=["dong_code", "industry_code", "quarter"],
    )
    assert (merged["label"] == merged["expected_label"]).all()
```

- [ ] **Step 2: test fail 확인**

Run: `python -m pytest tests/test_closure_risk_label.py -v`
Expected: 새 3 test 가 fail (`_make_labels` 시그니처 mismatch).

- [ ] **Step 3: `_make_labels` 재작성**

Replace existing `_make_labels` in `models/closure_risk/data_prep.py` (line 155-198):

```python
def _make_labels(
    df: pd.DataFrame,
    train_quarters: set[int] | None,
    *,
    drop_unseen_industry: bool = True,
) -> pd.DataFrame:
    """단일 quantile 기반 label 생성 (C-B1).

    label = 1 ⟺ next_closure_rate > industry_p75_train.
    train_quarters 의 closure_rate 만으로 p75 fit (leakage 차단).

    Args:
        df: lag feature 까지 적용된 dataset.
        train_quarters: train split 분기 set. None / 빈 set → ValueError.
        drop_unseen_industry: True (default) train 에 없는 industry row drop.
                              False 이면 global_p75 fallback.

    Returns:
        df + ["label", "industry_p75"] 컬럼. 마지막 분기 (next 없음) row drop.

    Raises:
        ValueError: train_quarters 가 None 또는 빈 set.
    """
    if not train_quarters:
        raise ValueError("train_quarters 필수 — leakage 차단 위해 None / 빈 set 금지")

    df = df.copy().sort_values(["dong_code", "industry_code", "quarter"])
    gk = ["dong_code", "industry_code"]

    df["next_closure_rate"] = df.groupby(gk)["closure_rate"].shift(-1)

    p75_series, global_p75 = _compute_industry_p75_train(df, train_quarters)
    df["industry_p75"] = df["industry_code"].map(p75_series)

    if drop_unseen_industry:
        unseen_count = int(df["industry_p75"].isna().sum())
        if unseen_count > 0:
            logger.warning("train 에 없거나 sample 부족 industry → %d row drop", unseen_count)
        df = df[df["industry_p75"].notna()].copy()
    else:
        df["industry_p75"] = df["industry_p75"].fillna(global_p75)

    df["label"] = (df["next_closure_rate"] > df["industry_p75"]).astype(int)
    df = df[df["next_closure_rate"].notna()].copy()
    df = df.drop(columns=["next_closure_rate"])

    return df
```

- [ ] **Step 4: test 통과 확인**

Run: `python -m pytest tests/test_closure_risk_label.py -v`
Expected: 5 passed.

- [ ] **Step 5: ruff + commit**

```bash
ruff check --fix models/closure_risk/data_prep.py tests/test_closure_risk_label.py
ruff format models/closure_risk/data_prep.py tests/test_closure_risk_label.py
git add models/closure_risk/data_prep.py tests/test_closure_risk_label.py
git commit -m "feat(closure_risk): _make_labels quantile + train-only fit (C layer fix T2)"
```

---

## Task 3: `build_closure_risk_dataset` 시그니처 변경 + train.py 재구성

**Files:**
- Modify: `models/closure_risk/data_prep.py` (`build_closure_risk_dataset` — line 245-286)
- Modify: `models/closure_risk/train.py` (`train()` — line 303~)

- [ ] **Step 1: regression test 추가 (`build_closure_risk_dataset` 새 시그니처 검증)**

Append to `tests/test_closure_risk_label.py`:

```python
def test_build_closure_risk_dataset_returns_df_only(monkeypatch):
    """build_closure_risk_dataset 가 단일 df (lag feature 까지) 반환 — label 미포함."""
    from models.closure_risk import data_prep as dp

    rng = np.random.default_rng(3)
    rows = []
    for ind in ["I001", "I002"]:
        for d in range(5):
            for q in [20191, 20192, 20193, 20194, 20201, 20202, 20203, 20204]:
                rows.append({
                    "dong_code": f"114403{d:02d}",
                    "industry_code": ind,
                    "quarter": q,
                    "closure_rate": float(rng.uniform(0, 0.5)),
                    "store_count": 10,
                    "monthly_sales": 1_000_000.0,
                    "franchise_count": 2,
                })
    fake_ts = pd.DataFrame(rows)
    monkeypatch.setattr(dp, "load_base_data", lambda **kwargs: fake_ts.copy())

    df = dp.build_closure_risk_dataset()
    assert "label" not in df.columns
    assert "closure_rate_lag1" in df.columns
    assert "industry_code" in df.columns
```

- [ ] **Step 2: test fail 확인**

Run: `python -m pytest tests/test_closure_risk_label.py::test_build_closure_risk_dataset_returns_df_only -v`
Expected: FAIL (현재 3-tuple 반환).

- [ ] **Step 3: `build_closure_risk_dataset` 재작성**

Edit `models/closure_risk/data_prep.py` — `build_closure_risk_dataset` 전체 교체 (line 245-286):

```python
def build_closure_risk_dataset(
    db_url: str = DB_URL,
    dong_prefix: str = "11440",
) -> pd.DataFrame:
    """폐업위험도 학습용 데이터셋 빌드 — load + lag feature 까지만.

    label 은 split 이후 별도로 `_make_labels(train_quarters=...)` 호출.

    Returns
    -------
    df : pd.DataFrame
        lag feature 적용 + LGBM_FEATURES 누락 컬럼 0 채움. label/industry_p75 미포함.
    """
    logger.info("폐업위험도 데이터셋 빌드 중 (label 미생성, split 이후 별도)...")
    df = load_base_data(db_url=db_url, dong_prefix=dong_prefix)
    df = _engineer_lag_features(df)

    missing = [f for f in LGBM_FEATURES if f not in df.columns]
    if missing:
        logger.warning("누락 피처 (0으로 채움): %s", missing)
        for f in missing:
            df[f] = 0.0

    return df
```

- [ ] **Step 4: `train.py` pipeline 재구성**

Edit `models/closure_risk/train.py` — `train()` 함수 line 303~ 의 1~5 단계 교체:

```python
def train(config: dict | None = None) -> None:

    cfg = {**DEFAULT_CONFIG, **(config or {})}
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 데이터 준비 (label 미생성)
    from models.closure_risk.data_prep import LGBM_FEATURES, _make_labels

    df_unlabeled = build_closure_risk_dataset(db_url=cfg["db_url"], dong_prefix=cfg["dong_prefix"])
    logger.info("데이터셋 (unlabeled): %d 샘플", len(df_unlabeled))

    # 2. split (label 없이) — quarter 기준
    if cfg["split_strategy"] == "time":
        train_df_raw, val_df_raw, test_df_raw = _time_based_split(
            df_unlabeled, cfg["train_ratio"], cfg["val_ratio"]
        )
    elif cfg["split_strategy"] == "random":
        logger.warning("random split — temporal leakage 위험 (deprecated). split_strategy='time' 권장")
        from sklearn.model_selection import train_test_split

        test_ratio = 1 - cfg["train_ratio"] - cfg["val_ratio"]
        train_df_raw, temp_df = train_test_split(
            df_unlabeled,
            test_size=(cfg["val_ratio"] + test_ratio),
            random_state=cfg["random_state"],
        )
        val_df_raw, test_df_raw = train_test_split(
            temp_df,
            test_size=test_ratio / (cfg["val_ratio"] + test_ratio),
            random_state=cfg["random_state"] + 1,
        )
    else:
        raise ValueError(f"unknown split_strategy: {cfg['split_strategy']}")

    train_quarters = set(train_df_raw["quarter"].unique())
    val_quarters = set(val_df_raw["quarter"].unique())
    test_quarters = set(test_df_raw["quarter"].unique())

    # 3. label 생성 (train_quarters 만으로 industry_p75 fit)
    df_labeled = _make_labels(df_unlabeled, train_quarters=train_quarters)
    logger.info("레이블 분포 — 고위험(1): %d / 저위험(0): %d (총 %d)",
                int(df_labeled["label"].sum()),
                int((df_labeled["label"] == 0).sum()),
                len(df_labeled))

    # 4. label 적용된 df 에서 split 별 row 재추출
    train_df = df_labeled[df_labeled["quarter"].isin(train_quarters)].copy()
    val_df = df_labeled[df_labeled["quarter"].isin(val_quarters)].copy()
    test_df = df_labeled[df_labeled["quarter"].isin(test_quarters)].copy()

    if len(train_df) == 0 or len(val_df) == 0 or len(test_df) == 0:
        raise ValueError(
            f"split 결과 비어있는 set 존재 — "
            f"train={len(train_df)}, val={len(val_df)}, test={len(test_df)}"
        )

    logger.info(
        "time-based split: train=%d (<=%s), val=%d (<=%s), test=%d (>%s)",
        len(train_df), train_df["quarter"].max(),
        len(val_df), val_df["quarter"].max(),
        len(test_df), val_df["quarter"].max(),
    )

    # 5. X_lgbm / y 추출 (label 컬럼 = 'label')
    X_lgbm_tr = train_df[LGBM_FEATURES].fillna(0).values
    X_lgbm_val = val_df[LGBM_FEATURES].fillna(0).values
    X_lgbm_test = test_df[LGBM_FEATURES].fillna(0).values
    y_tr_arr = train_df["label"].values
    y_val_arr = val_df["label"].values
    y_test_arr = test_df["label"].values

    # ↓ 이후 LightGBM 학습 / TCN 학습 / evaluate / save 는 기존 logic 그대로 유지.
    #   단, _build_tcn_sequences 호출 시 df_full=df_labeled, y=df_labeled["label"] 로 변경.

    # 6. LightGBM 학습 (기존)
    lgbm_model = train_lgbm(X_lgbm_tr, y_tr_arr, cfg)
    # ... (line 367 이후 기존 logic — 단 train_tcn(df_full=df_labeled, y=df_labeled["label"]) 로 변경)
```

핵심 변경 포인트:
- 기존 `df_full, X_lgbm, y = build_closure_risk_dataset(...)` (3-tuple) → 단일 df 반환
- 기존 `df_full_aligned["__y__"] = y.loc[...]` index align 로직 (line 313-317) **제거** — label 이 이미 df_labeled 컬럼에 있음
- `train_tcn(df_full, y, ...)` 호출에서 `df_full=df_labeled`, `y=df_labeled["label"]` 로 변경

전체 train() 코드는 길어 단계별로 implementer subagent 가 적용. 본 task 의 핵심은:
1. `build_closure_risk_dataset` 1-tuple 반환
2. split → `_make_labels` 호출 → split 별 재추출 순서
3. `train_tcn` 호출 시 label 컬럼 사용

- [ ] **Step 5: 회귀 test 통과 확인**

Run: `python -m pytest tests/test_closure_risk_label.py tests/test_closure_risk_split.py tests/test_closure_risk_metrics.py tests/test_closure_risk_regression.py -v`
Expected: 모든 test passed (label 6 + split 6 + metrics 8 + regression 3 = 23 test).

- [ ] **Step 6: ruff + commit**

```bash
ruff check --fix models/closure_risk/data_prep.py models/closure_risk/train.py tests/test_closure_risk_label.py
ruff format models/closure_risk/data_prep.py models/closure_risk/train.py tests/test_closure_risk_label.py
git add models/closure_risk/data_prep.py models/closure_risk/train.py tests/test_closure_risk_label.py
git commit -m "refactor(closure_risk): split → label pipeline 재구성 (C layer fix T3)"
```

---

## Task 4: `predict.py` 호환성 검증

**Files:**
- Verify only: `models/closure_risk/predict.py`
- Test: `tests/test_closure_risk_regression.py` (보강)

- [ ] **Step 1: `predict.py` 가 의존하는 컬럼 grep**

```bash
grep -nE "(_engineer_lag_features|build_closure_risk_dataset|_make_labels|LGBM_FEATURES)" models/closure_risk/predict.py
```

확인:
- `predict.py:357` `from models.closure_risk.data_prep import LGBM_FEATURES, _engineer_lag_features` — 직접 사용 OK
- `build_closure_risk_dataset` 호출 X — predict 는 학습된 model 만 load
- `_make_labels` 호출 X — label 은 학습 시에만 필요

→ predict.py 는 **변경 없음** 확인.

- [ ] **Step 2: 회귀 test 보강**

Append to `tests/test_closure_risk_regression.py`:

```python
def test_predict_does_not_use_label_pipeline():
    """predict.py 가 _make_labels / build_closure_risk_dataset 를 호출하지 않음."""
    import inspect
    from models.closure_risk import predict as predict_mod
    src = inspect.getsource(predict_mod)
    assert "_make_labels" not in src, "predict.py 가 _make_labels 호출하면 안 됨"
    assert "build_closure_risk_dataset" not in src, "predict.py 가 dataset builder 호출하면 안 됨"
```

- [ ] **Step 3: test 통과 확인**

Run: `python -m pytest tests/test_closure_risk_regression.py -v`
Expected: 모든 test passed (기존 3 + 신규 1 = 4).

- [ ] **Step 4: ruff + commit**

```bash
ruff check --fix tests/test_closure_risk_regression.py
ruff format tests/test_closure_risk_regression.py
git add tests/test_closure_risk_regression.py
git commit -m "test(closure_risk): predict.py 회귀 격리 검증 (C layer fix T4)"
```

---

## Task 5: Production retrain + metrics 비교

**Files:**
- Update (실행 산출물): `models/closure_risk/weights/*`

- [ ] **Step 1: 기존 metrics.json 백업 (commit log 만으로 비교 가능 — 별도 backup 파일 생성 X)**

`git log` 에 이전 commit (3b52b96) 의 metrics.json 보존되어 있음 — 추가 작업 불필요.

- [ ] **Step 2: production retrain**

```bash
cd "/c/Users/804/Documents/final project"
set -a && source .env && set +a
python -m models.closure_risk.train 2>&1 | tee /tmp/closure_risk_retrain_c.log
```

Expected:
- 데이터 load 후 split log 출력
- 레이블 분포 log (변경 후 pos_ratio 확인)
- LightGBM 학습 → val_AUC log
- TCN 학습 → epoch 별 val_AUC log
- evaluate 후 metrics.json + calibration_curve.png 갱신
- 최종 ensemble val_AUC / test_AUC log

소요시간: ~2분 (기존 retrain 과 유사).

- [ ] **Step 3: 새 metrics 검증**

```bash
python -c "
import json
with open('models/closure_risk/weights/metrics.json') as f:
    m = json.load(f)
print('split:', m['split_strategy'])
print('train q:', m['train_quarters'][:3], '...', m['train_quarters'][-1])
print('val q:', m['val_quarters'])
print('test q:', m['test_quarters'])
print('LGBM val AUC:', m['lgbm']['val']['auc'])
print('LGBM test AUC:', m['lgbm']['test']['auc'])
print('TCN val AUC:', m['tcn']['val']['auc'])
print('TCN test AUC:', m['tcn']['test']['auc'])
print('Ensemble val AUC:', m['ensemble']['val']['auc'])
print('Ensemble test AUC:', m['ensemble']['test']['auc'])
print('val pos_ratio:', m['ensemble']['val']['pos_ratio'])
print('test pos_ratio:', m['ensemble']['test']['pos_ratio'])
"
```

Expected:
- split_strategy = "time"
- pos_ratio 가 0.20~0.30 범위 (이전 0.27~0.32 → 단일 quantile 로 약간 줄어듦 예상)
- test AUC 는 알 수 없음 — 0.50~0.55 범위로 예상 (기존 0.5142 와 유사 또는 약간 변화)

- [ ] **Step 4: 재현 가능 확인 (optional)**

`weights/metrics.json` 의 `split_strategy="time"` + train/val/test_quarters 가 이전과 동일한지 확인 (data 변화 없으면 split 도 동일).

- [ ] **Step 5: commit (산출물)**

```bash
git add models/closure_risk/weights/metrics.json \
        models/closure_risk/weights/calibration_curve.png \
        models/closure_risk/weights/closure_risk_lgbm.pkl \
        models/closure_risk/weights/closure_risk_tcn_scaler.pkl \
        models/closure_risk/weights/ensemble_weights.pkl
# closure_risk_tcn.pt 는 gitignored (확인)
git commit -m "chore(closure_risk): retrain with C layer label fix (T5)"
```

---

## Task 6: 회고 작성

**Files:**
- Create: `docs/retrospective/2026-05-01.md`

- [ ] **Step 1: 회고 파일 작성**

내용 구조:
1. **요약** — C layer (label) fix 완료. 단일 quantile + train-only fit. AUC 변화량 명시.
2. **배경** — E layer fix 후 진단 (test AUC 0.5142). C layer 가 가장 큰 비중.
3. **작업 내역** — 5 task subagent 실행 (T1~T5) + 회고. commit SHA 기록.
4. **결과 — metric 비교** — before/after 표 (val/test AUC, PR-AUC, P@10, R@10, Brier, pos_ratio).
5. **진단** — label 단순화 후 신호 변화 해석. 모델의 진짜 한계 노출.
6. **다음 sprint 우선순위** — D (threshold) → B (feature) → A (구조). 각 별도 spec 권장.
7. **배운 점** — leakage 차단 패턴, label 단순화의 정직한 효과 등.

- [ ] **Step 2: commit**

```bash
git add docs/retrospective/2026-05-01.md
git commit -m "docs(closure_risk): 2026-05-01 회고 — C layer label fix"
```

---

## Verification — 최종 회귀 + 산출물 확인

- [ ] **Step 1: 전체 closure_risk test 통과**

```bash
python -m pytest tests/test_closure_risk_*.py -v
```

Expected: ~24 test passed (label 6 + split 6 + metrics 8 + regression 4).

- [ ] **Step 2: ruff clean**

```bash
ruff check models/closure_risk/ tests/test_closure_risk_*.py
ruff format --check models/closure_risk/ tests/test_closure_risk_*.py
```

Expected: clean.

- [ ] **Step 3: git log 확인**

```bash
git log --oneline -10
```

Expected: 6 commit (T1~T5 + 회고) 가 명확히 보임.

- [ ] **Step 4: 산출물 sanity check**

```bash
ls -la models/closure_risk/weights/
```

Expected:
- metrics.json (~6KB)
- calibration_curve.png (~60KB)
- closure_risk_lgbm.pkl, closure_risk_tcn.pt, closure_risk_tcn_scaler.pkl, ensemble_weights.pkl

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| `_make_labels` 시그니처 변경으로 다른 모듈 깨짐 | grep `_make_labels` — `train.py` 와 test 만 사용. predict.py 무관 |
| `build_closure_risk_dataset` 시그니처 변경 (3-tuple → df) | 호출자 grep — `train.py` 만. 다른 모듈 사용 X 확인 |
| pos_ratio 가 너무 변함 (0.10 또는 0.50) | log 출력으로 즉시 확인. 0.15 미만 또는 0.40 초과 시 spec 재검토 |
| AUC 더 떨어짐 | 정직한 진단이 deliverable. 회고에 명시 |
| Production retrain 실패 (DB 연결 등) | `set -a && source .env` 로 환경변수 로드. 기존 retrain 패턴 동일 |
| commit 전 사용자 확인 (memory rule) | 각 task 의 git commit 단계는 implementer subagent 가 stage 후 controller 가 사용자에게 확인 받고 진행 |

## Self-Review

1. **Spec coverage**: ✅ — `_compute_industry_p75_train` (T1), `_make_labels` 재작성 (T2), `build_closure_risk_dataset` 시그니처 + train.py 재구성 (T3), predict.py 무영향 검증 (T4), production retrain (T5), 회고 (T6).
2. **Placeholder scan**: ✅ — TBD/TODO 없음.
3. **Type consistency**: ✅ — `_make_labels(df, train_quarters: set[int] | None)`, `_compute_industry_p75_train(df, train_quarters: set[int])`, `build_closure_risk_dataset(...) -> pd.DataFrame` 일관.

승인 후 subagent-driven-development 로 실행.
