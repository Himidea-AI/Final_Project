# tests/test_imputed_v4.py
"""Phase 1 본 학습 단위 테스트 — Multi-Output + 6 seed + CI + extrapolation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from validation.reverse_engineer_sales_v4 import (
    COUNT_COLS,
    SALES_COLS,
    SEEDS,
    TARGET_COLS,
    calculate_confidence,
    detect_extrapolation_cells,
    fit_seed_ensemble_multi,
    predict_with_ci_multi,
)


@pytest.fixture
def small_train():
    """100 셀 × 5 피처 학습 + 137 셀 결측 mock."""
    rng = np.random.default_rng(42)
    X_train = pd.DataFrame(rng.normal(size=(100, 5)), columns=[f"f{i}" for i in range(5)])
    Y_train = pd.DataFrame(rng.normal(size=(100, 48)), columns=TARGET_COLS)
    X_missing = pd.DataFrame(rng.normal(size=(137, 5)), columns=[f"f{i}" for i in range(5)])
    store_count = np.full(137, 10.0)
    return X_train, Y_train, X_missing, store_count


def test_target_cols_count():
    assert len(TARGET_COLS) == 48
    assert len(SALES_COLS) == 24
    assert len(COUNT_COLS) == 24


def test_predict_with_ci_multi_returns_correct_shape(small_train, tmp_path):
    X_tr, Y_tr, X_mi, sc = small_train
    models = fit_seed_ensemble_multi(
        X_tr, Y_tr, SEEDS, {"n_estimators": 50, "max_depth": 5, "n_jobs": -1}, ckpt_dir=tmp_path
    )
    out = predict_with_ci_multi(models, X_mi, sc)
    assert set(out.keys()) == {"mean", "std", "lower_95", "upper_95", "ci_width_ratio"}
    for v in out.values():
        assert v.shape == (137, 48)


def test_lower_95_never_negative(small_train, tmp_path):
    X_tr, Y_tr, X_mi, sc = small_train
    models = fit_seed_ensemble_multi(
        X_tr, Y_tr, SEEDS, {"n_estimators": 50, "max_depth": 5, "n_jobs": -1}, ckpt_dir=tmp_path
    )
    out = predict_with_ci_multi(models, X_mi, sc)
    assert (out["lower_95"].values >= 0).all()


def test_extrapolation_detection_high_variance():
    """monthly_sales std 가 median 의 1.8배 이상인 셀 → True."""
    pred_dict = {
        "std": pd.DataFrame(np.array([[1.0] * 48, [10.0] * 48, [1.0] * 48]), columns=TARGET_COLS),
    }
    df_missing = pd.DataFrame({"quarter": [20191, 20192, 20193]})
    mask = detect_extrapolation_cells(df_missing, pred_dict, threshold_ratio=1.8)
    assert mask[1]  # std 10 vs median 1.0 → ratio 10
    assert not mask[0]
    assert not mask[2]


def test_calculate_confidence_extrapolation_max_04():
    """extrapolation flag=True 셀 confidence ≤ 0.40."""
    pred_dict = {"ci_width_ratio": pd.DataFrame({"monthly_sales": [0.4, 0.4]}, index=[0, 1])}
    extrap_mask = np.array([True, False])
    audit = {"mnar_wape": 13.0}  # base = 0.87
    conf = calculate_confidence(pred_dict, extrap_mask, audit)
    assert conf[0] <= 0.40
    assert conf[1] >= 0.65


def test_calculate_confidence_normal_min_065():
    """일반 imputed (low CI) → confidence ≥ 0.65."""
    pred_dict = {"ci_width_ratio": pd.DataFrame({"monthly_sales": [0.3, 0.3]}, index=[0, 1])}
    extrap_mask = np.array([False, False])
    audit = {"mnar_wape": 13.0}
    conf = calculate_confidence(pred_dict, extrap_mask, audit)
    assert (conf >= 0.65).all()


def test_six_seeds_all_used(small_train, tmp_path):
    X_tr, Y_tr, X_mi, sc = small_train
    models = fit_seed_ensemble_multi(
        X_tr, Y_tr, SEEDS, {"n_estimators": 50, "max_depth": 5, "n_jobs": -1}, ckpt_dir=tmp_path
    )
    assert len(models) == 6
