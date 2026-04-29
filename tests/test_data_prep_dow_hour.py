"""data_prep_dow_hour 단위 테스트."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from models.living_pop_forecast.data_prep import MAPO_DONG_CODES
from models.living_pop_forecast.data_prep_dow_hour import (
    build_dow_hour_aggregation,
    load_living_population_raw,
)


def _synthetic_raw() -> pd.DataFrame:
    """16동 × 2분기 (2024Q1 + 2024Q2) × 7요일 × 24시간 × 일별 raw."""
    dates_q1 = pd.date_range("2024-01-01", "2024-03-31", freq="D")
    dates_q2 = pd.date_range("2024-04-01", "2024-06-30", freq="D")
    dates = list(dates_q1) + list(dates_q2)

    rows = []
    rng = np.random.default_rng(42)
    for date in dates:
        for dong in MAPO_DONG_CODES:
            for tz in range(24):
                pop = float(rng.uniform(1000, 50000))
                rows.append(
                    {
                        "date": date,
                        "dong_code": dong,
                        "time_zone": tz,
                        "total_pop": pop,
                        "day_of_week": date.dayofweek,
                        "quarter": date.year * 10 + ((date.month - 1) // 3 + 1),
                    }
                )
    return pd.DataFrame(rows)


def test_aggregation_row_count():
    """16 dongs × 7 dow × 24 hours × n_quarters = 합계 row 수."""
    raw = _synthetic_raw()
    agg = build_dow_hour_aggregation(raw)
    n_q = raw["quarter"].nunique()
    expected = 16 * 7 * 24 * n_q
    assert len(agg) == expected


def test_quarter_format():
    """quarter = year*10 + Q (예: 20241)."""
    raw = _synthetic_raw()
    agg = build_dow_hour_aggregation(raw)
    qs = sorted(agg["quarter"].unique().tolist())
    assert qs == [20241, 20242]
    # 20241 = 2024 * 10 + 1
    assert qs[0] // 10 == 2024
    assert qs[0] % 10 == 1


def test_day_of_week_range():
    """day_of_week 가 0~6 범위."""
    raw = _synthetic_raw()
    agg = build_dow_hour_aggregation(raw)
    assert agg["day_of_week"].min() == 0
    assert agg["day_of_week"].max() == 6
    assert set(agg["day_of_week"].unique().tolist()) == set(range(7))


def test_no_missing_groups_after_fillna():
    """결측 그룹 fillna/interpolate 후 NaN 0개."""
    raw = _synthetic_raw()
    # 일부 (dong, dow, hour, quarter) 조합 강제 누락
    drop_mask = (raw["dong_code"] == "11440555") & (raw["time_zone"] == 5) & (raw["day_of_week"] == 3)
    raw_partial = raw[~drop_mask].copy()
    agg = build_dow_hour_aggregation(raw_partial)
    assert agg["mean_pop"].isna().sum() == 0
    # full grid 유지
    n_q = raw_partial["quarter"].nunique()
    assert len(agg) == 16 * 7 * 24 * n_q


def test_time_zone_range():
    """time_zone 0~23."""
    raw = _synthetic_raw()
    agg = build_dow_hour_aggregation(raw)
    assert agg["time_zone"].min() == 0
    assert agg["time_zone"].max() == 23
    assert set(agg["time_zone"].unique().tolist()) == set(range(24))


def test_dong_codes_mapo_only():
    """16 마포동만."""
    raw = _synthetic_raw()
    agg = build_dow_hour_aggregation(raw)
    assert set(agg["dong_code"].unique().tolist()) == set(MAPO_DONG_CODES)


def test_load_living_population_raw_missing_path(tmp_path):
    """존재하지 않는 path → FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_living_population_raw(tmp_path / "missing.csv")
