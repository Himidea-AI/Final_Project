"""data_prep_daily 단위 테스트."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from models.living_pop_forecast.data_prep import MAPO_DONG_CODES
from models.living_pop_forecast.data_prep_daily import (
    build_daily_aggregation,
    load_living_pop_daily_raw,
    split_time_order_per_group,
)


def _synthetic_raw(n_days: int = 30) -> pd.DataFrame:
    """16동 × n_days × 24시간 일별 raw."""
    dates = pd.date_range("2024-01-01", periods=n_days, freq="D")
    rows = []
    rng = np.random.default_rng(42)
    for date in dates:
        for dong in MAPO_DONG_CODES:
            for tz in range(24):
                rows.append(
                    {
                        "date": date,
                        "dong_code": dong,
                        "time_zone": tz,
                        "total_pop": float(rng.uniform(1000, 50000)),
                        "day_of_week": date.dayofweek,
                    }
                )
    return pd.DataFrame(rows)


def test_aggregation_row_count():
    """일별 aggregation row 수 = 16 × 24 × n_days."""
    n_days = 14
    raw = _synthetic_raw(n_days)
    agg = build_daily_aggregation(raw)
    assert len(agg) == 16 * 24 * n_days


def test_no_missing_after_fill():
    """결측 그룹 fillna/interpolate 후 NaN 0개."""
    raw = _synthetic_raw(20)
    drop_mask = (raw["dong_code"] == "11440555") & (raw["time_zone"] == 5) & (raw["date"] == raw["date"].iloc[100])
    raw_partial = raw[~drop_mask].copy()
    agg = build_daily_aggregation(raw_partial)
    assert agg["total_pop"].isna().sum() == 0
    n_days = raw_partial["date"].nunique()
    assert len(agg) == 16 * 24 * n_days


def test_dong_codes_mapo_only():
    """16 마포동만."""
    raw = _synthetic_raw(7)
    agg = build_daily_aggregation(raw)
    assert set(agg["dong_code"].unique().tolist()) == set(MAPO_DONG_CODES)


def test_time_zone_range():
    """time_zone 0~23."""
    raw = _synthetic_raw(7)
    agg = build_daily_aggregation(raw)
    assert agg["time_zone"].min() == 0
    assert agg["time_zone"].max() == 23
    assert set(int(x) for x in agg["time_zone"].unique()) == set(range(24))


def test_day_of_week_correct():
    """date → day_of_week 변환 정확성 (2024-01-01 = 월요일 = 0)."""
    raw = _synthetic_raw(7)
    agg = build_daily_aggregation(raw)
    jan1 = agg[pd.to_datetime(agg["date"]) == pd.Timestamp("2024-01-01")]
    assert (jan1["day_of_week"] == 0).all()  # 월요일
    jan7 = agg[pd.to_datetime(agg["date"]) == pd.Timestamp("2024-01-07")]
    assert (jan7["day_of_week"] == 6).all()  # 일요일


def test_time_order_split_per_group():
    """각 그룹의 train.max_date < val.min_date < test.min_date."""
    raw = _synthetic_raw(100)
    agg = build_daily_aggregation(raw)
    train, val, test = split_time_order_per_group(agg, train_ratio=0.70, val_ratio=0.15)

    for (dong, tz), _ in agg.groupby(["dong_code", "time_zone"]):
        t_g = train[(train["dong_code"] == dong) & (train["time_zone"] == tz)]
        v_g = val[(val["dong_code"] == dong) & (val["time_zone"] == tz)]
        s_g = test[(test["dong_code"] == dong) & (test["time_zone"] == tz)]
        assert not t_g.empty and not v_g.empty and not s_g.empty
        assert pd.to_datetime(t_g["date"]).max() < pd.to_datetime(v_g["date"]).min()
        assert pd.to_datetime(v_g["date"]).max() < pd.to_datetime(s_g["date"]).min()


def test_no_data_leakage():
    """test split 의 모든 date 가 train+val 의 max date 이후 (그룹 내 시간순 보장)."""
    raw = _synthetic_raw(50)
    agg = build_daily_aggregation(raw)
    train, val, test = split_time_order_per_group(agg, train_ratio=0.70, val_ratio=0.15)
    for (dong, tz), _ in agg.groupby(["dong_code", "time_zone"]):
        t_g = train[(train["dong_code"] == dong) & (train["time_zone"] == tz)]
        s_g = test[(test["dong_code"] == dong) & (test["time_zone"] == tz)]
        if t_g.empty or s_g.empty:
            continue
        assert pd.to_datetime(t_g["date"]).max() < pd.to_datetime(s_g["date"]).min()
        # 교집합 0
        common = set(pd.to_datetime(t_g["date"])) & set(pd.to_datetime(s_g["date"]))
        assert not common


def test_split_ratios_approximate():
    """split 비율이 대략 70/15/15 인지 (그룹 내)."""
    raw = _synthetic_raw(100)
    agg = build_daily_aggregation(raw)
    train, val, test = split_time_order_per_group(agg, train_ratio=0.70, val_ratio=0.15)
    total = len(agg)
    assert 0.65 * total < len(train) < 0.75 * total
    assert 0.10 * total < len(val) < 0.20 * total
    assert 0.10 * total < len(test) < 0.20 * total


def test_load_living_pop_daily_raw_missing_path(tmp_path):
    """존재하지 않는 path → FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_living_pop_daily_raw(tmp_path / "missing.csv")
