import numpy as np
import pytest


def test_compute_mape_basic():
    from scripts.evaluate_model import compute_mape
    pred = np.array([110.0, 220.0, 330.0, 440.0])
    true = np.array([100.0, 200.0, 300.0, 400.0])
    assert compute_mape(pred, true) == pytest.approx(10.0)


def test_compute_mape_excludes_near_zero():
    from scripts.evaluate_model import compute_mape
    pred = np.array([110.0, 500.0])
    true = np.array([100.0, 1.0])   # 1원 → 제외
    assert compute_mape(pred, true) == pytest.approx(10.0)


def test_compute_mape_all_near_zero_returns_nan():
    from scripts.evaluate_model import compute_mape
    assert np.isnan(compute_mape(np.array([1.0]), np.array([0.5])))


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
