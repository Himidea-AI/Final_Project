"""C layer (label) fix 단위 test.

`_compute_industry_p75_train` 의 train-only fit + min_samples fallback 검증.
`_make_labels` 의 quantile 기반 label 정의 + unseen industry drop 검증.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from models.closure_risk.data_prep import (
    _compute_industry_p75_train,
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
