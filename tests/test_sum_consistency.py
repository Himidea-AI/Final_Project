# tests/test_sum_consistency.py
"""raking post-processing 단위 테스트 — 5종 sum constraint 보장."""

from __future__ import annotations

import pandas as pd
import pytest

from validation.sum_consistency import (
    SUM_CONSTRAINTS_SALES,
    enforce_sum_consistency,
)


@pytest.fixture
def imperfect_pred() -> pd.DataFrame:
    """sum constraint 가 깨진 샘플 — raking 으로 복원돼야."""
    return pd.DataFrame(
        [
            {
                "monthly_sales": 100,
                "weekday_sales": 60,
                "weekend_sales": 50,  # 합 110 ≠ 100
                "mon_sales": 14,
                "tue_sales": 14,
                "wed_sales": 14,
                "thu_sales": 14,
                "fri_sales": 14,
                "sat_sales": 14,
                "sun_sales": 14,  # 합 98 ≠ 100
                "time_00_06_sales": 16,
                "time_06_11_sales": 16,
                "time_11_14_sales": 16,
                "time_14_17_sales": 16,
                "time_17_21_sales": 16,
                "time_21_24_sales": 16,  # 합 96
                "male_sales": 60,
                "female_sales": 50,  # 합 110
                "age_10_sales": 16,
                "age_20_sales": 16,
                "age_30_sales": 16,
                "age_40_sales": 16,
                "age_50_sales": 16,
                "age_60_above_sales": 16,  # 합 96
            }
        ]
    )


def test_weekday_weekend_sum_equals_monthly(imperfect_pred):
    out = enforce_sum_consistency(imperfect_pred.copy(), SUM_CONSTRAINTS_SALES)
    assert abs(out["weekday_sales"].iloc[0] + out["weekend_sales"].iloc[0] - out["monthly_sales"].iloc[0]) < 1.0


def test_dow_7days_sum_equals_monthly(imperfect_pred):
    out = enforce_sum_consistency(imperfect_pred.copy(), SUM_CONSTRAINTS_SALES)
    dow = ["mon_sales", "tue_sales", "wed_sales", "thu_sales", "fri_sales", "sat_sales", "sun_sales"]
    assert abs(out[dow].sum(axis=1).iloc[0] - out["monthly_sales"].iloc[0]) < 1.0


def test_time_6buckets_sum_equals_monthly(imperfect_pred):
    out = enforce_sum_consistency(imperfect_pred.copy(), SUM_CONSTRAINTS_SALES)
    time_cols = [f"time_{t}_sales" for t in ["00_06", "06_11", "11_14", "14_17", "17_21", "21_24"]]
    assert abs(out[time_cols].sum(axis=1).iloc[0] - out["monthly_sales"].iloc[0]) < 1.0


def test_gender_sum_equals_monthly(imperfect_pred):
    out = enforce_sum_consistency(imperfect_pred.copy(), SUM_CONSTRAINTS_SALES)
    assert abs(out["male_sales"].iloc[0] + out["female_sales"].iloc[0] - out["monthly_sales"].iloc[0]) < 1.0


def test_age_6buckets_sum_equals_monthly(imperfect_pred):
    out = enforce_sum_consistency(imperfect_pred.copy(), SUM_CONSTRAINTS_SALES)
    age_cols = [f"age_{a}_sales" for a in ["10", "20", "30", "40", "50", "60_above"]]
    assert abs(out[age_cols].sum(axis=1).iloc[0] - out["monthly_sales"].iloc[0]) < 1.0


def test_enforce_sum_consistency_idempotent(imperfect_pred):
    """두 번 호출해도 결과 동일 (이미 일관성 보장된 후)."""
    once = enforce_sum_consistency(imperfect_pred.copy(), SUM_CONSTRAINTS_SALES)
    twice = enforce_sum_consistency(once.copy(), SUM_CONSTRAINTS_SALES)
    pd.testing.assert_frame_equal(once, twice, atol=0.01)


def test_zero_sub_sum_does_not_crash():
    """sub_sum = 0 (모든 sub_col 이 0) 인 경우 division-by-zero 방지."""
    df = pd.DataFrame(
        [
            {
                "monthly_sales": 100,
                "weekday_sales": 0,
                "weekend_sales": 0,
                **{f"{d}_sales": 0 for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]},
                **{f"time_{t}_sales": 0 for t in ["00_06", "06_11", "11_14", "14_17", "17_21", "21_24"]},
                "male_sales": 0,
                "female_sales": 0,
                **{f"age_{a}_sales": 0 for a in ["10", "20", "30", "40", "50", "60_above"]},
            }
        ]
    )
    out = enforce_sum_consistency(df, SUM_CONSTRAINTS_SALES)
    # 0 합계는 그대로 유지 (raking 적용 X)
    assert out["weekday_sales"].iloc[0] == 0
