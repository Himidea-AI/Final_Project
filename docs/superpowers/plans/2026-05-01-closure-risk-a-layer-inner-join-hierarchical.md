# 폐업 위험도 모델 A layer (inner-join + hierarchical) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A-1 (LGBM/TCN proba alignment 정확성) + A-2 (industry-level prior model 의 stage 1 LGBM, stage 2 dong-level 의 feature 로 활용) 동시 도입.

**Architecture:** A-1 은 `_build_tcn_sequences` / `train_tcn` 가 (dong, industry, quarter) keys 반환 + `_align_predictions` helper 로 inner-join. A-2 는 `models/closure_risk/stage1_industry_prior.py` 신규 모듈에 industry-level LGBM 정의 + `train()` 통합. predict.py 도 stage1 lookup.

**Tech Stack:** Python, pandas/numpy, LightGBM (LGBMRegressor stage 1), pytest, PyTorch (TCN 기존).

**선행 spec:** `docs/superpowers/specs/2026-05-01-closure-risk-a-layer-inner-join-hierarchical-design.md`

---

## File Structure

| 파일 | 변경 유형 |
|---|---|
| `models/closure_risk/stage1_industry_prior.py` | Create (Stage 1 모듈) |
| `models/closure_risk/train.py` | Modify (`_align_predictions` helper, `_build_tcn_sequences` 키 반환, `train_tcn` 시그니처 확장, `train()` Stage 1 통합 + ensemble inner-join) |
| `models/closure_risk/data_prep.py` | Modify (`LGBM_FEATURES` 에 `industry_prior_pred` 추가) |
| `models/closure_risk/predict.py` | Modify (`_load_models` Stage 1 추가, `predict()` industry_prior_pred lookup) |
| `tests/test_closure_risk_align.py` | Create (~5 test) |
| `tests/test_closure_risk_stage1.py` | Create (~4 test) |
| `models/closure_risk/weights/stage1_industry_prior.pkl` | Create (production retrain) |
| `models/closure_risk/weights/*` | Update (production retrain) |
| `docs/retrospective/2026-05-01-a-layer.md` | Create |

---

## Task 1: A-1 Inner-join alignment

**Files:**
- Modify: `models/closure_risk/train.py`
- Test: `tests/test_closure_risk_align.py` (신규)

- [ ] **Step 1: 신규 test 파일 생성 (5 test)**

```python
"""A-1 inner-join alignment 단위 test."""

from __future__ import annotations

import numpy as np
import pandas as pd  # noqa: F401
import pytest

from models.closure_risk.train import _align_predictions, _build_tcn_sequences, train_tcn  # noqa: F401


def test_align_predictions_inner_join():
    """같은 (dong, industry, quarter) key 만 ensemble."""
    lgbm_proba = np.array([0.1, 0.2, 0.3, 0.4])
    lgbm_keys = [("d1", "i1", 20211), ("d2", "i1", 20211), ("d3", "i1", 20211), ("d4", "i1", 20211)]
    tcn_proba = np.array([0.5, 0.6, 0.7])
    tcn_keys = [("d1", "i1", 20211), ("d2", "i1", 20211), ("d4", "i1", 20211)]
    label_dict = {k: 0 for k in lgbm_keys}

    aligned_lgbm, aligned_tcn, aligned_y, common = _align_predictions(
        lgbm_proba, lgbm_keys, tcn_proba, tcn_keys, label_dict
    )
    assert len(aligned_lgbm) == 3
    assert len(aligned_tcn) == 3
    assert len(common) == 3
    assert ("d3", "i1", 20211) not in common  # TCN 에 없음 → 제외


def test_align_predictions_handles_no_overlap():
    """common keys 0건 → 빈 array."""
    lgbm_proba = np.array([0.1])
    lgbm_keys = [("d1", "i1", 20211)]
    tcn_proba = np.array([0.5])
    tcn_keys = [("d2", "i2", 20212)]
    label_dict = {("d1", "i1", 20211): 0, ("d2", "i2", 20212): 1}

    aligned_lgbm, aligned_tcn, aligned_y, common = _align_predictions(
        lgbm_proba, lgbm_keys, tcn_proba, tcn_keys, label_dict
    )
    assert len(aligned_lgbm) == 0
    assert len(common) == 0


def test_align_predictions_preserves_order():
    """common keys 가 sorted 순서."""
    lgbm_proba = np.array([0.1, 0.2])
    lgbm_keys = [("d2", "i1", 20211), ("d1", "i1", 20211)]
    tcn_proba = np.array([0.5, 0.6])
    tcn_keys = [("d2", "i1", 20211), ("d1", "i1", 20211)]
    label_dict = {k: 0 for k in lgbm_keys}

    _, _, _, common = _align_predictions(lgbm_proba, lgbm_keys, tcn_proba, tcn_keys, label_dict)
    assert common == sorted(common)


def test_align_predictions_y_uses_label_dict():
    """aligned_y 는 label_dict 의 값을 사용."""
    lgbm_proba = np.array([0.1, 0.2])
    lgbm_keys = [("d1", "i1", 20211), ("d2", "i1", 20211)]
    tcn_proba = np.array([0.5, 0.6])
    tcn_keys = [("d1", "i1", 20211), ("d2", "i1", 20211)]
    label_dict = {("d1", "i1", 20211): 1, ("d2", "i1", 20211): 0}

    _, _, aligned_y, common = _align_predictions(lgbm_proba, lgbm_keys, tcn_proba, tcn_keys, label_dict)
    # sorted common[0] = ("d1", "i1", 20211) → y=1
    assert aligned_y[0] == label_dict[common[0]]
    assert aligned_y[1] == label_dict[common[1]]


def test_build_tcn_sequences_returns_keys():
    """_build_tcn_sequences 가 val_keys, test_keys 반환."""
    rng = np.random.default_rng(0)
    rows = []
    for d in range(2):
        for ind in ["I001"]:
            for q in [20191, 20192, 20193, 20194, 20201, 20202, 20203, 20204]:
                rows.append({
                    "dong_code": f"d{d}",
                    "industry_code": ind,
                    "quarter": q,
                    "monthly_sales": float(rng.uniform(1e6, 1e7)),
                    "store_count": 10,
                })
    df = pd.DataFrame(rows)
    df["__y__"] = 0  # dummy label

    result = _build_tcn_sequences(
        df, df["__y__"], window_size=4, feature_cols=["monthly_sales", "store_count"],
        train_quarters={20191, 20192, 20193, 20194},
        val_quarters={20201, 20202},
        test_quarters={20203, 20204},
    )
    # 시그니처: (X_tr, X_val, X_test, y_tr, y_val, y_test, scaler, val_keys, test_keys)
    assert len(result) == 9
    val_keys = result[7]
    test_keys = result[8]
    assert all(isinstance(k, tuple) and len(k) == 3 for k in val_keys)
    assert all(isinstance(k, tuple) and len(k) == 3 for k in test_keys)
```

- [ ] **Step 2: test fail 확인**

Run: `python -m pytest tests/test_closure_risk_align.py -v`
Expected: 모두 FAIL (`_align_predictions` import 실패).

- [ ] **Step 3: `train.py` 에 `_align_predictions` 추가**

Add helper function near top of `train.py` (after imports, before existing helpers):

```python
def _align_predictions(
    lgbm_proba: np.ndarray,
    lgbm_keys: list[tuple],
    tcn_proba: np.ndarray,
    tcn_keys: list[tuple],
    label_dict: dict[tuple, int],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[tuple]]:
    """LGBM/TCN proba 를 (dong, industry, quarter) inner-join.

    Args:
        lgbm_proba: LGBM 예측 확률 array (len = N_lgbm).
        lgbm_keys: 각 LGBM proba 의 (dong_code, industry_code, quarter) tuple list.
        tcn_proba: TCN 예측 확률 array.
        tcn_keys: TCN proba 의 키 tuple list.
        label_dict: {key: label} dict.

    Returns:
        (aligned_lgbm, aligned_tcn, aligned_y, common_keys)
        common_keys 는 sorted intersection.
    """
    lgbm_dict = dict(zip(lgbm_keys, lgbm_proba))
    tcn_dict = dict(zip(tcn_keys, tcn_proba))
    common = sorted(set(lgbm_dict) & set(tcn_dict))
    if not common:
        empty = np.array([], dtype=float)
        return empty, empty, np.array([], dtype=int), []
    aligned_lgbm = np.array([lgbm_dict[k] for k in common], dtype=float)
    aligned_tcn = np.array([tcn_dict[k] for k in common], dtype=float)
    aligned_y = np.array([label_dict[k] for k in common], dtype=int)
    return aligned_lgbm, aligned_tcn, aligned_y, common
```

- [ ] **Step 4: `_build_tcn_sequences` 시그니처 확장**

Find `_build_tcn_sequences` function (currently around line 101). Modify the per-group loop to track keys:

```python
# 함수 시작 부근에서 이미 X_tr_list, y_tr_list 등이 있음. 추가:
val_keys: list[tuple] = []
test_keys: list[tuple] = []
```

루프 안에서 use_split 분기:
```python
if use_split:
    label_key = (
        str(group_sorted["dong_code"].iloc[i + window_size]),
        str(group_sorted["industry_code"].iloc[i + window_size]),
        int(label_quarter),
    )
    if label_quarter in train_quarters:
        X_tr_list.append(x_seq); y_tr_list.append(y_label)
    elif label_quarter in val_quarters:
        X_val_list.append(x_seq); y_val_list.append(y_label)
        val_keys.append(label_key)
    elif label_quarter in test_quarters:
        X_test_list.append(x_seq); y_test_list.append(y_label)
        test_keys.append(label_key)
```

함수 끝 return statement 에 val_keys, test_keys 추가:
```python
return X_tr, X_val, X_test, y_tr, y_val, y_test, feat_scaler, val_keys, test_keys
```

- [ ] **Step 5: `train_tcn` 시그니처 확장**

`train_tcn` 의 `_build_tcn_sequences` 호출 unpack 수정:
```python
X_tr, X_val, X_test, y_tr, y_val, y_test, feat_scaler, val_keys, test_keys = _build_tcn_sequences(...)
```

return statement:
```python
return model, best_auc, val_proba, test_proba, y_val, y_test, feat_scaler, val_keys, test_keys
```

- [ ] **Step 6: `train()` 의 ensemble 단계 수정**

`train_tcn` 호출 unpack 수정:
```python
tcn_model, tcn_val_auc, tcn_val_proba, tcn_test_proba, y_val_tcn, y_test_tcn, tcn_scaler, tcn_val_keys, tcn_test_keys = train_tcn(...)
```

기존 trim 기반 ensemble 코드 (line 421~ "n_val = min(len(...), len(...))" 부터 evaluate 호출 전까지) 를 다음으로 교체:

```python
# A-1: inner-join alignment (2026-05-01)
lgbm_val_keys = [
    (str(d), str(i), int(q))
    for d, i, q in zip(val_df["dong_code"], val_df["industry_code"], val_df["quarter"])
]
lgbm_test_keys = [
    (str(d), str(i), int(q))
    for d, i, q in zip(test_df["dong_code"], test_df["industry_code"], test_df["quarter"])
]
label_dict = {
    (str(row["dong_code"]), str(row["industry_code"]), int(row["quarter"])): int(row["label"])
    for _, row in df_labeled.iterrows()
}

aligned_lgbm_val, aligned_tcn_val, aligned_y_val, val_common = _align_predictions(
    lgbm_val_proba, lgbm_val_keys, tcn_val_proba, tcn_val_keys, label_dict
)
aligned_lgbm_test, aligned_tcn_test, aligned_y_test, test_common = _align_predictions(
    lgbm_test_proba, lgbm_test_keys, tcn_test_proba, tcn_test_keys, label_dict
)

logger.info("A-1 inner-join: val common=%d, test common=%d", len(val_common), len(test_common))

if len(val_common) > 0:
    ensemble_val_proba = w_lgbm * aligned_lgbm_val + w_tcn * aligned_tcn_val
    y_val_common = aligned_y_val
else:
    logger.warning("inner-join val common=0, fallback to trim")
    n_val = min(len(lgbm_val_proba), len(tcn_val_proba))
    ensemble_val_proba = w_lgbm * lgbm_val_proba[:n_val] + w_tcn * tcn_val_proba[:n_val]
    y_val_common = y_val_arr[:n_val]

if len(test_common) > 0:
    ensemble_test_proba = w_lgbm * aligned_lgbm_test + w_tcn * aligned_tcn_test
    y_test_common = aligned_y_test
else:
    logger.warning("inner-join test common=0, fallback to trim")
    n_test = min(len(lgbm_test_proba), len(tcn_test_proba)) if len(tcn_test_proba) > 0 else len(lgbm_test_proba)
    if n_test > 0 and len(tcn_test_proba) > 0:
        ensemble_test_proba = w_lgbm * lgbm_test_proba[:n_test] + w_tcn * tcn_test_proba[:n_test]
        y_test_common = y_test_arr[:n_test]
    else:
        ensemble_test_proba = lgbm_test_proba
        y_test_common = y_test_arr
```

evaluate() 호출에서 `y_val_common`, `y_test_common`, `ensemble_val_proba`, `ensemble_test_proba` 사용 (이미 코드 그대로).

- [ ] **Step 7: 5 test 통과 확인**

Run: `python -m pytest tests/test_closure_risk_align.py -v`
Expected: 5 passed.

- [ ] **Step 8: 회귀 통과 확인**

Run: `python -m pytest tests/test_closure_risk_*.py -v`
Expected: 45 passed (label 6 + split 6 + metrics 8 + regression 4 + topk 11 + b_features 5 + align 5).

기존 train_tcn 시그니처 변경으로 train_tcn 호출 site 검색해서 fix 필요할 수 있음 — `grep "train_tcn(" -r models/ tests/`. 호출자가 train.py 와 직접 호출 X 라면 OK.

- [ ] **Step 9: ruff + commit**

```bash
ruff check --fix models/closure_risk/train.py tests/test_closure_risk_align.py
ruff format models/closure_risk/train.py tests/test_closure_risk_align.py
git add models/closure_risk/train.py tests/test_closure_risk_align.py
git commit -m "$(cat <<'EOF'
feat(closure_risk): A-1 inner-join alignment (A layer T1)

LGBM/TCN proba 를 (dong, industry, quarter) 기준 inner-join 으로 ensemble.
기존 [:n] trim 의 known limitation (순서 보장 X) 해결.

_build_tcn_sequences / train_tcn 가 val_keys, test_keys 반환.
_align_predictions helper 로 inner-join + label_dict 기반 aligned y 추출.
common=0 fallback to trim (회귀 안전).

학습 신호 무영향 — ensemble layer 만 변경. AUC 변화는 alignment 정확성
회복으로 인한 측정값 보정 의미.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

DO NOT push.

---

## Task 2: A-2 Stage 1 industry prior model

**Files:**
- Create: `models/closure_risk/stage1_industry_prior.py`
- Test: `tests/test_closure_risk_stage1.py` (신규)

- [ ] **Step 1: 신규 test 파일 생성**

```python
"""A-2 Stage 1 industry prior model 단위 test."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from models.closure_risk.stage1_industry_prior import (
    STAGE1_FEATURES,
    _aggregate_industry_quarter,
    _engineer_industry_lag,
    predict_industry_prior,
    train_industry_prior_stage1,
)


def _make_synthetic(quarters, rng_seed=0):
    rng = np.random.default_rng(rng_seed)
    rows = []
    for ind in ["I001", "I002"]:
        for d in range(3):
            for q in quarters:
                rows.append({
                    "dong_code": f"d{d}",
                    "industry_code": ind,
                    "quarter": q,
                    "closure_rate": float(rng.uniform(0, 0.5)),
                    "store_count": int(rng.integers(5, 30)),
                    "monthly_sales": float(rng.uniform(1e6, 1e8)),
                    "label": int(rng.integers(0, 2)),
                })
    return pd.DataFrame(rows)


def test_aggregate_industry_quarter():
    """(industry, quarter) 단위 mean 집계."""
    df = _make_synthetic([20191, 20192], rng_seed=1)
    agg = _aggregate_industry_quarter(df)
    assert "ind_closure_rate" in agg.columns
    assert "ind_store_count" in agg.columns
    assert "ind_monthly_sales" in agg.columns
    assert len(agg) == 2 * 2  # 2 industry × 2 quarter


def test_engineer_industry_lag():
    """lag1, lag2, sales_yoy, next_closure_rate 컬럼 생성."""
    quarters = [20191, 20192, 20193, 20194, 20201, 20202]
    df = _make_synthetic(quarters)
    agg = _aggregate_industry_quarter(df)
    agg = _engineer_industry_lag(agg)

    for col in ["ind_closure_rate_lag1", "ind_closure_rate_lag2", "ind_sales_yoy", "ind_next_closure_rate"]:
        assert col in agg.columns


def test_train_industry_prior_returns_model():
    """Stage 1 LGBM fit 성공 + agg 반환."""
    quarters = [20191, 20192, 20193, 20194, 20201, 20202, 20203, 20204]
    df = _make_synthetic(quarters)
    train_quarters = {20191, 20192, 20193, 20194}

    model, agg = train_industry_prior_stage1(df, train_quarters)
    assert hasattr(model, "predict")
    assert "ind_closure_rate" in agg.columns


def test_predict_industry_prior_broadcast():
    """같은 (industry, quarter) 의 모든 dong row 에 동일 industry_prior_pred."""
    quarters = [20191, 20192, 20193, 20194, 20201, 20202, 20203, 20204]
    df = _make_synthetic(quarters)
    train_quarters = {20191, 20192, 20193, 20194}

    model, agg = train_industry_prior_stage1(df, train_quarters)
    df_with_prior = predict_industry_prior(df, model, agg)

    assert "industry_prior_pred" in df_with_prior.columns
    # 같은 (industry, quarter) row 의 prior 값 동일
    for (ind, q), grp in df_with_prior.groupby(["industry_code", "quarter"]):
        unique_priors = grp["industry_prior_pred"].unique()
        assert len(unique_priors) == 1, f"{ind}-{q}: prior 값 mismatch {unique_priors}"
```

- [ ] **Step 2: test fail 확인**

Run: `python -m pytest tests/test_closure_risk_stage1.py -v`
Expected: import 실패 (모듈 없음).

- [ ] **Step 3: 신규 모듈 작성 — `models/closure_risk/stage1_industry_prior.py`**

(spec section 2a 의 코드 그대로 — `_aggregate_industry_quarter`, `_engineer_industry_lag`, `STAGE1_FEATURES`, `train_industry_prior_stage1`, `predict_industry_prior`).

- [ ] **Step 4: 4 test 통과 확인**

Run: `python -m pytest tests/test_closure_risk_stage1.py -v`
Expected: 4 passed.

- [ ] **Step 5: ruff + commit**

```bash
ruff check --fix models/closure_risk/stage1_industry_prior.py tests/test_closure_risk_stage1.py
ruff format models/closure_risk/stage1_industry_prior.py tests/test_closure_risk_stage1.py
git add models/closure_risk/stage1_industry_prior.py tests/test_closure_risk_stage1.py
git commit -m "$(cat <<'EOF'
feat(closure_risk): A-2 Stage 1 industry prior model (A layer T2)

신규 모듈 stage1_industry_prior.py — industry-quarter level 집계 +
LGBM regressor 로 industry 평균 next_closure_rate 예측. Stage 2 의
'industry_prior_pred' 입력 feature 로 활용.

train_industry_prior_stage1: train_quarters 만으로 fit (leakage 차단).
predict_industry_prior: 모든 (industry, quarter) row 에 broadcast.

학술 근거: Wolpert (1992) two-stage stacking, hierarchical regression.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: A-2 Stage 2 통합 + LGBM_FEATURES + predict.py

**Files:**
- Modify: `models/closure_risk/data_prep.py` (LGBM_FEATURES)
- Modify: `models/closure_risk/train.py` (Stage 1 호출)
- Modify: `models/closure_risk/predict.py` (_load_models + predict)

- [ ] **Step 1: LGBM_FEATURES 에 `industry_prior_pred` 추가**

`data_prep.py` 의 `LGBM_FEATURES` list 끝에 (현재 `"adstrd_flpop"` 다음, 주석 처리된 B-1 list 위에) 추가:

```python
    "adstrd_flpop",  # 행정동 전체 유동인구
    # A-2 Stage 1 hierarchical (2026-05-01)
    "industry_prior_pred",  # industry-level prior model 예측 (Wolpert 1992 stacking)
    # B-1 신규 8 derivation (2026-05-01) — production rollback (commit 9b09cd1)
    # ... (주석 처리된 항목 그대로)
```

LGBM_FEATURES 길이: 15 → 16.

- [ ] **Step 2: `train.py` Stage 1 통합**

`train()` 의 `_make_labels(df_unlabeled, train_quarters=train_quarters)` 직후, split 별 row 재추출 **이전** 에 추가:

```python
# A-2 Stage 1: industry prior model 학습 + df_labeled 에 industry_prior_pred 컬럼 추가
from models.closure_risk.stage1_industry_prior import (
    train_industry_prior_stage1,
    predict_industry_prior,
)
stage1_model, stage1_agg = train_industry_prior_stage1(df_labeled, train_quarters)
df_labeled = predict_industry_prior(df_labeled, stage1_model, stage1_agg)
logger.info("A-2 Stage 1 prior 추가 완료. industry_prior_pred range: [%.4f, %.4f]",
            df_labeled["industry_prior_pred"].min(),
            df_labeled["industry_prior_pred"].max())

# Stage 1 model + agg 저장
import pickle
stage1_path = WEIGHTS_DIR / "stage1_industry_prior.pkl"
with open(stage1_path, "wb") as f:
    pickle.dump({"model": stage1_model, "agg": stage1_agg}, f)
logger.info("Stage 1 model 저장: %s", stage1_path)
```

- [ ] **Step 3: `predict.py` Stage 1 통합**

`_load_models()` 끝부분에 Stage 1 추가:

```python
def _load_models() -> tuple:
    global _cache  # noqa: PLW0603
    if _cache:
        return _cache["lgbm"], _cache["tcn"], _cache["weights"], _cache["scaler"], _cache["stage1"]

    # ... 기존 로드 ...

    stage1_path = WEIGHTS_DIR / "stage1_industry_prior.pkl"
    stage1_data = None
    if stage1_path.exists():
        with open(stage1_path, "rb") as f:
            stage1_data = pickle.load(f)  # noqa: S301

    _cache.update({"lgbm": lgbm, "tcn": tcn, "weights": ensemble_w, "scaler": tcn_scaler, "stage1": stage1_data})
    return lgbm, tcn, ensemble_w, tcn_scaler, stage1_data
```

`predict()` 함수의 `_load_models()` unpack 수정:
```python
lgbm_model, tcn_model, ensemble_w, tcn_scaler, stage1_data = _load_models()
```

`x_lgbm` 계산 직전, `latest` 계산 후에 industry_prior_pred lookup 추가:
```python
# A-2 Stage 1 prior lookup
industry_prior_pred = 0.0
if stage1_data is not None:
    agg = stage1_data["agg"]
    matching = agg[
        (agg["industry_code"] == industry_code)
        & (agg["quarter"] == int(latest["quarter"]))
    ]
    if len(matching) > 0 and "industry_prior_pred" in matching.columns:
        industry_prior_pred = float(matching["industry_prior_pred"].iloc[0])
    elif len(matching) > 0:
        # agg 에 prediction 미저장 → on-the-fly
        from models.closure_risk.stage1_industry_prior import STAGE1_FEATURES
        X = matching[STAGE1_FEATURES].fillna(0).values
        industry_prior_pred = float(stage1_data["model"].predict(X)[0])
```

`x_lgbm` 계산 시 `industry_prior_pred` 가 LGBM_FEATURES 에 포함되어 있으므로 `latest.get(...)` 가 정상 작동 — 단, latest 의 industry_prior_pred 컬럼이 채워져 있어야 함. 그렇지 않으면 위에서 lookup 한 값으로 직접 array 구성:

```python
x_lgbm = np.array(
    [latest.get(f, 0.0) if f != "industry_prior_pred" else industry_prior_pred for f in LGBM_FEATURES],
    dtype=np.float32,
)
```

또한 `predict_industry_prior` 의 결과 column 이 `agg` 에는 있지만 `_engineer_lag_features` 의 결과인 `latest` 에는 없을 가능성. 안전하게 위 코드처럼 `if f != "industry_prior_pred" else industry_prior_pred` 분기 사용.

- [ ] **Step 4: 회귀 test 보강 — predict() 가 stage1 미존재 시 graceful**

Append to `tests/test_closure_risk_stage1.py`:

```python
def test_predict_works_without_stage1_pkl(tmp_path, monkeypatch):
    """stage1_industry_prior.pkl 미존재 시 predict() 가 그래도 작동 (industry_prior_pred=0.0 fallback)."""
    from models.closure_risk import predict as predict_mod
    # _cache 비우기
    predict_mod._cache.clear()
    # WEIGHTS_DIR 을 빈 tmp 로 monkeypatch — 모든 weight 미존재
    monkeypatch.setattr(predict_mod, "WEIGHTS_DIR", tmp_path)

    # _load_models 가 FileNotFoundError → mock 반환
    result = predict_mod.predict("11440555", "CS100001")
    assert result["is_mock"] is True or result["risk_score"] is None
    # cache 정리 (다른 test 영향 X)
    predict_mod._cache.clear()
```

- [ ] **Step 5: 회귀 통과 확인**

Run: `python -m pytest tests/test_closure_risk_*.py -v`
Expected: 50 passed (label 6 + split 6 + metrics 8 + regression 4 + topk 11 + b_features 5 + align 5 + stage1 5).

만약 LGBM_FEATURES 길이 검증 test 가 있어 길이 mismatch 로 실패 시:
- `tests/test_closure_risk_b_features.py:test_LGBM_FEATURES_count_after_b1_rollback` 를 16 으로 update.

- [ ] **Step 6: ruff + commit**

```bash
ruff check --fix models/closure_risk/data_prep.py models/closure_risk/train.py models/closure_risk/predict.py tests/test_closure_risk_stage1.py tests/test_closure_risk_b_features.py
ruff format models/closure_risk/data_prep.py models/closure_risk/train.py models/closure_risk/predict.py tests/test_closure_risk_stage1.py tests/test_closure_risk_b_features.py
git add models/closure_risk/data_prep.py models/closure_risk/train.py models/closure_risk/predict.py tests/test_closure_risk_stage1.py tests/test_closure_risk_b_features.py
git commit -m "$(cat <<'EOF'
feat(closure_risk): A-2 Stage 1 통합 + LGBM_FEATURES industry_prior_pred (A layer T3)

train.py: _make_labels 직후 train_industry_prior_stage1 호출 →
df_labeled["industry_prior_pred"] broadcast → stage1.pkl 저장.

data_prep.py: LGBM_FEATURES 15 → 16 (industry_prior_pred 추가).

predict.py: _load_models 가 stage1.pkl load. predict() 에서
(industry_code, latest_quarter) lookup → x_lgbm 의 industry_prior_pred
slot 채움. stage1.pkl 미존재 시 0.0 fallback (graceful).

LGBM_FEATURES 길이 test 16 으로 업데이트.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Production retrain + decision

- [ ] **Step 1: retrain**

```bash
cd "/c/Users/804/Documents/final project"
python -m models.closure_risk.train 2>&1 | tee /tmp/closure_risk_retrain_a.log
```

Expected:
- Stage 1 학습 log + industry_prior_pred range
- Stage 1 model 저장 log
- 기존 LGBM/TCN 학습 (16 feature)
- A-1 inner-join: val/test common count log
- threshold fit (D layer, 동일)
- 최종 val/test AUC

- [ ] **Step 2: metric 비교 + 의사결정**

```bash
python -c "
import json
with open('models/closure_risk/weights/metrics.json') as f:
    m = json.load(f)
print('val AUC:', m['ensemble']['val']['auc'])
print('test AUC:', m['ensemble']['test']['auc'])
print('threshold danger:', m['thresholds']['danger'])
"
```

vs D layer baseline (181b84f): val 0.5950, test 0.5974.

**의사결정 규칙**:
- 두 AUC 모두 baseline 대비 -0.01 이상 떨어짐 → **rollback** (B layer 패턴)
  - rollback: `git checkout 181b84f -- models/closure_risk/weights/`
  - LGBM_FEATURES 에서 `industry_prior_pred` 주석 처리
  - stage1 모듈은 보존 (별도 sprint 활용 가능)
- 둘 중 하나라도 baseline 이상 → **keep** (개선 또는 alignment 정확성 회복으로 평가)
  - production 으로 적용. retrospective 에 결과 기록.

- [ ] **Step 3: 산출물 commit (또는 rollback commit)**

**Keep 시**:
```bash
git add models/closure_risk/weights/
git commit -m "chore(closure_risk): retrain with A layer (T4) — keep"
```

**Rollback 시**:
```bash
git checkout 181b84f -- models/closure_risk/weights/
# LGBM_FEATURES 의 industry_prior_pred 주석 처리
# (Edit data_prep.py)
git add models/closure_risk/data_prep.py models/closure_risk/weights/
git commit -m "chore(closure_risk): A layer rollback — Stage 1 신호 noise (T4)"
```

---

## Task 5: 회고

**Files:**
- Create: `docs/retrospective/2026-05-01-a-layer.md`

내용 구조:
1. 요약 — A-3 결과 (keep/rollback)
2. 배경 — D layer 후 alignment + hierarchy 의 두 축
3. 작업 내역 — T1~T4 + commit SHA
4. 결과 — A-1 효과 (alignment 정확성), A-2 효과 (Stage 1 hierarchy)
5. 진단 — keep 시 개선 원인, rollback 시 noise 원인 분석
6. 다음 sprint 우선순위 — D-3 calibration / B-3 / B-4 등
7. 배운 점

```bash
git add docs/retrospective/2026-05-01-a-layer.md
git commit -m "docs(closure_risk): 2026-05-01 A layer 회고"
```

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| A-1 후 회귀 test 깨짐 | T1 의 5 신규 test + 기존 40 test 통과 강제 |
| A-2 noise → AUC 하락 | T4 의 의사결정 규칙으로 자동 rollback. B-1 패턴 보존 |
| Stage 1 train data 부족 | ValueError + skip stage1 (predict.py default 0.0) |
| predict.py 의 cache stale | T3 의 회귀 test 가 monkeypatch 로 격리 검증 |
| scope 큼 (12~16h) | 5 task 분해 + 중간 commit. T1 후 retrain check 도 가능 |

## Self-Review

1. **Spec coverage**: ✅ — A-1 (T1), A-2 Stage 1 (T2), A-2 Stage 2 + LGBM_FEATURES + predict.py (T3), retrain + decision (T4), 회고 (T5).
2. **Placeholder scan**: ✅ — TBD/TODO 없음.
3. **Type consistency**: ✅ — `_align_predictions` 시그니처 일관, `train_industry_prior_stage1` Returns tuple, `LGBM_FEATURES` 16.

승인 후 subagent-driven-development 실행.
