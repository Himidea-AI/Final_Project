import numpy as np
import pytest


def test_compute_mape_basic():
    from scripts.evaluate_model import compute_mape
    pred = np.array([1100.0, 2200.0, 3300.0, 4400.0])
    true = np.array([1000.0, 2000.0, 3000.0, 4000.0])
    assert compute_mape(pred, true) == pytest.approx(10.0)


def test_compute_mape_excludes_near_zero():
    from scripts.evaluate_model import compute_mape
    # 999원은 제외, 1000원은 포함 — 경계값 1000원 명확히 검증
    pred = np.array([110.0, 500.0, 1100.0])
    true = np.array([100.0, 999.0, 1000.0])  # 999원 제외, 1000원 포함
    # 포함되는 것: pred=1100, true=1000 → MAPE = 10%
    # pred=110, true=100 → MAPE = 10%
    # 평균 = 10%
    assert compute_mape(pred, true) == pytest.approx(10.0)


def test_compute_mape_all_near_zero_returns_nan():
    from scripts.evaluate_model import compute_mape
    # 999원 미만 전부 → nan
    assert np.isnan(compute_mape(np.array([500.0]), np.array([999.0])))


def test_compute_mae():
    from scripts.evaluate_model import compute_mae
    assert compute_mae(np.array([110.0, 90.0]), np.array([100.0, 100.0])) == pytest.approx(10.0)


def test_compute_rmse():
    from scripts.evaluate_model import compute_rmse
    assert compute_rmse(np.array([110.0, 90.0]), np.array([100.0, 100.0])) == pytest.approx(10.0)


def test_compute_bias_positive():
    from scripts.evaluate_model import compute_bias
    assert compute_bias(np.array([110.0, 220.0]), np.array([100.0, 200.0])) == pytest.approx(15.0)


def test_compute_bias_negative():
    from scripts.evaluate_model import compute_bias
    assert compute_bias(np.array([90.0, 180.0]), np.array([100.0, 200.0])) == pytest.approx(-15.0)
