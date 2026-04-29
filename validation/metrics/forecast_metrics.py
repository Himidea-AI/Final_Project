"""시계열 forecasting 학술 표준 지표.

출처:
- MASE: Hyndman & Koehler (2006), "Another look at measures of forecast accuracy"
- MAPE 등급: Lewis (1982)
- R² 등급: Cohen (1988)
- sMAPE: M4 competition standard

모든 함수는 numpy ndarray 입력을 받고 float 반환.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

ArrayLike = npt.ArrayLike


def mae(y_true: ArrayLike, y_pred: ArrayLike) -> float:
    """Mean Absolute Error."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return float(np.mean(np.abs(y_true - y_pred)))


def rmse(y_true: ArrayLike, y_pred: ArrayLike) -> float:
    """Root Mean Squared Error."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def mape(y_true: ArrayLike, y_pred: ArrayLike, eps: float = 1e-9) -> float:
    """Mean Absolute Percentage Error (%). 분모 0 방지를 위해 eps 사용."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    denom = np.maximum(np.abs(y_true), eps)
    return float(np.mean(np.abs((y_true - y_pred) / denom)) * 100.0)


def smape(y_true: ArrayLike, y_pred: ArrayLike, eps: float = 1e-9) -> float:
    """Symmetric MAPE (%). M4 competition 표준 정의: |y-ŷ| / ((|y|+|ŷ|)/2)."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    denom = np.maximum((np.abs(y_true) + np.abs(y_pred)) / 2.0, eps)
    return float(np.mean(np.abs(y_true - y_pred) / denom) * 100.0)


def r2(y_true: ArrayLike, y_pred: ArrayLike) -> float:
    """결정계수 R². 모델이 mean 대비 얼마나 분산을 설명하는지 (1 = perfect, 0 = mean baseline)."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    if ss_tot == 0.0:
        return float("nan")
    return float(1.0 - ss_res / ss_tot)


def mase(y_true: ArrayLike, y_pred: ArrayLike, y_naive: ArrayLike) -> float:
    """Mean Absolute Scaled Error — *Same-period* (M4 competition style).

    MASE = MAE(y_true, y_pred) / MAE(y_true, y_naive).
    분모는 *test set* 의 1-step naive MAE 이다.
    < 1 이면 naive 보다 우수, = 1 이면 동등, > 1 이면 열등.

    Notes
    -----
    학술적으로 "Hyndman & Koehler 2006 정의" 라고 부르는 표준 MASE 는 분모를
    *train set* 의 1-step naive MAE 로 사용한다. 그 변형은 :func:`mase_in_sample`
    참조. 본 함수는 backward compat 을 위해 same-period 정의로 유지.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    y_naive = np.asarray(y_naive, dtype=float)
    naive_mae = float(np.mean(np.abs(y_true - y_naive)))
    if naive_mae == 0.0:
        return float("nan")
    model_mae = float(np.mean(np.abs(y_true - y_pred)))
    return float(model_mae / naive_mae)


def mase_in_sample(
    y_true_test: ArrayLike,
    y_pred_test: ArrayLike,
    y_train_actuals: ArrayLike,
) -> float:
    """Hyndman & Koehler (2006) 정의 — in-sample naive MAE 분모.

    Parameters
    ----------
    y_true_test : ndarray
        Test set 의 실제값.
    y_pred_test : ndarray
        Test set 의 예측값.
    y_train_actuals : ndarray
        Train set 의 실제 시계열 (1-step naive MAE 분모 계산용).

    Returns
    -------
    float
        MASE_in_sample = mean(|y_true_test - y_pred_test|) /
                         mean(|y_train[t] - y_train[t-1]|)

    Reference
    ---------
    Hyndman, R. J., & Koehler, A. B. (2006).
    Another look at measures of forecast accuracy.
    International Journal of Forecasting, 22(4), 679-688.
    """
    y_true_arr = np.asarray(y_true_test, dtype=float)
    y_pred_arr = np.asarray(y_pred_test, dtype=float)
    y_train_arr = np.asarray(y_train_actuals, dtype=float).reshape(-1)
    if y_train_arr.size < 2:
        return float("nan")
    train_diff_mae = float(np.mean(np.abs(np.diff(y_train_arr))))
    if train_diff_mae == 0.0:
        return float("nan")
    model_mae = float(np.mean(np.abs(y_true_arr - y_pred_arr)))
    return float(model_mae / train_diff_mae)


def evaluate_all(
    y_true: ArrayLike,
    y_pred: ArrayLike,
    y_naive: ArrayLike | None = None,
    y_train: ArrayLike | None = None,
) -> dict:
    """모든 지표 한번에 계산.

    Parameters
    ----------
    y_true, y_pred : array-like
        Test set 의 실제값 / 예측값.
    y_naive : array-like, optional
        Test set 의 1-step naive baseline (Same-period MASE 분모).
        주어지면 결과 dict 에 ``MASE`` 키 추가.
    y_train : array-like, optional
        Train split 의 1차원 실제 시계열 (Hyndman in-sample MASE 분모).
        주어지면 결과 dict 에 ``MASE_in_sample`` 키 추가.

    Notes
    -----
    두 MASE 정의 모두 valid 하다.
    - ``MASE`` : test 구간 1-step naive MAE 기반 (M4 competition style).
    - ``MASE_in_sample`` : train 시계열 lag-1 변동성 기반 (Hyndman & Koehler 2006).
    """
    y_true_arr = np.asarray(y_true, dtype=float)
    y_pred_arr = np.asarray(y_pred, dtype=float)

    rmse_val = rmse(y_true_arr, y_pred_arr)
    # NRMSE_pct: 분모 = y_true 의 range (max - min). 다른 정의 (mean 기반) 와 비교 시 주의.
    y_range = float(np.max(y_true_arr) - np.min(y_true_arr))
    nrmse_pct = float(rmse_val / y_range * 100.0) if y_range > 0 else float("nan")

    result: dict = {
        "MAE": mae(y_true_arr, y_pred_arr),
        "RMSE": rmse_val,
        "NRMSE_pct": nrmse_pct,
        "MAPE_pct": mape(y_true_arr, y_pred_arr),
        "sMAPE_pct": smape(y_true_arr, y_pred_arr),
        "R2": r2(y_true_arr, y_pred_arr),
    }
    if y_naive is not None:
        result["MASE"] = mase(y_true_arr, y_pred_arr, y_naive)
    if y_train is not None:
        result["MASE_in_sample"] = mase_in_sample(y_true_arr, y_pred_arr, y_train)
    return result
