"""
예측 정확도 측정 — MAPE, MAE, RMSE, R², 방향성 일치율
"""

from __future__ import annotations

import numpy as np


def mape(actual: list | np.ndarray, predicted: list | np.ndarray) -> float:
    """MAPE (Mean Absolute Percentage Error) 계산. 실제값이 0인 항목은 제외."""
    actual = np.array(actual, dtype=float)
    predicted = np.array(predicted, dtype=float)
    mask = actual != 0
    if mask.sum() == 0:
        return float("nan")
    return float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100)


def mae(actual: list | np.ndarray, predicted: list | np.ndarray) -> float:
    """MAE (Mean Absolute Error) 계산."""
    actual = np.array(actual, dtype=float)
    predicted = np.array(predicted, dtype=float)
    return float(np.mean(np.abs(actual - predicted)))


def calculate_mae(actual: list | np.ndarray, predicted: list | np.ndarray) -> float:
    """MAE 별칭 (하위 호환)."""
    return mae(actual, predicted)


def rmse(actual: list | np.ndarray, predicted: list | np.ndarray) -> float:
    """RMSE (Root Mean Square Error) 계산."""
    actual = np.array(actual, dtype=float)
    predicted = np.array(predicted, dtype=float)
    return float(np.sqrt(np.mean((actual - predicted) ** 2)))


def calculate_rmse(actual: list | np.ndarray, predicted: list | np.ndarray) -> float:
    """RMSE 별칭 (하위 호환)."""
    return rmse(actual, predicted)


def r_squared(actual: list | np.ndarray, predicted: list | np.ndarray) -> float:
    """R² 결정계수 계산."""
    actual = np.array(actual, dtype=float)
    predicted = np.array(predicted, dtype=float)
    ss_res = np.sum((actual - predicted) ** 2)
    ss_tot = np.sum((actual - np.mean(actual)) ** 2)
    if ss_tot == 0:
        return float("nan")
    return float(1 - ss_res / ss_tot)


def calculate_directional_accuracy(
    actual: list | np.ndarray, predicted: list | np.ndarray
) -> float:
    """방향성 일치율 — 상승/하락 방향 예측 정확도."""
    actual = np.array(actual, dtype=float)
    predicted = np.array(predicted, dtype=float)
    if len(actual) < 2:
        return float("nan")
    actual_dir = np.diff(actual) > 0
    pred_dir = np.diff(predicted) > 0
    return float(np.mean(actual_dir == pred_dir) * 100)


def generate_accuracy_report(
    actual: list | np.ndarray,
    predicted: list | np.ndarray,
    labels: list[str] | None = None,
) -> dict:
    """정확도 종합 보고서.

    Returns
    -------
    dict
        overall: {mape, mae, rmse, r_squared, directional_accuracy}
        per_label: [{label, mape, mae, rmse}, ...] (labels 제공 시)
    """
    report: dict = {
        "overall": {
            "mape": mape(actual, predicted),
            "mae": mae(actual, predicted),
            "rmse": rmse(actual, predicted),
            "r_squared": r_squared(actual, predicted),
            "directional_accuracy": calculate_directional_accuracy(actual, predicted),
        }
    }

    if labels is not None:
        from collections import defaultdict

        groups: dict[str, dict] = defaultdict(lambda: {"actual": [], "predicted": []})
        for lbl, a, p in zip(labels, actual, predicted):
            groups[lbl]["actual"].append(a)
            groups[lbl]["predicted"].append(p)

        per_label = []
        for lbl, vals in sorted(groups.items()):
            per_label.append(
                {
                    "label": lbl,
                    "mape": mape(vals["actual"], vals["predicted"]),
                    "mae": mae(vals["actual"], vals["predicted"]),
                    "rmse": rmse(vals["actual"], vals["predicted"]),
                }
            )
        report["per_label"] = per_label

    return report
