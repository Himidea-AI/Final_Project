"""B layer (feature expansion) 단위 test.

8 신규 LGBM feature 의 derivation 정확성 + LGBM_FEATURES 길이 검증.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest  # noqa: F401  (T2/T3 사용 가능)

from models.closure_risk.data_prep import LGBM_FEATURES, _engineer_lag_features


def _make_synthetic_full(quarters: list[int], rng_seed: int = 0) -> pd.DataFrame:
    """B-1 derivation 검증용 — ALL_FEATURES 의 dependency column 포함."""
    rng = np.random.default_rng(rng_seed)
    rows = []
    for ind in ["I001"]:
        for d in range(3):
            for q in quarters:
                rows.append(
                    {
                        "dong_code": f"114403{d:02d}",
                        "industry_code": ind,
                        "quarter": q,
                        "closure_rate": float(rng.uniform(0, 0.5)),
                        "store_count": int(rng.integers(5, 30)),
                        "monthly_sales": float(rng.uniform(1e6, 1e8)),
                        "weekday_sales": float(rng.uniform(5e5, 5e7)),
                        "weekend_sales": float(rng.uniform(2e5, 3e7)),
                        "age_20_sales": float(rng.uniform(1e5, 1e7)),
                        "age_60_above_sales": float(rng.uniform(1e5, 1e7)),
                        "open_count": int(rng.integers(0, 5)),
                        "close_count": int(rng.integers(0, 5)),
                        "total_pop": int(rng.integers(10000, 50000)),
                        "cpi_index": float(rng.uniform(95, 110)),
                        "holiday_count": int(rng.integers(1, 5)),
                        "franchise_count": int(rng.integers(0, 5)),
                    }
                )
    return pd.DataFrame(rows)


def test_engineer_adds_8_new_features():
    """_engineer_lag_features 후 8 신규 컬럼 모두 존재."""
    df = _make_synthetic_full([20191, 20192, 20193, 20194, 20201, 20202])
    out = _engineer_lag_features(df)

    new_cols = [
        "weekday_sales_yoy",
        "weekend_sales_yoy",
        "age_20_sales_ratio",
        "age_60_sales_ratio",
        "open_close_ratio_lag1",
        "total_pop_yoy",
        "holiday_count",
        "cpi_index_yoy",
    ]
    for col in new_cols:
        assert col in out.columns, f"신규 feature 누락: {col}"


def test_yoy_features_correct_with_lag4():
    """weekday/weekend/total_pop/cpi yoy 가 lag4 기준 정확히 계산."""
    quarters = [20191, 20192, 20193, 20194, 20201, 20202, 20203, 20204]
    df = _make_synthetic_full(quarters, rng_seed=42)
    out = _engineer_lag_features(df).sort_values(["dong_code", "industry_code", "quarter"])

    g = out[(out["dong_code"] == "11440300") & (out["industry_code"] == "I001")].sort_values("quarter")
    if len(g) >= 5:
        row_q5 = g.iloc[4]  # 20201
        row_q1 = g.iloc[0]  # 20191
        expected_yoy = (row_q5["weekday_sales"] - row_q1["weekday_sales"]) / (abs(row_q1["weekday_sales"]) + 1)
        assert abs(row_q5["weekday_sales_yoy"] - expected_yoy) < 1e-6


def test_age_ratio_features_bounded():
    """age_20/60_sales_ratio 가 finite — NaN/Inf 없음."""
    df = _make_synthetic_full([20191, 20192, 20193, 20194])
    out = _engineer_lag_features(df)

    assert out["age_20_sales_ratio"].notna().all()
    assert out["age_60_sales_ratio"].notna().all()
    assert np.isfinite(out["age_20_sales_ratio"]).all()
    assert np.isfinite(out["age_60_sales_ratio"]).all()


def test_open_close_ratio_handles_zero_close():
    """close_count=0 시 division-by-zero 회피 (clip lower=1)."""
    quarters = [20191, 20192]
    df = _make_synthetic_full(quarters)
    df["close_count"] = 0
    df["open_count"] = 3

    out = _engineer_lag_features(df).sort_values(["dong_code", "industry_code", "quarter"])
    g = out[(out["dong_code"] == "11440300") & (out["industry_code"] == "I001")].sort_values("quarter")
    second_row = g.iloc[1]
    assert second_row["open_close_ratio_lag1"] > 0
    assert np.isfinite(second_row["open_close_ratio_lag1"])


def test_LGBM_FEATURES_count_after_b1_rollback():
    """B-1 production rollback 후 LGBM_FEATURES = 15 (D layer baseline).

    B-1 retrain 결과 AUC -0.024 degradation → LGBM_FEATURES 에서 신규 8 제거.
    derivation 코드는 _engineer_lag_features 에 보존 (미래 sprint 활용).
    """
    assert len(LGBM_FEATURES) == 15, f"LGBM_FEATURES 길이 mismatch: {len(LGBM_FEATURES)}"
    # 신규 8 feature 는 LGBM_FEATURES 에 없어야 함 (rollback)
    new_cols = {
        "weekday_sales_yoy",
        "weekend_sales_yoy",
        "age_20_sales_ratio",
        "age_60_sales_ratio",
        "open_close_ratio_lag1",
        "total_pop_yoy",
        "holiday_count",
        "cpi_index_yoy",
    }
    assert new_cols.isdisjoint(set(LGBM_FEATURES))
