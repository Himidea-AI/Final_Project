"""B-3 dong residual feature 단위 test."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest  # noqa: F401

from models.closure_risk.data_prep import LGBM_FEATURES, add_dong_residual_feature


def _make_df_with_lag1(quarters: list[int], rng_seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(rng_seed)
    rows = []
    for ind in ["I001", "I002"]:
        for d in range(3):
            for q in quarters:
                rows.append(
                    {
                        "dong_code": f"d{d}",
                        "industry_code": ind,
                        "quarter": q,
                        "closure_rate_lag1": float(rng.uniform(0, 0.5)),
                    }
                )
    return pd.DataFrame(rows)


def test_add_dong_residual_creates_column():
    """add_dong_residual_feature 후 dong_closure_rate_residual_lag1 컬럼 존재."""
    df = _make_df_with_lag1([20191, 20192, 20193, 20194], rng_seed=1)
    train_quarters = {20191, 20192, 20193, 20194}
    out = add_dong_residual_feature(df, train_quarters)
    assert "dong_closure_rate_residual_lag1" in out.columns


def test_add_dong_residual_train_only_fit():
    """val/test 분기의 closure_rate_lag1 이 industry mean 계산에 안 들어감."""
    df = _make_df_with_lag1([20191, 20192, 20193, 20194, 20201, 20202], rng_seed=42)
    train_quarters = {20191, 20192, 20193, 20194}

    out = add_dong_residual_feature(df, train_quarters)

    # 직접 계산한 train-only mean 과 비교
    train_only = df[df["quarter"].isin(train_quarters)]
    expected_mean_i001 = train_only[train_only["industry_code"] == "I001"]["closure_rate_lag1"].mean()

    # I001 의 모든 row 의 residual 이 closure_rate_lag1 - expected_mean_i001 와 일치
    i001_rows = out[out["industry_code"] == "I001"]
    expected_residuals = i001_rows["closure_rate_lag1"].fillna(0) - expected_mean_i001
    diffs = (i001_rows["dong_closure_rate_residual_lag1"] - expected_residuals).abs()
    assert (diffs < 1e-9).all()


def test_LGBM_FEATURES_count_after_b3():
    """A-2 Stage 1 + B-3 추가 후 LGBM_FEATURES = 17."""
    assert len(LGBM_FEATURES) == 17, f"LGBM_FEATURES 길이 mismatch: {len(LGBM_FEATURES)}"
    assert "dong_closure_rate_residual_lag1" in LGBM_FEATURES
    assert "industry_prior_pred" in LGBM_FEATURES
