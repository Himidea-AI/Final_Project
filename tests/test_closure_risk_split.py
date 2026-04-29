"""폐업 위험도 모델의 time-based split 검증."""

from __future__ import annotations

import pandas as pd
import pytest

from models.closure_risk.data_prep import _time_based_split


def _make_quarterly_df(n_quarters: int = 20, n_groups: int = 3) -> pd.DataFrame:
    """n_quarters × n_groups 행 데이터 생성 (quarter 컬럼 + 더미 label)."""
    rows = []
    quarters = [
        f"2020Q{(i % 4) + 1}" if i < 4 else f"202{1 + (i - 4) // 4}Q{((i - 4) % 4) + 1}" for i in range(n_quarters)
    ]
    for q in quarters:
        for g in range(n_groups):
            rows.append({"quarter": q, "dong_code": f"d{g}", "industry_code": "x", "label": g % 2})
    return pd.DataFrame(rows)


def test_time_based_split_correct_boundaries():
    """20분기 70/15/15 → train 14Q / val 3Q / test 3Q."""
    df = _make_quarterly_df(n_quarters=20)
    train, val, test = _time_based_split(df, train_ratio=0.70, val_ratio=0.15)

    train_quarters = sorted(train["quarter"].unique())
    val_quarters = sorted(val["quarter"].unique())
    test_quarters = sorted(test["quarter"].unique())

    # 분기 수 검증 (boundary index 가 idx-1 → 정확히 14/3/3)
    assert len(train_quarters) == 14, f"train: {len(train_quarters)}"
    assert len(val_quarters) == 3, f"val: {len(val_quarters)}"
    assert len(test_quarters) == 3, f"test: {len(test_quarters)}"


def test_time_based_split_no_overlap():
    """train/val/test quarter 교집합이 0 이어야 함."""
    df = _make_quarterly_df(n_quarters=20)
    train, val, test = _time_based_split(df)

    train_q = set(train["quarter"].unique())
    val_q = set(val["quarter"].unique())
    test_q = set(test["quarter"].unique())

    assert train_q & val_q == set(), f"train ∩ val: {train_q & val_q}"
    assert val_q & test_q == set(), f"val ∩ test: {val_q & test_q}"
    assert train_q & test_q == set(), f"train ∩ test: {train_q & test_q}"


def test_time_based_split_raises_on_small_data():
    """6분기 → ValueError."""
    df = _make_quarterly_df(n_quarters=6)
    with pytest.raises(ValueError, match="분기 수 부족"):
        _time_based_split(df)


def test_time_based_split_preserves_dong_industry_grouping():
    """같은 (dong, industry) 가 여러 split 에 들어가도 OK (시계열 정상)."""
    df = _make_quarterly_df(n_quarters=20, n_groups=3)
    train, val, test = _time_based_split(df)

    # 같은 dong_code "d0" 가 train, val, test 모두에 존재해야 정상
    assert "d0" in train["dong_code"].values
    assert "d0" in val["dong_code"].values
    assert "d0" in test["dong_code"].values


def test_time_based_split_raises_on_invalid_ratios():
    """train_ratio + val_ratio >= 1.0 → ValueError (test set 비어있음)."""
    df = _make_quarterly_df(n_quarters=20)
    with pytest.raises(ValueError, match="test set 이 비어있음"):
        _time_based_split(df, train_ratio=0.70, val_ratio=0.40)


def test_time_based_split_raises_on_null_quarter():
    """quarter 컬럼에 NaN 포함 → ValueError."""
    df = _make_quarterly_df(n_quarters=20)
    df.loc[0, "quarter"] = None
    with pytest.raises(ValueError, match="null"):
        _time_based_split(df)
