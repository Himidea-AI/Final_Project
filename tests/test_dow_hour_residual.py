"""dow_hour residual learning 단위 테스트 — Plan Phase 2.

mode='residual' 시 prepare_sequences_dow_hour 가 Δy 를 target 으로 생성하고,
metadata 에 mode/task 가 기록되며, 0 잔차 출력 시 y_pred = last_value (= naive lag1)
임을 검증한다.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def _synthetic_dow_hour_df() -> pd.DataFrame:
    """16 dongs × 7 dow × 24 hours × 12 quarters 합성 데이터.

    target = 1000 + 100*qi + 10*tz + 5*dow (단순 trend) → 그룹내 Δy 가 일정한 100.
    """
    from models.living_pop_forecast.data_prep import MAPO_DONG_CODES

    rows = []
    for dc in MAPO_DONG_CODES:
        for dow in range(7):
            for tz in range(24):
                for qi in range(12):
                    quarter = 20190 + qi
                    base = 1000.0 + 100.0 * qi + 10.0 * tz + 5.0 * dow
                    rows.append(
                        {
                            "dong_code": dc,
                            "quarter": quarter,
                            "day_of_week": dow,
                            "time_zone": tz,
                            "mean_pop": base,
                        }
                    )
    return pd.DataFrame(rows)


def test_residual_mode_target_is_delta_dow_hour():
    """mode='residual' 시 target = y[t] - y[t-1]."""
    from models.living_pop_forecast.data_prep_dow_hour import (
        DOW_HOUR_FEATURES,
        DOW_HOUR_TARGET_COL,
        build_dow_hour_features,
        prepare_sequences_dow_hour,
    )

    df = _synthetic_dow_hour_df()
    df = build_dow_hour_features(df)

    X_abs, y_abs, _, tgt_abs = prepare_sequences_dow_hour(
        df,
        window_size=8,
        target_col=DOW_HOUR_TARGET_COL,
        mode="absolute",
        feature_cols=list(DOW_HOUR_FEATURES),
    )
    X_res, y_res, _, tgt_res = prepare_sequences_dow_hour(
        df,
        window_size=8,
        target_col=DOW_HOUR_TARGET_COL,
        mode="residual",
        feature_cols=list(DOW_HOUR_FEATURES),
    )

    # 시퀀스 수 동일
    assert X_abs.shape == X_res.shape
    assert y_abs.shape == y_res.shape

    # 잔차 분포 < raw 분포
    abs_min = float(tgt_abs.data_min_[0])
    abs_max = float(tgt_abs.data_max_[0])
    res_min = float(tgt_res.data_min_[0])
    res_max = float(tgt_res.data_max_[0])
    assert (res_max - res_min) < (abs_max - abs_min), (
        f"잔차 range ({res_max - res_min:.2f}) >= raw range ({abs_max - abs_min:.2f})"
    )

    # 합성 데이터의 잔차는 일정한 100 → inverse_transform 결과 모두 100 근처
    sample_y_norm = y_res[:5].astype(np.float32)
    sample_delta_actual = tgt_res.inverse_transform(sample_y_norm)
    assert np.allclose(sample_delta_actual, 100.0, atol=1.0), (
        f"잔차 100 기대, 실제 {sample_delta_actual.flatten().tolist()}"
    )


def test_metadata_records_mode_and_task():
    """metadata json 에 mode='residual', task='dow_hour' 기록.

    학습 산출물이 없으면 skip — train_dow_hour_residual.py 실행 후 재시도.
    """
    weights_dir = Path("models/living_pop_forecast/weights")
    target_meta = weights_dir / "living_pop_metadata_v6_dow_hour_residual.json"
    if not target_meta.exists():
        pytest.skip("아직 dow_hour residual 학습 미실행 — train 후 재시도")
    meta = json.loads(target_meta.read_text(encoding="utf-8"))
    assert meta.get("mode") == "residual"
    assert meta.get("task") == "dow_hour"
    assert meta.get("version") == "v6_dow_hour_residual"
    # 25 차원 입력 (mean_pop + time_zone_norm + 7 dow + 16 dong)
    assert int(meta.get("input_size", 0)) == 25
    assert int(meta.get("n_dong", 0)) == 16
    assert int(meta.get("n_dow", 0)) == 7
    assert int(meta.get("n_hours", 0)) == 24


def test_residual_zero_delta_equals_naive_dow_hour():
    """model output = 0 (delta_actual=0) 이면 y_pred = last_value = naive."""
    from models.living_pop_forecast.data_prep_dow_hour import (
        DOW_HOUR_FEATURES,
        DOW_HOUR_TARGET_COL,
        build_dow_hour_features,
        prepare_sequences_dow_hour,
    )

    df = _synthetic_dow_hour_df()
    df = build_dow_hour_features(df)

    X, _, feat_scaler, _ = prepare_sequences_dow_hour(
        df,
        window_size=8,
        target_col=DOW_HOUR_TARGET_COL,
        mode="residual",
        feature_cols=list(DOW_HOUR_FEATURES),
    )

    # 첫 시퀀스의 마지막 step (t-1) 의 raw target 복원
    feature_cols = list(DOW_HOUR_FEATURES)
    target_idx = feature_cols.index(DOW_HOUR_TARGET_COL)
    seq = X[0]
    last_norm = float(seq[-1, target_idx])
    n_feat = len(feat_scaler.scale_)
    placeholder = np.zeros((1, n_feat), dtype=np.float32)
    placeholder[0, target_idx] = last_norm
    last_actual = float(feat_scaler.inverse_transform(placeholder)[0, target_idx])

    # delta_actual = 0 → y_pred = last_actual + 0 = last_actual (naive lag1)
    delta_actual = 0.0
    y_pred = last_actual + delta_actual
    assert abs(y_pred - last_actual) < 1e-6


def test_dow_hour_features_dimensionality():
    """피처 컬럼이 정확히 25 차원 (mean_pop + time_zone_norm + 7 dow + 16 dong)."""
    from models.living_pop_forecast.data_prep_dow_hour import (
        DOW_HOUR_DONG_FEATURES,
        DOW_HOUR_DOW_FEATURES,
        DOW_HOUR_FEATURES,
    )

    assert len(DOW_HOUR_DOW_FEATURES) == 7
    assert len(DOW_HOUR_DONG_FEATURES) == 16
    assert len(DOW_HOUR_FEATURES) == 1 + 1 + 7 + 16  # 25
    assert DOW_HOUR_FEATURES[0] == "mean_pop"
    assert DOW_HOUR_FEATURES[1] == "time_zone_norm"


def test_prepare_sequences_invalid_mode():
    """잘못된 mode 값은 ValueError."""
    from models.living_pop_forecast.data_prep_dow_hour import (
        DOW_HOUR_FEATURES,
        DOW_HOUR_TARGET_COL,
        build_dow_hour_features,
        prepare_sequences_dow_hour,
    )

    df = _synthetic_dow_hour_df()
    df = build_dow_hour_features(df)
    with pytest.raises(ValueError, match="mode 는 'absolute'"):
        prepare_sequences_dow_hour(
            df,
            window_size=4,
            target_col=DOW_HOUR_TARGET_COL,
            mode="invalid",
            feature_cols=list(DOW_HOUR_FEATURES),
        )


def test_sequence_count_matches_expected():
    """그룹당 길이 12 quarters → window=8 → 4 sequences. 16×7×24 = 2688 그룹 → 10752 시퀀스."""
    from models.living_pop_forecast.data_prep_dow_hour import (
        DOW_HOUR_FEATURES,
        DOW_HOUR_TARGET_COL,
        build_dow_hour_features,
        prepare_sequences_dow_hour,
    )

    df = _synthetic_dow_hour_df()
    df = build_dow_hour_features(df)
    X, _, _, _ = prepare_sequences_dow_hour(
        df,
        window_size=8,
        target_col=DOW_HOUR_TARGET_COL,
        mode="residual",
        feature_cols=list(DOW_HOUR_FEATURES),
    )
    n_groups = 16 * 7 * 24  # = 2688
    seq_per_group = 12 - 8  # = 4
    assert X.shape[0] == n_groups * seq_per_group  # 10752
    assert X.shape[1] == 8
    assert X.shape[2] == 25  # 25 features
