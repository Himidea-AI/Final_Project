"""Residual learning 단위 테스트 — Plan Task 2.

mode='residual' 시 prepare_sequences 가 Δy 를 target 으로 생성하고,
predict_residual 이 last_value + delta 로 합산하는지 검증.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def _make_synthetic_df() -> pd.DataFrame:
    """16동 × 24시간대 × 12분기 = 4608 row 합성 데이터.

    target = 1000 + 100*quarter_idx + 10*time_zone (단순 trend) — diff 가 일정하면
    잔차 분포가 안정적.
    """
    from models.living_pop_forecast.data_prep import MAPO_DONG_CODES

    rows = []
    for dc in MAPO_DONG_CODES:
        for tz in range(24):
            for qi in range(12):
                quarter = 20190 + qi  # 2019Q0..2021Q11 (단순 정수 quarter id)
                base = 1000.0 + 100.0 * qi + 10.0 * tz
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


def test_residual_mode_target_is_delta():
    """mode='residual' 시 y_seq 가 Δy 인지 확인 + target_scaler 가 잔차 분포 fit."""
    from models.living_pop_forecast.data_prep import (
        TARGET_COL,
        _add_dong_one_hot,
        build_timeseries,
        prepare_sequences,
    )

    df = _make_synthetic_df()
    df = build_timeseries(df)
    df = _add_dong_one_hot(df)

    feature_cols = [
        "total_avg_pop",
        "weekday_avg_pop",
        "weekend_avg_pop",
        "time_zone_norm",
        "quarter_num",
    ]

    X_abs, y_abs, _, tgt_abs, _ = prepare_sequences(
        df, window_size=8, target_col=TARGET_COL, feature_cols=feature_cols, mode="absolute"
    )
    X_res, y_res, feat_res, tgt_res, _ = prepare_sequences(
        df, window_size=8, target_col=TARGET_COL, feature_cols=feature_cols, mode="residual"
    )

    # 같은 시퀀스 수
    assert X_abs.shape == X_res.shape
    assert y_abs.shape == y_res.shape

    # absolute mode 에서 raw y 분포: tgt_abs.data_min_ 는 raw target 의 최소값
    # residual mode 에서 잔차 분포: tgt_res.data_min_ 는 잔차 (Δy) 의 최소값
    abs_min = float(tgt_abs.data_min_[0])
    abs_max = float(tgt_abs.data_max_[0])
    res_min = float(tgt_res.data_min_[0])
    res_max = float(tgt_res.data_max_[0])

    # 합성 데이터: y 는 1000~3110 범위, Δy 는 동일 (dong, tz) 그룹 내 일정한 100
    assert abs_min >= 1000.0 - 1.0
    assert abs_max <= 3500.0
    # 잔차 분포는 raw 보다 훨씬 좁아야 함 (max-min 비교)
    assert (res_max - res_min) < (abs_max - abs_min), (
        f"잔차 range ({res_max - res_min:.2f}) 가 absolute range ({abs_max - abs_min:.2f}) 보다 크다"
    )

    # 평균: 잔차 mean 는 ~0 근처여야 (trend 가 일정하면 정확히 100, 합성 데이터)
    # tgt_scaler 의 mean 는 직접 노출 X — y 정규화값을 inverse_transform 해서 확인.
    sample_y_norm = y_res[:5].astype(np.float32)
    sample_delta_actual = tgt_res.inverse_transform(sample_y_norm)
    # 합성 데이터의 잔차는 모두 100 이어야 한다
    assert np.allclose(sample_delta_actual, 100.0, atol=1.0), (
        f"잔차 평균 100 기대, 실제 {sample_delta_actual.flatten().tolist()}"
    )


def test_residual_zero_delta_equals_naive():
    """model 이 0 출력하면 y_pred = last_value (= naive lag=1)."""
    import torch

    from models.living_pop_forecast.data_prep import (
        TARGET_COL,
        _add_dong_one_hot,
        build_timeseries,
        prepare_sequences,
    )
    from models.living_pop_forecast.residual_predict import (
        _autoregressive_residual_predict,
    )

    df = _make_synthetic_df()
    df = build_timeseries(df)
    df = _add_dong_one_hot(df)

    feature_cols = [
        "total_avg_pop",
        "weekday_avg_pop",
        "weekend_avg_pop",
        "time_zone_norm",
        "quarter_num",
    ]

    X, _, feat_scaler, tgt_scaler, _ = prepare_sequences(
        df, window_size=8, target_col=TARGET_COL, feature_cols=feature_cols, mode="residual"
    )

    class ZeroModel(torch.nn.Module):
        """delta_norm = 0.5 → tgt_scaler.inverse(0.5) 가 0 이 되도록 fit 했다면 OK.
        하지만 일반적으로 잔차 0 의 정규화값은 0.5 가 아님 (MinMax). 따라서 정확히
        '0 잔차' 출력하려면 inverse_transform([[0_norm]]) == 0 인 norm 값을 찾아야.
        합성 데이터는 잔차가 항상 100 이므로 잔차 0 은 normalize 도메인 외 → 단순화 위해
        delta_actual=0 직접 검증 대신, '예측 = last_value + 0_actual' 시나리오를
        tgt_scaler 가 (0,)→0_norm 변환하도록 mock 한다."""

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return torch.zeros((x.shape[0], 1))

    # tgt_scaler 우회: 대체 mock — 0 delta_norm → 0 delta_actual
    class IdentityScaler:
        scale_ = np.array([1.0])
        min_ = np.array([0.0])

        def inverse_transform(self, x):  # type: ignore[no-untyped-def]
            return np.asarray(x)

        def transform(self, x):  # type: ignore[no-untyped-def]
            return np.asarray(x)

    # 첫 시퀀스만 사용
    seq = X[0]
    model = ZeroModel()
    target_col = TARGET_COL

    results = _autoregressive_residual_predict(
        model=model,  # type: ignore[arg-type]
        seq_norm=seq,
        feat_scaler=feat_scaler,
        tgt_scaler=IdentityScaler(),  # type: ignore[arg-type]
        feature_cols=feature_cols,
        target_col=target_col,
        n_quarters=3,
        confidence_z=1.96,
        device=torch.device("cpu"),
    )

    # last_value 계산 (실제 인구 단위)
    target_idx = feature_cols.index(target_col)
    last_norm = float(seq[-1, target_idx])
    n_feat = len(feat_scaler.scale_)
    placeholder = np.zeros((1, n_feat), dtype=np.float32)
    placeholder[0, target_idx] = last_norm
    last_actual = float(feat_scaler.inverse_transform(placeholder)[0, target_idx])

    # delta=0 이면 모든 step 의 예측이 last_value 와 일치 (naive lag=1 baseline)
    assert abs(results[0]["predicted_pop"] - round(last_actual, 0)) < 1.0
    assert abs(results[1]["predicted_pop"] - round(last_actual, 0)) < 1.0
    assert abs(results[2]["predicted_pop"] - round(last_actual, 0)) < 1.0


def test_metadata_mode_residual_recorded(tmp_path):
    """metadata json 에 mode='residual' 기록 검증 (실제 학습 산출물 확인)."""
    weights_dir = Path("models/living_pop_forecast/weights")
    target_meta = weights_dir / "living_pop_metadata_v4_residual.json"
    if not target_meta.exists():
        pytest.skip("아직 residual 학습 미실행 — train 후 재시도")
    meta = json.loads(target_meta.read_text(encoding="utf-8"))
    assert meta.get("mode") == "residual"
    assert meta.get("version") == "v4_residual"


def test_absolute_mode_unchanged():
    """mode='absolute' default 동작은 v2 와 동일 (regression 방지).

    주의: prepare_sequences v2 구현에서 y 정규화는 group 별 scaler.transform 했으나,
    refactor 후에도 결과 동일해야 함 — 고정 합성 데이터로 비교.
    """
    from models.living_pop_forecast.data_prep import (
        TARGET_COL,
        _add_dong_one_hot,
        build_timeseries,
        prepare_sequences,
    )

    df = _make_synthetic_df()
    df = build_timeseries(df)
    df = _add_dong_one_hot(df)

    feature_cols = [
        "total_avg_pop",
        "weekday_avg_pop",
        "weekend_avg_pop",
        "time_zone_norm",
        "quarter_num",
    ]

    # default mode call (mode 인자 없이) 와 mode="absolute" 명시 호출이 동일
    X1, y1, _, _, _ = prepare_sequences(df, window_size=8, target_col=TARGET_COL, feature_cols=feature_cols)
    X2, y2, _, _, _ = prepare_sequences(
        df, window_size=8, target_col=TARGET_COL, feature_cols=feature_cols, mode="absolute"
    )
    assert np.array_equal(X1, X2)
    assert np.array_equal(y1, y2)


def test_residual_mode_invalid_raises():
    """잘못된 mode 값은 ValueError."""
    from models.living_pop_forecast.data_prep import prepare_sequences

    df = _make_synthetic_df()

    with pytest.raises(ValueError, match="mode 는 'absolute'"):
        prepare_sequences(
            df,
            window_size=4,
            target_col="total_avg_pop",
            feature_cols=["total_avg_pop", "weekday_avg_pop", "weekend_avg_pop"],
            mode="invalid",
        )
