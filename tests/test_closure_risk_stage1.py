"""A-2 Stage 1 industry prior model 단위 test."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest  # noqa: F401

from models.closure_risk.stage1_industry_prior import (
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
                rows.append(
                    {
                        "dong_code": f"d{d}",
                        "industry_code": ind,
                        "quarter": q,
                        "closure_rate": float(rng.uniform(0, 0.5)),
                        "store_count": int(rng.integers(5, 30)),
                        "monthly_sales": float(rng.uniform(1e6, 1e8)),
                        "label": int(rng.integers(0, 2)),
                    }
                )
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
    for (ind, q), grp in df_with_prior.groupby(["industry_code", "quarter"]):
        unique_priors = grp["industry_prior_pred"].unique()
        assert len(unique_priors) == 1, f"{ind}-{q}: prior 값 mismatch {unique_priors}"
