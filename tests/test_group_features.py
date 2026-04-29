"""Group-aware features 단위 테스트 — Plan Task 3.

build_timeseries(add_group_features=True, train_end_quarter=...) 가
group_mean / group_relative 컬럼을 추가하고 leakage 가 없는지 검증.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def _make_synthetic_df() -> pd.DataFrame:
    """16동 × 24시간대 × 12분기 합성 데이터.

    분기 id: 20191..20264 (1~4 quarter, 6년치) — 실제 raw quarter 와 동일 구조.
    target = 1000 + 100*qi + 10*tz + offset_per_dong (그룹별 평균이 차이나야 group features 의미).
    """
    from models.living_pop_forecast.data_prep import MAPO_DONG_CODES

    rows = []
    quarters = []
    for year in range(2019, 2025):
        for q in range(1, 5):
            quarters.append(year * 10 + q)
    for di, dc in enumerate(MAPO_DONG_CODES):
        for tz in range(24):
            for qi, quarter in enumerate(quarters):
                base = 1000.0 + 100.0 * qi + 10.0 * tz + 50.0 * di
                rows.append(
                    {
                        "quarter": quarter,
                        "dong_code": dc,
                        "dong_name": f"d_{dc}",
                        "time_zone": tz,
                        "total_avg_pop": base,
                        "weekday_avg_pop": base * 1.05,
                        "weekend_avg_pop": base * 0.95,
                    }
                )
    return pd.DataFrame(rows)


def test_group_features_columns_added():
    """add_group_features=True 시 group_mean / group_relative 컬럼 존재."""
    from models.living_pop_forecast.data_prep import build_timeseries

    df = _make_synthetic_df()
    out = build_timeseries(df, add_group_features=True, train_end_quarter=20214)
    assert "group_mean" in out.columns
    assert "group_relative" in out.columns
    # default off 면 없음
    out_off = build_timeseries(df.copy())
    assert "group_mean" not in out_off.columns
    assert "group_relative" not in out_off.columns


def test_group_mean_no_leakage():
    """group_mean 계산이 train_end_quarter 이하 데이터로만 사용되는지.

    test 분기 (20221+) row 의 group_mean 이 train 분기 (20191~20214) 평균과 일치해야 함.
    """
    from models.living_pop_forecast.data_prep import build_timeseries

    df = _make_synthetic_df()
    train_end = 20214
    out = build_timeseries(df, add_group_features=True, train_end_quarter=train_end)

    # 직접 train 분기 평균 계산 (raw df 에서)
    train_only = df[df["quarter"] <= train_end]
    expected = train_only.groupby(["dong_code", "time_zone"])["total_avg_pop"].mean()

    # test 분기 (20221+) 의 group_mean 가 train 평균과 일치하는지 sample 검증
    test_rows = out[out["quarter"] > train_end]
    assert len(test_rows) > 0, "test 분기 row 가 있어야 함"

    sampled = test_rows.sample(min(50, len(test_rows)), random_state=0)
    for _, row in sampled.iterrows():
        key = (row["dong_code"], row["time_zone"])
        assert abs(row["group_mean"] - float(expected[key])) < 1e-3, (
            f"leakage 의심: {key} group_mean={row['group_mean']} expected={float(expected[key])}"
        )


def test_group_mean_full_data_when_no_cutoff():
    """train_end_quarter=None 이면 전체 데이터로 group_mean 계산 (legacy)."""
    from models.living_pop_forecast.data_prep import build_timeseries

    df = _make_synthetic_df()
    out = build_timeseries(df, add_group_features=True, train_end_quarter=None)

    expected = df.groupby(["dong_code", "time_zone"])["total_avg_pop"].mean()

    sampled = out.sample(50, random_state=0)
    for _, row in sampled.iterrows():
        key = (row["dong_code"], row["time_zone"])
        assert abs(row["group_mean"] - float(expected[key])) < 1e-3


def test_group_relative_zero_when_at_mean():
    """group_relative = (y - group_mean) / group_mean. y == group_mean 인 row 에서 0."""
    from models.living_pop_forecast.data_prep import build_timeseries

    df = _make_synthetic_df()
    out = build_timeseries(df, add_group_features=True, train_end_quarter=None)

    # 정의 식 그대로 검증 (모든 row 에서)
    reconstructed = (out["total_avg_pop"] - out["group_mean"]) / out["group_mean"]
    np.testing.assert_allclose(out["group_relative"].values, reconstructed.values, rtol=1e-6)


def test_group_features_in_pop_features_v5():
    """POP_FEATURES_GROUP_RESIDUAL 가 group_mean, group_relative 포함."""
    from models.living_pop_forecast.data_prep import POP_FEATURES_GROUP_RESIDUAL

    assert "group_mean" in POP_FEATURES_GROUP_RESIDUAL
    assert "group_relative" in POP_FEATURES_GROUP_RESIDUAL
    # v2 5 features + 2 new = 7
    assert len(POP_FEATURES_GROUP_RESIDUAL) == 7
    # 기존 v2 피처도 포함
    for f in ("total_avg_pop", "weekday_avg_pop", "weekend_avg_pop", "time_zone_norm", "quarter_num"):
        assert f in POP_FEATURES_GROUP_RESIDUAL


def test_build_timeseries_backward_compat():
    """build_timeseries(df) 단일 인자 호출 시 group features 없음 (legacy 동작)."""
    from models.living_pop_forecast.data_prep import build_timeseries

    df = _make_synthetic_df()
    out = build_timeseries(df)
    assert "group_mean" not in out.columns
    assert "group_relative" not in out.columns
    # v2 production 피처는 여전히 있어야 함
    assert "time_zone_norm" in out.columns
    assert "quarter_num" in out.columns


def test_train_end_quarter_empty_raises():
    """train_end_quarter 이 모든 분기 미만이면 ValueError."""
    from models.living_pop_forecast.data_prep import build_timeseries

    df = _make_synthetic_df()
    with pytest.raises(ValueError, match="train_end_quarter"):
        build_timeseries(df, add_group_features=True, train_end_quarter=20180)


def test_v5_metadata_records_group_features():
    """v5_group_residual 학습 산출물 metadata 가 add_group_features=True 와 train_end_quarter 기록."""
    weights_dir = Path("models/living_pop_forecast/weights")
    target_meta = weights_dir / "living_pop_metadata_v5_group_residual.json"
    if not target_meta.exists():
        pytest.skip("아직 v5_group_residual 학습 미실행 — train 후 재시도")
    meta = json.loads(target_meta.read_text(encoding="utf-8"))
    assert meta.get("mode") == "residual"
    assert meta.get("version") == "v5_group_residual"
    assert meta.get("add_group_features") is True
    assert meta.get("train_end_quarter") is not None
    feats = meta.get("feature_columns", [])
    assert "group_mean" in feats
    assert "group_relative" in feats
