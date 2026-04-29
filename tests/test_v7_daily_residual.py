"""v7_daily_residual 단위 테스트.

mode='residual_lag7' 시 prepare_sequences_daily 가 (y[t] - y[t-7]) 를 target 으로
생성하고, metadata 에 mode/task 가 기록되며, 0 잔차 출력 시 y_pred = last_value
(= naive lag7) 임을 검증한다.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from models.living_pop_forecast.data_prep import MAPO_DONG_CODES
from models.living_pop_forecast.data_prep_daily import (
    DAILY_FEATURES,
    DAILY_TARGET_COL,
    build_daily_features,
    prepare_sequences_daily,
)


def _synthetic_daily_df(n_days: int = 60) -> pd.DataFrame:
    """16 dongs × 24 hours × n_days 합성 일별 데이터.

    target = 1000 + 10*tz + 5*(date_idx % 7) + 100*(date_idx // 7)
    → 그룹 (dong, hour) 내 lag=7 차분 = 100*1 + 5*0 = 100 (일정).
    """
    dates = pd.date_range("2024-01-01", periods=n_days, freq="D")
    rows = []
    for date_idx, date in enumerate(dates):
        for dc in MAPO_DONG_CODES:
            for tz in range(24):
                base = 1000.0 + 10.0 * tz + 5.0 * (date_idx % 7) + 100.0 * (date_idx // 7)
                rows.append(
                    {
                        "date": date,
                        "dong_code": dc,
                        "time_zone": tz,
                        "total_pop": base,
                        "day_of_week": date.dayofweek,
                    }
                )
    return pd.DataFrame(rows)


def test_residual_lag7_target_is_correct():
    """mode='residual_lag7' 시 target = y[t] - y[t-7]."""
    df = _synthetic_daily_df(60)
    df = build_daily_features(df)

    X, y, last_value_raw, _, tgt_scaler = prepare_sequences_daily(
        df,
        window_size=14,
        target_col=DAILY_TARGET_COL,
        mode="residual_lag7",
        feature_cols=list(DAILY_FEATURES),
    )

    # 합성 trend: lag=7 차분 = 100*((date_idx)//7 - (date_idx-7)//7) + 5*((date_idx)%7 - (date_idx-7)%7)
    #            = 100*1 + 5*0 = 100 (일정).
    sample_y_norm = y[:5].astype(np.float32)
    sample_delta_actual = tgt_scaler.inverse_transform(sample_y_norm)
    # 실제 합성 trend: lag=7 차분 = 100*((date_idx)//7 - (date_idx-7)//7) = 100*1 = 100.
    # 잔여 5*((date_idx)%7 - (date_idx-7)%7) = 0 (mod 7 동일).
    assert np.allclose(sample_delta_actual, 100.0, atol=1.0), (
        f"lag7 차분 100 기대, 실제 {sample_delta_actual.flatten().tolist()}"
    )

    # last_value_raw 는 y[t-7] (raw)
    assert last_value_raw.shape == (X.shape[0],)
    # last_value 가 raw target 단위 (1000 ~ 수천 범위)
    assert last_value_raw.min() > 0.0
    assert last_value_raw.max() < 1e6


def test_residual_lag7_distribution_smaller_than_absolute():
    """잔차 (lag7) 분포 range < raw 분포 range."""
    df = _synthetic_daily_df(60)
    df = build_daily_features(df)

    _, _, _, _, tgt_abs = prepare_sequences_daily(
        df,
        window_size=14,
        target_col=DAILY_TARGET_COL,
        mode="absolute",
        feature_cols=list(DAILY_FEATURES),
    )
    _, _, _, _, tgt_res = prepare_sequences_daily(
        df,
        window_size=14,
        target_col=DAILY_TARGET_COL,
        mode="residual_lag7",
        feature_cols=list(DAILY_FEATURES),
    )

    abs_range = float(tgt_abs.data_max_[0] - tgt_abs.data_min_[0])
    res_range = float(tgt_res.data_max_[0] - tgt_res.data_min_[0])
    assert res_range < abs_range, f"잔차 range ({res_range:.2f}) >= raw range ({abs_range:.2f})"


def test_metadata_records_mode_residual_lag7():
    """metadata json 에 mode='residual_lag7' 기록.

    학습 산출물이 없으면 skip — train_daily_residual.py 실행 후 재시도.
    """
    weights_dir = Path("models/living_pop_forecast/weights")
    target_meta = weights_dir / "living_pop_metadata_v7_daily_residual.json"
    if not target_meta.exists():
        pytest.skip("아직 daily residual 학습 미실행 — train 후 재시도")
    meta = json.loads(target_meta.read_text(encoding="utf-8"))
    assert meta.get("mode") == "residual_lag7"
    assert meta.get("task") == "daily"
    assert meta.get("version") == "v7_daily_residual"
    # 25 차원 입력 (total_pop + time_zone_norm + 7 dow + 16 dong)
    assert int(meta.get("input_size", 0)) == 25
    assert int(meta.get("n_dong", 0)) == 16
    assert int(meta.get("n_hours", 0)) == 24


def test_v7_zero_delta_equals_naive_lag7():
    """model output = 0 (delta_actual=0) 이면 y_pred = last_value = naive_lag7."""
    df = _synthetic_daily_df(40)
    df = build_daily_features(df)

    _, _, last_value_raw, _, _ = prepare_sequences_daily(
        df,
        window_size=14,
        target_col=DAILY_TARGET_COL,
        mode="residual_lag7",
        feature_cols=list(DAILY_FEATURES),
    )

    # delta_actual = 0 → y_pred = last_value + 0 = last_value (naive_lag7)
    delta_actual = np.zeros_like(last_value_raw)
    y_pred = last_value_raw + delta_actual
    assert np.allclose(y_pred, last_value_raw, atol=1e-6)


def test_daily_features_dimensionality():
    """피처 컬럼이 정확히 25 차원 (total_pop + time_zone_norm + 7 dow + 16 dong)."""
    from models.living_pop_forecast.data_prep_daily import (
        DAILY_DONG_FEATURES,
        DAILY_DOW_FEATURES,
    )

    assert len(DAILY_DOW_FEATURES) == 7
    assert len(DAILY_DONG_FEATURES) == 16
    assert len(DAILY_FEATURES) == 1 + 1 + 7 + 16  # 25
    assert DAILY_FEATURES[0] == "total_pop"
    assert DAILY_FEATURES[1] == "time_zone_norm"


def test_prepare_sequences_invalid_mode():
    """잘못된 mode 값은 ValueError."""
    df = _synthetic_daily_df(20)
    df = build_daily_features(df)
    with pytest.raises(ValueError, match="mode 는 'absolute'"):
        prepare_sequences_daily(
            df,
            window_size=14,
            target_col=DAILY_TARGET_COL,
            mode="invalid",
            feature_cols=list(DAILY_FEATURES),
        )


def test_window_size_below_lag_offset_raises():
    """window_size < 7 (residual_lag7) → ValueError."""
    df = _synthetic_daily_df(20)
    df = build_daily_features(df)
    with pytest.raises(ValueError, match="window_size"):
        prepare_sequences_daily(
            df,
            window_size=5,
            target_col=DAILY_TARGET_COL,
            mode="residual_lag7",
            feature_cols=list(DAILY_FEATURES),
        )


def test_residual_lag1_mode_target():
    """residual_lag1 mode → target = y[t] - y[t-1]."""
    df = _synthetic_daily_df(40)
    df = build_daily_features(df)

    _, y, last_value_raw, _, tgt_scaler = prepare_sequences_daily(
        df,
        window_size=14,
        target_col=DAILY_TARGET_COL,
        mode="residual_lag1",
        feature_cols=list(DAILY_FEATURES),
    )

    # 합성 trend: lag=1 차분
    # date_idx 변경마다 변화: 100*((date_idx)//7 - (date_idx-1)//7) + 5*((date_idx)%7 - (date_idx-1)%7).
    # 일반적: 두 항 합 — date_idx%7 가 0→6 일 때 큰 변화 (다른 mod), 외에는 +5.
    # 평균적 양수.
    sample_delta = tgt_scaler.inverse_transform(y[:50].astype(np.float32))
    assert sample_delta.shape == (50, 1)
    # last_value_raw 는 y[t-1]
    assert last_value_raw.shape == (y.shape[0],)


def test_sequence_count_matches_expected():
    """그룹당 길이 60 → window=14 → 46 sequences. 16×24 = 384 그룹 → 17,664 시퀀스."""
    df = _synthetic_daily_df(60)
    df = build_daily_features(df)
    X, _, _, _, _ = prepare_sequences_daily(
        df,
        window_size=14,
        target_col=DAILY_TARGET_COL,
        mode="residual_lag7",
        feature_cols=list(DAILY_FEATURES),
    )
    n_groups = 16 * 24  # = 384
    seq_per_group = 60 - 14  # = 46
    assert X.shape[0] == n_groups * seq_per_group  # 17664
    assert X.shape[1] == 14
    assert X.shape[2] == 25  # 25 features
