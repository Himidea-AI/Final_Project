"""
TCN v1(자기회귀) vs v2(DMS) 비교 평가 스크립트

Usage:
    python scripts/evaluate_model.py \
        --v2-weights models/tcn_forecast/weights/finetuned_mapo_tcn_v2.pt \
        --v2-scalers models/tcn_forecast/weights/finetune_tcn_scalers_v2.pkl

담당: B2 — 수지니
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"

VAL_QUARTER = 20241  # 검증 시작 분기 (2024Q1 이상 → val)

V2_CONFIG = {
    "window_size": 8,  # TCN v2 최소 학습 윈도우
}

EXCLUDE_COMBOS: set[tuple[str, str]] = set()  # 평가 제외 조합 (필요 시 추가)


# ---------------------------------------------------------------------------
# 지표 계산 함수
# ---------------------------------------------------------------------------


def compute_mape(pred: np.ndarray, true: np.ndarray) -> float:
    """MAPE 계산. true < 1000원(near-zero) 포인트 제외."""
    mask = true >= 1000
    if mask.sum() == 0:
        return float("nan")
    return float(np.mean(np.abs(pred[mask] - true[mask]) / true[mask]) * 100)


def compute_mae(pred: np.ndarray, true: np.ndarray) -> float:
    return float(np.mean(np.abs(pred - true)))


def compute_rmse(pred: np.ndarray, true: np.ndarray) -> float:
    return float(np.sqrt(np.mean((pred - true) ** 2)))


def compute_bias(pred: np.ndarray, true: np.ndarray) -> float:
    return float(np.mean(pred - true))


def compute_per_quarter_mape(pred: np.ndarray, true: np.ndarray) -> list[float]:
    """분기별 MAPE. pred/true shape: (n_combos, 4). true < 1000원 제외."""
    result = []
    for q in range(4):
        mask = true[:, q] >= 1000
        if mask.sum() == 0:
            result.append(float("nan"))
        else:
            result.append(float(np.mean(np.abs(pred[mask, q] - true[mask, q]) / true[mask, q]) * 100))
    return result


def compute_directional_accuracy(q0: np.ndarray, pred: np.ndarray, true: np.ndarray) -> float:
    """방향 정확도. q0: (n_combos,), pred/true: (n_combos, 4)."""
    pred_seq = np.concatenate([q0[:, None], pred], axis=1)
    true_seq = np.concatenate([q0[:, None], true], axis=1)
    return float(np.mean(np.sign(np.diff(pred_seq, axis=1)) == np.sign(np.diff(true_seq, axis=1))) * 100)


# ---------------------------------------------------------------------------
# val 데이터 분리 / 유효 조합 필터링
# ---------------------------------------------------------------------------


def split_train_val(ts: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """quarter 기준으로 train / val 분리. VAL_QUARTER 이상 → val."""
    return ts[ts["quarter"] < VAL_QUARTER].copy(), ts[ts["quarter"] >= VAL_QUARTER].copy()


def get_valid_combos(ts: pd.DataFrame) -> list[tuple[str, str]]:
    """평가 가능한 (dong_code, industry_code) 조합 목록 반환."""
    train_ts, val_ts = split_train_val(ts)
    v2_window = V2_CONFIG["window_size"]  # 8
    valid = []
    for (dong, ind), train_group in train_ts.groupby(["dong_code", "industry_code"]):
        if (dong, ind) in EXCLUDE_COMBOS:
            continue
        if len(train_group) < v2_window:
            continue
        val_group = val_ts[(val_ts["dong_code"] == dong) & (val_ts["industry_code"] == ind)]
        if len(val_group) < 4:
            continue
        valid.append((dong, ind))
    return valid
