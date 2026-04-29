"""C 모델 baseline 단위 테스트."""

import pandas as pd


def test_group_mean_baseline_returns_dong_industry_average():
    from validation.experiments.customer_revenue.baseline_c import group_mean_baseline

    df = pd.DataFrame(
        {
            "dong_code": ["11440660"] * 4 + ["11440555"] * 2,
            "industry_code": ["CS100001"] * 4 + ["CS100001"] * 2,
            "quarter": [20231, 20232, 20233, 20234, 20231, 20232],
            "age_30_ratio": [0.3, 0.4, 0.5, 0.4, 0.2, 0.3],
        }
    )
    result = group_mean_baseline(df, segment_cols=["age_30_ratio"])
    val = result.loc[("11440660", "CS100001"), "age_30_ratio"]
    assert abs(val - 0.4) < 1e-6


def test_global_mean_baseline_ignores_dong_industry():
    from validation.experiments.customer_revenue.baseline_c import global_mean_baseline

    df = pd.DataFrame(
        {
            "dong_code": ["11440660", "11440555"],
            "industry_code": ["CS100001", "CS100001"],
            "age_30_ratio": [0.5, 0.3],
        }
    )
    result = global_mean_baseline(df, segment_cols=["age_30_ratio"])
    assert abs(result["age_30_ratio"] - 0.4) < 1e-6
