"""B1 데이터 단독 신호 강도 단위 테스트."""

import pandas as pd


def test_subway_quarterly_growth_returns_per_dong_quarter():
    from validation.experiments.emerging_district.b1_signal_strength import (
        compute_subway_quarterly_growth,
    )

    df = pd.DataFrame(
        {
            "dong_code": ["11440660", "11440660"],
            "quarter": [20231, 20232],
            "passenger_count": [10000.0, 12000.0],
        }
    )
    growth = compute_subway_quarterly_growth(df)
    assert abs(growth.iloc[1]["growth"] - 0.20) < 1e-3
