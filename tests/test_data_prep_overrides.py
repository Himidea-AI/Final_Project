"""data_prep.load_sales_data / prepare_dataloaders 의 sales_csv_override 동작 테스트."""

from __future__ import annotations

import pandas as pd
import pytest

from models.lstm_forecast import data_prep as dp
from models.lstm_forecast.data_prep import load_sales_data, prepare_dataloaders


def test_sales_csv_override_takes_precedence(tmp_path):
    """sales_csv_override 가 주어지면 DB를 시도하지 않고 CSV를 직접 읽어야 한다."""
    csv = tmp_path / "override.csv"
    pd.DataFrame(
        {
            "quarter": [20191],
            "dong_code": ["11440555"],
            "dong_name": ["서교동"],
            "industry_code": ["CS100001"],
            "industry_name": ["한식"],
            "monthly_sales": [1.0e9],
        }
    ).to_csv(csv, index=False, encoding="utf-8-sig")

    # DB URL을 일부러 잘못된 값으로 — override가 동작하면 DB를 안 건드려야 함
    df = load_sales_data(
        db_url="postgresql://invalid:invalid@localhost:1/nonexistent",
        sales_csv_override=str(csv),
        dong_prefix="11440",
    )
    assert len(df) == 1
    assert df.iloc[0]["monthly_sales"] == pytest.approx(1.0e9)


def test_prepare_dataloaders_passes_override_through(tmp_path, monkeypatch):
    """config['sales_csv_override']가 load_sales_data까지 전달되어야 한다."""
    captured = {}

    real_load = dp.load_sales_data

    def spy(*args, **kwargs):
        captured["sales_csv_override"] = kwargs.get("sales_csv_override")
        return real_load(*args, **kwargs)

    monkeypatch.setattr(dp, "load_sales_data", spy)

    csv = tmp_path / "stub.csv"
    pd.DataFrame(
        {
            "quarter": [20191] * 8 + [20192] * 8 + [20193] * 8 + [20194] * 8 + [20201] * 8,
            "dong_code": ["11440555"] * 40,
            "dong_name": ["서교동"] * 40,
            "industry_code": ["CS100001"] * 40,
            "industry_name": ["한식"] * 40,
            "monthly_sales": list(range(1_000_000_000, 1_000_000_000 + 40 * 1_000_000, 1_000_000)),
        }
    ).to_csv(csv, index=False, encoding="utf-8-sig")

    cfg = {
        "db_url": "postgresql://invalid:invalid@localhost:1/x",
        "dong_prefix": "11440",
        "window_size": 4,
        "batch_size": 4,
        "val_ratio": 0.2,
        "target_col": "monthly_sales",
        "feature_cols": ["monthly_sales"],
        "sales_csv_override": str(csv),
    }
    exc_from_pipeline: Exception | None = None
    try:
        prepare_dataloaders(cfg)
    except Exception as e:
        exc_from_pipeline = e  # store_df/build_timeseries 등 후속 단계 실패는 허용
    assert captured.get("sales_csv_override") == str(csv), (
        f"override가 load_sales_data까지 전달되지 않음 (pipeline 예외: {exc_from_pipeline!r})"
    )


def test_train_cutoff_quarter_filters_recent_data(tmp_path):
    """train_cutoff_quarter=20241 이면 quarter >= 20241 row가 학습 데이터에서 제외되어야 한다."""
    csv = tmp_path / "stub.csv"
    quarters = [
        20191,
        20192,
        20193,
        20194,
        20201,
        20202,
        20203,
        20204,
        20211,
        20212,
        20213,
        20214,
        20221,
        20222,
        20223,
        20224,
        20231,
        20232,
        20233,
        20234,
        20241,
        20242,
        20243,
        20244,
    ]
    pd.DataFrame(
        {
            "quarter": quarters,
            "dong_code": ["11440555"] * len(quarters),
            "dong_name": ["서교동"] * len(quarters),
            "industry_code": ["CS100001"] * len(quarters),
            "industry_name": ["한식"] * len(quarters),
            "monthly_sales": [1.0e9 + i * 1e7 for i in range(len(quarters))],
        }
    ).to_csv(csv, index=False, encoding="utf-8-sig")

    from models.lstm_forecast import data_prep as dp

    captured = {}
    real_build = dp.build_timeseries

    def spy(sales_df, *args, **kwargs):
        captured["max_quarter"] = sales_df["quarter"].max()
        return real_build(sales_df, *args, **kwargs)

    import pytest as _pt

    with _pt.MonkeyPatch.context() as m:
        m.setattr(dp, "build_timeseries", spy)
        cfg = {
            "db_url": "postgresql://invalid:invalid@localhost:1/x",
            "dong_prefix": "11440",
            "window_size": 4,
            "batch_size": 4,
            "val_ratio": 0.2,
            "target_col": "monthly_sales",
            "feature_cols": ["monthly_sales"],
            "sales_csv_override": str(csv),
            "train_cutoff_quarter": 20241,
        }
        try:
            dp.prepare_dataloaders(cfg)
        except Exception:
            pass
    assert captured.get("max_quarter") is not None
    assert captured["max_quarter"] < 20241, f"cutoff 후 max_quarter={captured['max_quarter']}"
