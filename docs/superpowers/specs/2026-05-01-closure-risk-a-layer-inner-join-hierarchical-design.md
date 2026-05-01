# 폐업 위험도 모델 A layer (inner-join + hierarchical) — Design Spec

> **상태**: 브레인스토밍 완료, 사용자 승인 (2026-05-01).
> **작업 영역**: `models/closure_risk/` (B2 — 수지니 영역, A1 찬영 cross-team contribution).
> **선행 작업**: E ✅, C ✅, D ✅, B-1 ⚠️ (rollback). 현 production = D layer (181b84f).
> **Plan 단계**: 본 spec 통과 후 `writing-plans` skill 으로 implementation plan 작성.

## Goal

A layer 두 축 동시 개선:
1. **Inner-join alignment** — 현재 `train.py:423` 의 `[:n]` trim 으로 LGBM/TCN proba 를 ensemble 하는 방식이 (dong, industry, quarter) 순서 보장 X. (dong, industry, quarter) 기준 inner-join 으로 정확한 ensemble.
2. **Two-stage hierarchical** — Stage 1 industry-level prior model (LGBM 작은 모델) → Stage 2 dong-level model (기존 LGBM + TCN) 의 입력 feature 로 industry_prior_pred 추가.

## Background

D layer (181b84f) 의 현재 production:
- ensemble val AUC = 0.5950, test AUC = 0.5974
- threshold fit + predict_topk API ✅

남은 layer 한계:
- **Ensemble alignment 정확성 의문**: `train.py:423` 의 trim 이 known limitation. LGBM 의 i-th row 와 TCN 의 i-th sequence 가 같은 sample 인지 보장 X. AUC 측정 자체가 misleading 가능.
- **모델 구조 단조로움**: LGBM + TCN 모두 dong×industry×quarter 단일 단위. industry hierarchy 미반영.

본 spec 은 두 축 (alignment + hierarchy) 을 함께 도입 — A-1 단독으로는 학습 신호 무영향이라 safe, A-2 결합 시 잠재력 큼.

B-1 실패 (feature 8개 noise) 의 교훈: 단순 derivation 보다 **명확한 hierarchy** 의 신호가 더 의미 있을 가능성. industry-level 통계는 macro broadcast (B-1 cpi 처럼) 와 다르게 dong×quarter 마다 변하는 dynamic 신호.

## Architecture

### 변경 전 (D layer)
```
build_dataset → split → label → train (LGBM 단일, TCN 단일) → ensemble (trim) → save
                                                                ↑ alignment 부정확
```

### 변경 후 (A-3)
```
build_dataset → split → label
    ↓
_train_industry_prior_stage1(train_df, train_quarters)
    ↓
df_labeled["industry_prior_pred"] = predict_stage1(df_labeled)
    ↓
train (LGBM with 16 features incl. industry_prior_pred, TCN unchanged)
    ↓
align(LGBM proba, TCN proba) on (dong, industry, quarter)  ← inner-join
    ↓
ensemble (정확한 alignment) → evaluate → save
```

## Components

### 1. A-1: Inner-join alignment

#### 1a. `_build_tcn_sequences` 시그니처 확장

현재 반환: `(X_tr, X_val, X_test, y_tr, y_val, y_test, feat_scaler)`.

변경 후: `(X_tr, X_val, X_test, y_tr, y_val, y_test, feat_scaler, val_keys, test_keys)`.

`val_keys`, `test_keys` = `list[tuple[str, str, int]]` of (dong_code, industry_code, quarter) per sequence.

```python
# 기존 sequence 생성 loop 안에서
for i in range(len(group_sorted) - window_size):
    x_seq = feat_vals[i : i + window_size]
    y_label = labels[i + window_size]
    label_quarter = quarters_arr[i + window_size]
    label_key = (
        group_sorted["dong_code"].iloc[i + window_size],
        group_sorted["industry_code"].iloc[i + window_size],
        int(label_quarter),
    )
    if use_split:
        if label_quarter in train_quarters:
            X_tr_list.append(x_seq); y_tr_list.append(y_label)
        elif label_quarter in val_quarters:
            X_val_list.append(x_seq); y_val_list.append(y_label)
            val_keys.append(label_key)
        elif label_quarter in test_quarters:
            X_test_list.append(x_seq); y_test_list.append(y_label)
            test_keys.append(label_key)
```

#### 1b. `train_tcn` 시그니처 확장

현재 반환: `(model, best_auc, val_proba, test_proba, y_val, y_test, feat_scaler)`.

변경 후: `(model, best_auc, val_proba, test_proba, y_val, y_test, feat_scaler, val_keys, test_keys)`.

#### 1c. `_align_predictions` helper (신규)

```python
def _align_predictions(
    lgbm_proba: np.ndarray,
    lgbm_keys: list[tuple],
    tcn_proba: np.ndarray,
    tcn_keys: list[tuple],
    label_dict: dict[tuple, int],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[tuple]]:
    """LGBM/TCN proba 를 (dong, industry, quarter) inner-join.

    Returns:
        (aligned_lgbm, aligned_tcn, aligned_y, common_keys)
    """
    lgbm_dict = dict(zip(lgbm_keys, lgbm_proba))
    tcn_dict = dict(zip(tcn_keys, tcn_proba))
    common = sorted(set(lgbm_dict) & set(tcn_dict))
    aligned_lgbm = np.array([lgbm_dict[k] for k in common])
    aligned_tcn = np.array([tcn_dict[k] for k in common])
    aligned_y = np.array([label_dict[k] for k in common])
    return aligned_lgbm, aligned_tcn, aligned_y, common
```

#### 1d. `train()` ensemble 단계 변경

```python
# LGBM key list 생성 (val_df 의 row order)
lgbm_val_keys = list(zip(val_df["dong_code"], val_df["industry_code"], val_df["quarter"].astype(int)))
lgbm_test_keys = list(zip(test_df["dong_code"], test_df["industry_code"], test_df["quarter"].astype(int)))

# label dict
label_dict = {
    (row["dong_code"], row["industry_code"], int(row["quarter"])): int(row["label"])
    for _, row in df_labeled.iterrows()
}

# inner-join
aligned_lgbm_val, aligned_tcn_val, aligned_y_val, val_common = _align_predictions(
    lgbm_val_proba, lgbm_val_keys, tcn_val_proba, tcn_val_keys, label_dict
)
aligned_lgbm_test, aligned_tcn_test, aligned_y_test, test_common = _align_predictions(
    lgbm_test_proba, lgbm_test_keys, tcn_test_proba, tcn_test_keys, label_dict
)

ensemble_val_proba = w_lgbm * aligned_lgbm_val + w_tcn * aligned_tcn_val
ensemble_test_proba = w_lgbm * aligned_lgbm_test + w_tcn * aligned_tcn_test
```

evaluate() 도 `aligned_y_val`, `aligned_y_test` 사용.

### 2. A-2: Two-stage hierarchical

#### 2a. Stage 1 model — `models/closure_risk/stage1_industry_prior.py` (신규 파일)

```python
"""Industry-level prior model — A-2 hierarchical Stage 1.

industry-quarter level aggregates (mean closure_rate, store_count, sales) 로
'다음 분기 industry 평균 closure_rate' 예측. Stage 2 의 feature 입력.

학술 근거:
    Two-stage stacking — Wolpert (1992).
    Hierarchical aggregation — 도메인 hierarchy 인코딩.
"""

from __future__ import annotations

import logging

import lightgbm as lgb
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _aggregate_industry_quarter(df: pd.DataFrame) -> pd.DataFrame:
    """(industry, quarter) 단위 집계.

    Returns:
        df with columns: industry_code, quarter, ind_closure_rate, ind_store_count,
                         ind_monthly_sales (각각 mean across dong)
    """
    agg = df.groupby(["industry_code", "quarter"]).agg(
        ind_closure_rate=("closure_rate", "mean"),
        ind_store_count=("store_count", "mean"),
        ind_monthly_sales=("monthly_sales", "mean"),
    ).reset_index()
    return agg


def _engineer_industry_lag(agg: pd.DataFrame) -> pd.DataFrame:
    """industry-level lag/yoy 피처."""
    agg = agg.sort_values(["industry_code", "quarter"]).copy()
    g = agg.groupby("industry_code")
    agg["ind_closure_rate_lag1"] = g["ind_closure_rate"].shift(1)
    agg["ind_closure_rate_lag2"] = g["ind_closure_rate"].shift(2)
    agg["ind_store_count_lag1"] = g["ind_store_count"].shift(1)
    agg["ind_sales_yoy"] = (agg["ind_monthly_sales"] - g["ind_monthly_sales"].shift(4)) / (g["ind_monthly_sales"].shift(4).abs() + 1)
    agg["ind_next_closure_rate"] = g["ind_closure_rate"].shift(-1)
    return agg


STAGE1_FEATURES = [
    "ind_closure_rate_lag1",
    "ind_closure_rate_lag2",
    "ind_store_count_lag1",
    "ind_sales_yoy",
]


def train_industry_prior_stage1(
    df: pd.DataFrame,
    train_quarters: set[int],
) -> tuple[object, pd.DataFrame]:
    """Stage 1 LGBM — industry 평균 next_closure_rate 예측.

    Args:
        df: 전체 dataset (lag feature 적용 + label 포함).
        train_quarters: train split 분기.

    Returns:
        (lgbm_model, agg_with_features) — agg_with_features 는 모든 (industry, quarter) row + ind_features.
    """
    agg = _aggregate_industry_quarter(df)
    agg = _engineer_industry_lag(agg)
    train_agg = agg[agg["quarter"].isin(train_quarters) & agg["ind_next_closure_rate"].notna()].copy()

    if len(train_agg) < 10:
        raise ValueError(f"Stage 1 train data 부족: {len(train_agg)} rows")

    X = train_agg[STAGE1_FEATURES].fillna(0).values
    y = train_agg["ind_next_closure_rate"].values

    model = lgb.LGBMRegressor(
        num_leaves=15,
        n_estimators=100,
        learning_rate=0.05,
        random_state=42,
        verbose=-1,
    )
    model.fit(X, y)
    logger.info("Stage 1 industry prior model 학습 완료 (%d rows)", len(train_agg))
    return model, agg


def predict_industry_prior(
    df: pd.DataFrame,
    model: object,
    agg: pd.DataFrame,
) -> pd.DataFrame:
    """df 에 industry_prior_pred 컬럼 추가.

    같은 (industry, quarter) 의 모든 dong row 에 동일 값 broadcast.
    """
    agg = agg.copy()
    X = agg[STAGE1_FEATURES].fillna(0).values
    agg["industry_prior_pred"] = model.predict(X)

    df = df.copy()
    df = df.merge(
        agg[["industry_code", "quarter", "industry_prior_pred"]],
        on=["industry_code", "quarter"],
        how="left",
    )
    df["industry_prior_pred"] = df["industry_prior_pred"].fillna(0.0)
    return df
```

#### 2b. Stage 2 — LGBM 입력에 추가

`LGBM_FEATURES` 에 `"industry_prior_pred"` 추가 → 15 + 1 = 16. 기존 `_engineer_lag_features` 의 derivation 8개는 그대로 보존 (LGBM 미사용 — B-1 rollback).

#### 2c. `train()` 통합

```python
# label 생성 직후
df_labeled = _make_labels(df_unlabeled, train_quarters=train_quarters)

# A-2 Stage 1
from models.closure_risk.stage1_industry_prior import (
    train_industry_prior_stage1, predict_industry_prior
)
stage1_model, agg = train_industry_prior_stage1(df_labeled, train_quarters)
df_labeled = predict_industry_prior(df_labeled, stage1_model, agg)

# Stage 1 model 저장
import pickle
with open(WEIGHTS_DIR / "stage1_industry_prior.pkl", "wb") as f:
    pickle.dump({"model": stage1_model, "agg": agg}, f)

# 이후 기존 Stage 2 학습 (LGBM 16 feature, TCN 그대로)
```

#### 2d. `predict.py` 추론 시 Stage 1 통합

```python
def _load_models() -> tuple:
    # ... 기존 ...
    stage1_path = WEIGHTS_DIR / "stage1_industry_prior.pkl"
    stage1_data = None
    if stage1_path.exists():
        with open(stage1_path, "rb") as f:
            stage1_data = pickle.load(f)  # {"model": ..., "agg": ...}
    return lgbm, tcn, ensemble_w, tcn_scaler, stage1_data


def predict(...):
    # ...
    lgbm_model, tcn_model, ensemble_w, tcn_scaler, stage1_data = _load_models()
    # ... 기존 ts_eng 계산 ...

    # A-2 Stage 1 prior lookup
    if stage1_data is not None:
        ind_prior = stage1_data["agg"][
            (stage1_data["agg"]["industry_code"] == industry_code)
            & (stage1_data["agg"]["quarter"] == latest_quarter)
        ]
        industry_prior_pred = float(ind_prior["industry_prior_pred"].iloc[0]) if len(ind_prior) > 0 else 0.0
    else:
        industry_prior_pred = 0.0

    # x_lgbm 에 추가
    x_lgbm = np.array([latest.get(f, 0.0) for f in LGBM_FEATURES if f != "industry_prior_pred"], dtype=np.float32)
    x_lgbm = np.append(x_lgbm, industry_prior_pred)
```

### 3. 회귀 호환성

- `models/interface.py:485` — predict() signature 그대로 → 무영향
- 기존 weight pkl: stage1_industry_prior.pkl 신규, 나머지 (LGBM, TCN, scaler, ensemble_w) 재학습 필수
- `LGBM_FEATURES` 16개 → 학습/추론 통합

## Data Flow

1. `build_closure_risk_dataset` → df_unlabeled
2. `_time_based_split` → train/val/test_quarters
3. `_make_labels(df_unlabeled, train_quarters)` → df_labeled (label, industry_p75)
4. **A-2 Stage 1**:
   - `train_industry_prior_stage1(df_labeled, train_quarters)` → (model, agg)
   - `predict_industry_prior(df_labeled, model, agg)` → df_labeled + industry_prior_pred 컬럼
   - Stage 1 model + agg pickle 저장
5. split → train_df / val_df / test_df 재추출
6. LGBM 학습 (16 feature)
7. TCN 학습 (34 feature, keys 반환)
8. **A-1 inner-join**: `_align_predictions` → aligned proba/y
9. ensemble weight (val AUC 비례), threshold fit, evaluate, save metrics

## Error Handling

| case | 처리 |
|---|---|
| Stage 1 train data 부족 (industry × quarter < 10) | ValueError |
| inner-join common keys 0 건 | warning + fallback to trim (회귀 안전) |
| stage1_industry_prior.pkl 미존재 (predict 시) | industry_prior_pred=0.0 fallback |
| `agg` 에 (industry, quarter) 없음 (예: 신규 industry) | 0.0 fallback |
| key list 와 proba length mismatch | ValueError + log |

## Testing

### A-1 inner-join (~5 test) — `tests/test_closure_risk_align.py`

1. `test_align_predictions_inner_join` — 같은 key 만 ensemble
2. `test_align_predictions_handles_no_overlap` — common=0 시 빈 array
3. `test_align_predictions_preserves_order` — sorted common keys
4. `test_build_tcn_sequences_returns_keys` — val_keys, test_keys 반환
5. `test_train_tcn_returns_keys` — train_tcn 시그니처 확장 검증

### A-2 Stage 1 (~4 test) — `tests/test_closure_risk_stage1.py`

1. `test_aggregate_industry_quarter` — group_by 결과 정확성
2. `test_engineer_industry_lag` — lag1/lag2/yoy 계산
3. `test_train_industry_prior_returns_model` — fit OK
4. `test_predict_industry_prior_broadcast` — 같은 (industry, quarter) row 에 동일 값

### 회귀

- 기존 40 closure_risk test 전체 통과
- ensemble AUC 측정이 trim 시점과 비교 (T1 후 / T3 후)

### Production retrain (T4)

- D layer baseline (181b84f) AUC 0.5950 / 0.5974 vs A-3 후 retrain 결과
- 의사결정: keep (개선) vs rollback (degradation, B-1 패턴)

## Risks

| Risk | Mitigation |
|---|---|
| inner-join 후 sample 수 감소 → metric 추정 불안정 | TCN sample 수 (sequence drop 후) 가 lower bound. 영향 측정 + 회고 명시 |
| Stage 1 의 `industry_prior_pred` 가 LGBM 에 noise 추가 | B-1 패턴. retrain 결과 나쁘면 LGBM_FEATURES 에서 제거 (rollback) |
| Stage 1 train data 부족 (industry × quarter < 10) | ValueError + skip stage1 (default fallback 0.0) |
| `predict.py` 변경이 기존 추론 깨뜨림 | T3 에서 명시적 회귀 test (existing predict() 동작 그대로) |
| Stage 1 model + agg 저장 size | pickle ~수 KB. 무시 가능 |
| scope 큼 (12~16h) | 5 task 분해, 중간 commit. T1 후 retrain check 권장 (alignment 만의 효과) |

## Out of Scope

- A-2 additive ensemble (stage1_pred + stage2_pred 별도 가중) — feature 방식 채택. 별도 spec 가능
- B-3 (hierarchical full) — 본 spec 의 stage1 이 부분 hierarchical. 더 깊은 층 (industry × time × dong residual) 은 별도
- B-4 (새 데이터 source) — 별도 spec
- D-3 (isotonic calibration) — 별도 spec
- TCN 에 Stage 1 prior 입력 — TCN 은 그대로 (sequence model 의 통합 복잡)
- predict_topk 의 Stage 1 통합 — predict() 만 통합, predict_topk 는 호출 chain 으로 자동 적용

## 참고 학술 자료

- Wolpert, D. H. (1992). "Stacked generalization." *Neural Networks* 5(2). — Two-stage stacking 표준
- Inner-join alignment 의 implicit assumption (same key for all models) 는 ensemble 의 기본 가정
- Hierarchical regression — Gelman & Hill (2006). 본 spec 의 industry-level prior 가 partial pooling 의 LGBM 변형
