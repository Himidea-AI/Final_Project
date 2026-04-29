"""validation/metrics/forecast_metrics.py 단위 테스트."""

from __future__ import annotations

import math

import numpy as np
import pytest

from validation.metrics.forecast_metrics import (
    evaluate_all,
    mae,
    mape,
    mase,
    mase_in_sample,
    r2,
    rmse,
    smape,
)


def test_mase_self_equals_one():
    y_true = np.array([10.0, 20.0, 30.0, 40.0])
    y_naive = np.array([12.0, 18.0, 33.0, 38.0])
    # y_pred = y_naive 이면 같은 MAE → MASE = 1
    assert mase(y_true, y_naive, y_naive) == pytest.approx(1.0)


def test_mase_perfect_prediction():
    y_true = np.array([10.0, 20.0, 30.0, 40.0])
    y_naive = np.array([12.0, 18.0, 33.0, 38.0])
    assert mase(y_true, y_true, y_naive) == pytest.approx(0.0)


def test_mape_zero_target_handled():
    y_true = [0.0, 10.0, 20.0]
    y_pred = [1.0, 11.0, 19.0]
    val = mape(y_true, y_pred)
    assert math.isfinite(val)
    assert val >= 0.0


def test_smape_symmetric():
    y_true = np.array([10.0, 20.0, 30.0, 40.0])
    y_pred = np.array([12.0, 18.0, 33.0, 38.0])
    assert smape(y_true, y_pred) == pytest.approx(smape(y_pred, y_true))


def test_r2_perfect():
    y_true = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    assert r2(y_true, y_true) == pytest.approx(1.0)


def test_r2_negative_when_worse_than_mean():
    y_true = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    # mean baseline 보다 훨씬 나쁜 예측 — R² 음수
    y_pred = np.array([10.0, -5.0, 15.0, -10.0, 20.0])
    assert r2(y_true, y_pred) < 0.0


def test_evaluate_all_keys():
    y_true = np.array([10.0, 20.0, 30.0, 40.0])
    y_pred = np.array([11.0, 19.0, 31.0, 39.0])
    y_naive = np.array([10.0, 10.0, 20.0, 30.0])
    result = evaluate_all(y_true, y_pred, y_naive)
    expected = {"MAE", "RMSE", "NRMSE_pct", "MAPE_pct", "sMAPE_pct", "R2", "MASE"}
    assert expected.issubset(result.keys())
    for v in result.values():
        assert isinstance(v, float)


def test_evaluate_all_no_naive():
    y_true = [10.0, 20.0, 30.0, 40.0]
    y_pred = [11.0, 19.0, 31.0, 39.0]
    result = evaluate_all(y_true, y_pred)
    assert "MASE" not in result
    expected = {"MAE", "RMSE", "NRMSE_pct", "MAPE_pct", "sMAPE_pct", "R2"}
    assert expected.issubset(result.keys())


def test_mae_basic():
    assert mae([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(0.0)
    assert mae([1.0, 2.0, 3.0], [2.0, 3.0, 4.0]) == pytest.approx(1.0)


def test_rmse_basic():
    assert rmse([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(0.0)
    assert rmse([0.0, 0.0], [3.0, 4.0]) == pytest.approx(np.sqrt((9 + 16) / 2))


def test_mase_in_sample_definition():
    """Hyndman 2006 정의: model MAE / mean(|train diff|)."""
    y_true_test = np.array([10.0, 20.0, 30.0, 40.0])
    y_pred_test = np.array([11.0, 19.0, 31.0, 39.0])
    # train diffs: 1, 1, 1, 1 → mean(|diff|) = 1.0
    y_train = np.array([5.0, 6.0, 7.0, 8.0, 9.0])
    expected = float(np.mean(np.abs(y_true_test - y_pred_test))) / 1.0
    assert mase_in_sample(y_true_test, y_pred_test, y_train) == pytest.approx(expected)

    # train 의 lag-1 평균변동을 키우면 MASE 분모가 커지고 결과는 작아진다.
    y_train_volatile = np.array([5.0, 25.0, 5.0, 25.0, 5.0])  # |diff| 평균 = 20
    expected_v = float(np.mean(np.abs(y_true_test - y_pred_test))) / 20.0
    assert mase_in_sample(y_true_test, y_pred_test, y_train_volatile) == pytest.approx(expected_v)


def test_mase_in_sample_independent_of_test_distribution():
    """test set 의 lag=1 변동성에 독립 (분모는 train 만 의존)."""
    y_train = np.array([100.0, 105.0, 95.0, 110.0, 90.0, 100.0])
    # 같은 (y_true_test, y_pred_test) 면 test 시퀀스 순서/이웃 변동성 무관하게 동일
    y_true_a = np.array([200.0, 220.0, 210.0])
    y_pred_a = np.array([198.0, 222.0, 209.0])
    y_true_b = np.array([220.0, 200.0, 210.0])  # 순서 바뀜 (test diff 분포 변경)
    y_pred_b = np.array([222.0, 198.0, 209.0])  # 같은 페어 유지
    a = mase_in_sample(y_true_a, y_pred_a, y_train)
    b = mase_in_sample(y_true_b, y_pred_b, y_train)
    assert a == pytest.approx(b)


def test_evaluate_all_includes_both_mase():
    """y_naive + y_train 모두 주면 MASE 와 MASE_in_sample 둘 다 dict 에 있음."""
    y_true = np.array([10.0, 20.0, 30.0, 40.0])
    y_pred = np.array([11.0, 19.0, 31.0, 39.0])
    y_naive = np.array([10.0, 10.0, 20.0, 30.0])
    y_train = np.array([5.0, 6.0, 7.0, 8.0, 9.0])
    result = evaluate_all(y_true, y_pred, y_naive=y_naive, y_train=y_train)
    assert "MASE" in result
    assert "MASE_in_sample" in result
    assert math.isfinite(result["MASE"])
    assert math.isfinite(result["MASE_in_sample"])
    # 명시 수치 검증
    expected_in_sample = float(np.mean(np.abs(y_true - y_pred))) / 1.0
    assert result["MASE_in_sample"] == pytest.approx(expected_in_sample)


def test_evaluate_all_only_y_train():
    """y_naive=None 이지만 y_train 있으면 MASE_in_sample 만 산출."""
    y_true = np.array([10.0, 20.0, 30.0, 40.0])
    y_pred = np.array([11.0, 19.0, 31.0, 39.0])
    y_train = np.array([5.0, 6.0, 7.0, 8.0, 9.0])
    result = evaluate_all(y_true, y_pred, y_train=y_train)
    assert "MASE" not in result
    assert "MASE_in_sample" in result
    expected = float(np.mean(np.abs(y_true - y_pred))) / 1.0
    assert result["MASE_in_sample"] == pytest.approx(expected)
