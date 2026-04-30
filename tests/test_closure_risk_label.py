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
            for d in range(5):
                rows.append(
                    {
                        "dong_code": f"114403{d:02d}",
                        "industry_code": ind,
                        "quarter": q,
                        "closure_rate": float(rng.uniform(0, 0.5)),
                        "store_count": 10,
                        "monthly_sales": 1_000_000.0,
                    }
                )
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
        "I_thin": [20191],  # 1 quarter × 5 dong = 5 rows; min_samples=8 → NaN
    }
    df = _make_synthetic_df(quarters, closure_rates_seed=7)

    train_quarters = {20191, 20192, 20193, 20194}
    p75_series, global_p75 = _compute_industry_p75_train(df, train_quarters, min_samples=8)

    assert pd.isna(p75_series.get("I_thin"))
    assert not pd.isna(p75_series["I001"])
    assert global_p75 > 0


def _make_synthetic_df_with_next(quarters: list[int], rng_seed: int = 0) -> pd.DataFrame:
    """(industry, quarter) 데이터 — _make_labels 회귀용."""
    rng = np.random.default_rng(rng_seed)
    rows = []
    for ind in ["I001", "I002"]:
        for d in range(5):
            for q in quarters:
                rows.append(
                    {
                        "dong_code": f"114403{d:02d}",
                        "industry_code": ind,
                        "quarter": q,
                        "closure_rate": float(rng.uniform(0, 0.5)),
                        "store_count": 10,
                        "monthly_sales": 1_000_000.0,
                    }
                )
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
    for q in [20191, 20192, 20193, 20194, 20201, 20202]:
        for d in range(5):
            rows.append(
                {
                    "dong_code": f"114403{d:02d}",
                    "industry_code": "I001",
                    "quarter": q,
                    "closure_rate": float(rng.uniform(0, 0.5)),
                    "store_count": 10,
                    "monthly_sales": 1_000_000.0,
                }
            )
    for q in [20201, 20202]:
        for d in range(5):
            rows.append(
                {
                    "dong_code": f"114403{d:02d}",
                    "industry_code": "I_unseen",
                    "quarter": q,
                    "closure_rate": float(rng.uniform(0, 0.5)),
                    "store_count": 10,
                    "monthly_sales": 1_000_000.0,
                }
            )
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
            rows.append(
                {
                    "dong_code": f"114403{d:02d}",
                    "industry_code": "I001",
                    "quarter": q,
                    "closure_rate": float(rng.uniform(0, 0.5)),
                    "store_count": 10,
                    "monthly_sales": 1_000_000.0,
                }
            )
    df = pd.DataFrame(rows)

    train_quarters = {20191, 20192, 20193, 20194}
    labeled = _make_labels(df, train_quarters=train_quarters)
    p75_series, _ = _compute_industry_p75_train(df, train_quarters)
    expected_p75 = p75_series["I001"]
    df_sorted = df.sort_values(["dong_code", "industry_code", "quarter"]).copy()
    df_sorted["next_cr"] = df_sorted.groupby(["dong_code", "industry_code"])["closure_rate"].shift(-1)
    df_sorted = df_sorted[df_sorted["next_cr"].notna()].copy()
    df_sorted["expected_label"] = (df_sorted["next_cr"] > expected_p75).astype(int)
    merged = labeled.merge(
        df_sorted[["dong_code", "industry_code", "quarter", "expected_label"]],
        on=["dong_code", "industry_code", "quarter"],
    )
    assert (merged["label"] == merged["expected_label"]).all()
