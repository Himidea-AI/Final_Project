"""모든 D 모델 변형을 동일 test split + 학술 metric 으로 평가.

각 모델 변형 (v2, v3, v4_residual, ARIMA, naive baseline) 을 시간순 70/15/15
split 의 동일 test 구간에서 평가하고 학술 metric (MAE/RMSE/MAPE/sMAPE/R2/MASE
/MASE_in_sample) 을 통합 출력한다.

각 evaluator 는 ``(y_true, y_pred, y_naive, y_train_actuals)`` 4-tuple 을
반환하는 시그니처로 추상화되어 있어 v5_group_residual 등 신규 변형도 동일
패턴으로 추가 가능하다. ``y_train_actuals`` 는 모든 그룹 (dong × time_zone) 의
train split target 시퀀스를 시간순으로 concat 한 1차원 array 로,
Hyndman & Koehler (2006) in-sample MASE 의 분모 계산에 쓰인다.

Usage:
    python -m validation.experiments.living_pop.evaluate_all
    python -m validation.experiments.living_pop.evaluate_all --versions naive_lag1,v2
    python -m validation.experiments.living_pop.evaluate_all --filter v4_residual
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from validation.metrics.forecast_metrics import evaluate_all as compute_metrics

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = PROJECT_ROOT / "validation" / "results"
DEFAULT_CSV_PATH = RESULTS_DIR / "living_pop_metrics_all.csv"

# 사전 보고된 MASE (Task 2 / 사전 결과 보고서) — 검증용
EXPECTED_MASE: dict[str, float] = {
    "naive_lag1": 1.0,
    "v2": 4.54,
    "v4_residual": 0.866,
    "arima": 2.54,
}

# 사전 보고 ±tolerance (절대값)
MASE_TOLERANCE = 0.20

DEFAULT_VERSIONS: tuple[str, ...] = (
    "naive_lag1",
    "naive_lag4_seasonal",
    "v2",
    "v3",
    "v4_residual",
    "v5_group_residual",
    "v5_group_rel_only",
    "v5_group_decomp",
    "arima",
)


# ---------------------------------------------------------------------------
# 공통 유틸 — 데이터 로드 / split 인덱스 / target 역정규화
# ---------------------------------------------------------------------------


def _split_indices(n: int, train_ratio: float = 0.70, val_ratio: float = 0.15) -> tuple[int, int]:
    """시간순 70/15/15 split 인덱스 (train_end, val_end)."""
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)
    return n_train, n_train + n_val


def _inverse_target_with_padding(value_norm: float | np.ndarray, feat_scaler, target_idx: int) -> np.ndarray:
    """MinMaxScaler.feat 차원의 target 만 inverse_transform.

    feat_scaler 는 모든 피처에 fit 됐으므로, target 차원만 살리고 나머지는 0 으로
    채워서 inverse 후 target_idx 만 추출한다.
    """
    arr = np.atleast_1d(np.asarray(value_norm, dtype=np.float32)).reshape(-1)
    n_feat = len(feat_scaler.scale_)
    placeholder = np.zeros((arr.shape[0], n_feat), dtype=np.float32)
    placeholder[:, target_idx] = arr
    inv = feat_scaler.inverse_transform(placeholder)
    return inv[:, target_idx]


def _load_metadata(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"metadata 미발견: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 시퀀스 빌드 — TCN 변형 (v2/v3/v4_residual) 공통
# ---------------------------------------------------------------------------


def _build_tcn_sequences(
    feature_cols: list[str],
    mode: str,
    window_size: int = 8,
    target_col: str | None = None,
    add_group_features: bool = False,
    train_end_quarter: int | None = None,
):
    """TCN 변형 추론용 raw 시퀀스 빌드 (정규화 X — scaler 는 caller 가 적용).

    Parameters
    ----------
    add_group_features : bool, default False
        v5 변형용. True 시 build_timeseries 가 group_mean / group_relative 컬럼 추가.
    train_end_quarter : int | None
        v5 변형용 leakage 방지 cutoff. metadata 에 기록된 값을 그대로 전달.

    Returns
    -------
    dict
        keys: X_raw, y_raw, last_value_raw, df_full, target_idx, feature_cols
        - X_raw: (N, W, F) — feature_cols 순서의 raw 값
        - y_raw: (N,) — t 시점 target 의 raw 값 (실제 인구 단위)
        - last_value_raw: (N,) — t-1 시점 target raw 값 (residual / naive 계산용)
        - last_value_lag4_raw: (N,) — t-4 시점 target raw 값 (seasonal naive 용)
    """
    from models.living_pop_forecast.data_prep import (
        TARGET_COL,
        _add_dong_one_hot,
        build_timeseries,
        load_living_population,
    )

    if target_col is None:
        target_col = TARGET_COL

    df = load_living_population()
    df = build_timeseries(df, add_group_features=add_group_features, train_end_quarter=train_end_quarter)
    df = _add_dong_one_hot(df)

    # feature_cols 중 df 에 없는 컬럼 검증
    missing = [c for c in feature_cols if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame 에 없는 feature_cols: {missing}")
    target_idx = feature_cols.index(target_col)

    X_list: list[np.ndarray] = []
    y_list: list[float] = []
    last_list: list[float] = []
    last_lag4_list: list[float] = []
    group_mean_list: list[float] = []
    # 그룹별 target 전체 시계열 (train_actuals 추출용 — Hyndman MASE 분모)
    group_full_targets: list[np.ndarray] = []
    # 각 그룹이 X_list 에 기여한 시퀀스 개수 (train/val/test 분기 시 그룹 매칭에 사용)
    group_seq_counts: list[int] = []

    has_group_mean = "group_mean" in df.columns

    for (_dong, _tz), group in df.groupby(["dong_code", "time_zone"], sort=True):
        if len(group) <= window_size:
            continue
        feat_vals = group[feature_cols].values.astype(np.float32)
        raw_targets = group[target_col].values.astype(np.float32)
        group_means = group["group_mean"].values.astype(np.float32) if has_group_mean else None
        group_full_targets.append(raw_targets.copy())
        group_seq_counts.append(len(group) - window_size)
        for i in range(len(group) - window_size):
            X_list.append(feat_vals[i : i + window_size])
            y_list.append(float(raw_targets[i + window_size]))
            last_list.append(float(raw_targets[i + window_size - 1]))
            # seasonal naive lag=4: window 중 4 step 전 (없으면 그냥 lag=1 으로 fallback)
            lag4_idx_in_window = window_size - 4
            if lag4_idx_in_window >= 0:
                last_lag4_list.append(float(feat_vals[i + lag4_idx_in_window, target_idx]))
            else:
                last_lag4_list.append(float(raw_targets[i + window_size - 1]))
            if group_means is not None:
                group_mean_list.append(float(group_means[i + window_size]))

    if not X_list:
        raise ValueError(f"시퀀스 생성 실패: window_size={window_size} 보다 긴 그룹 없음")

    X_raw = np.asarray(X_list, dtype=np.float32)
    y_raw = np.asarray(y_list, dtype=np.float32)
    last_raw = np.asarray(last_list, dtype=np.float32)
    last_lag4_raw = np.asarray(last_lag4_list, dtype=np.float32)
    group_mean_raw = np.asarray(group_mean_list, dtype=np.float32) if group_mean_list else None

    return {
        "X_raw": X_raw,
        "y_raw": y_raw,
        "last_value_raw": last_raw,
        "last_value_lag4_raw": last_lag4_raw,
        "group_mean_raw": group_mean_raw,
        "target_idx": target_idx,
        "feature_cols": feature_cols,
        "window_size": int(window_size),
        "group_full_targets": group_full_targets,
        "group_seq_counts": group_seq_counts,
    }


def _load_tcn_artifacts(metadata_path: Path):
    """metadata + scalers + model 가중치 로드.

    Returns
    -------
    dict
        keys: model, feat_scaler, tgt_scaler, metadata
    """
    from models.living_pop_forecast.train import load_scalers
    from models.tcn_forecast.model import TCNForecaster

    metadata = _load_metadata(metadata_path)
    weights_path = Path(metadata["save_path"])
    scalers_path = Path(metadata["scalers_path"])
    if not weights_path.exists():
        raise FileNotFoundError(f"가중치 파일 미발견: {weights_path}")
    if not scalers_path.exists():
        raise FileNotFoundError(f"scaler 파일 미발견: {scalers_path}")

    feat_scaler, tgt_scaler = load_scalers(scalers_path)
    input_size = len(feat_scaler.scale_)

    model = TCNForecaster(
        input_size=input_size,
        n_channels=int(metadata.get("n_channels", 64)),
        kernel_size=int(metadata.get("kernel_size", 2)),
        dilations=list(metadata.get("dilations", [1, 2, 4])),
        dropout=float(metadata.get("dropout", 0.2)),
    )
    model.load_weights(weights_path)
    model.eval()

    return {
        "model": model,
        "feat_scaler": feat_scaler,
        "tgt_scaler": tgt_scaler,
        "metadata": metadata,
    }


def _predict_tcn_test(
    model,
    X_test_raw: np.ndarray,
    feat_scaler,
    target_idx: int,
    batch_size: int = 256,
) -> np.ndarray:
    """test 윈도우 일괄 추론 — pred_norm 출력."""
    # window 별로 정규화 적용 (각 (W, F) 슬라이스)
    n, w, f = X_test_raw.shape
    flat = X_test_raw.reshape(-1, f)
    flat_norm = feat_scaler.transform(flat)
    X_norm = flat_norm.reshape(n, w, f).astype(np.float32)

    preds: list[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, n, batch_size):
            chunk = torch.from_numpy(X_norm[start : start + batch_size])
            out = model(chunk).cpu().numpy().reshape(-1)
            preds.append(out)
    return np.concatenate(preds, axis=0)


# ---------------------------------------------------------------------------
# Naive baseline 계산 — 모든 evaluator 공통 사용
# ---------------------------------------------------------------------------


def _compute_naive_lag1(seq_bundle: dict, train_end: int, val_end: int) -> np.ndarray:
    """test 구간의 lag=1 naive 예측 (= last_value_raw[test])."""
    return seq_bundle["last_value_raw"][val_end:].astype(np.float32)


def _compute_naive_lag4(seq_bundle: dict, train_end: int, val_end: int) -> np.ndarray:
    """test 구간의 seasonal naive lag=4 예측."""
    return seq_bundle["last_value_lag4_raw"][val_end:].astype(np.float32)


def _compute_train_actuals(seq_bundle: dict, train_end: int) -> np.ndarray:
    """Train split 의 1차원 target 시계열 (모든 그룹 시간순 concat).

    Hyndman & Koehler (2006) in-sample MASE 의 분모 (mean(|train[t]-train[t-1]|))
    계산용. 시퀀스 단위 (전역 train_end) 를 그룹별 시퀀스 개수 prefix-sum 으로
    매칭해, 각 그룹의 train 영역 target 만 추출한다.

    각 그룹은 길이 ``L`` 의 raw target 시계열이 있고 시퀀스를 ``L - W`` 개
    생성한다. 시퀀스 ``i`` 는 t=i+W 시점을 예측하므로, 전역 train 시퀀스
    인덱스 [0, train_end) 가 그룹 g 에 [g_start, g_end_in_train) 로 매핑된다면
    그 그룹에서 사용된 train target 시점은 [W, W + (g_end_in_train - g_start)).

    여기서는 lag-1 difference 계산이 목적이므로, 각 그룹마다 *연속된* train
    target 만 추출하고 그룹 사이 경계에서는 ``np.diff`` 가 의미 없는 점프를
    만들지 않도록 그룹별 segment 를 별도로 다룬 뒤 합쳐 ``mase_in_sample``
    내부 ``np.diff`` 가 그룹 경계도 차분에 포함하지 않게끔, NaN 이 아닌
    실수 연결로 간단히 concat 한다 (그룹 경계 차분의 영향은 그룹 수/시퀀스
    수 비율상 매우 작다).
    """
    full_targets = seq_bundle.get("group_full_targets")
    seq_counts = seq_bundle.get("group_seq_counts")
    window_size = int(seq_bundle.get("window_size", 8))
    if not full_targets or not seq_counts:
        # 구버전 bundle: y_raw 의 train 부분으로 대체 (정확도 약간 손실)
        return seq_bundle["y_raw"][:train_end].astype(np.float32)

    pieces: list[np.ndarray] = []
    consumed = 0  # 시퀀스 누적 인덱스 (전역)
    for raw_targets, n_seq in zip(full_targets, seq_counts):
        if n_seq <= 0:
            continue
        g_start = consumed
        g_end = consumed + n_seq
        # 이 그룹과 train_end 의 교집합
        if g_end <= train_end:
            n_train_seq = n_seq
        elif g_start >= train_end:
            n_train_seq = 0
        else:
            n_train_seq = train_end - g_start
        consumed = g_end
        if n_train_seq <= 0:
            continue
        # 시퀀스 i 는 raw_targets[i+W] 를 target 으로 한다.
        # train 시퀀스가 [0, n_train_seq) 면 사용된 target time = [W, W+n_train_seq).
        # 분모는 lag-1 변동성이므로 t=W-1 까지 포함하면 첫 diff 도 의미 있음.
        end_t = window_size + n_train_seq
        segment = raw_targets[:end_t].astype(np.float32)
        pieces.append(segment)
    if not pieces:
        return np.asarray([], dtype=np.float32)
    return np.concatenate(pieces, axis=0)


# ---------------------------------------------------------------------------
# Evaluator 함수 (모두 동일 시그니처:
#     () -> (y_true, y_pred, y_naive, y_train_actuals))
# ---------------------------------------------------------------------------


EvaluatorReturn = tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]


def _evaluate_naive_lag1() -> EvaluatorReturn:
    """Naive lag=1: y_pred = y_naive (test split 동일).

    MASE = 1.0 이어야 한다.
    """
    from models.living_pop_forecast.data_prep import ALL_FEATURES

    bundle = _build_tcn_sequences(feature_cols=list(ALL_FEATURES), mode="absolute")
    n = len(bundle["y_raw"])
    train_end, val_end = _split_indices(n)

    y_true = bundle["y_raw"][val_end:].astype(np.float32)
    y_naive = _compute_naive_lag1(bundle, train_end, val_end)
    y_pred = y_naive.copy()  # naive 자체를 모델로 평가 → MASE = 1
    y_train_actuals = _compute_train_actuals(bundle, train_end)
    return y_true, y_pred, y_naive, y_train_actuals


def _evaluate_naive_lag4_seasonal() -> EvaluatorReturn:
    """Seasonal naive lag=4: y_pred = y[t-4]. naive baseline 은 lag=1 (MASE 비교 공정성)."""
    from models.living_pop_forecast.data_prep import ALL_FEATURES

    bundle = _build_tcn_sequences(feature_cols=list(ALL_FEATURES), mode="absolute")
    n = len(bundle["y_raw"])
    train_end, val_end = _split_indices(n)

    y_true = bundle["y_raw"][val_end:].astype(np.float32)
    y_pred = _compute_naive_lag4(bundle, train_end, val_end)
    y_naive = _compute_naive_lag1(bundle, train_end, val_end)
    y_train_actuals = _compute_train_actuals(bundle, train_end)
    return y_true, y_pred, y_naive, y_train_actuals


def _evaluate_v2() -> EvaluatorReturn:
    """v2 absolute mode TCN 평가."""
    from models.living_pop_forecast.train import WEIGHTS_DIR

    metadata_path = WEIGHTS_DIR / "living_pop_metadata_v2.json"
    artifacts = _load_tcn_artifacts(metadata_path)
    metadata = artifacts["metadata"]

    feature_cols = list(metadata["feature_columns"])
    bundle = _build_tcn_sequences(feature_cols=feature_cols, mode="absolute")

    n = len(bundle["y_raw"])
    train_end, val_end = _split_indices(n)
    X_test = bundle["X_raw"][val_end:]
    y_true = bundle["y_raw"][val_end:].astype(np.float32)

    pred_norm = _predict_tcn_test(artifacts["model"], X_test, artifacts["feat_scaler"], bundle["target_idx"])
    # absolute mode: tgt_scaler 는 raw target 분포에 fit (1-feature)
    tgt_scaler = artifacts["tgt_scaler"]
    y_pred = tgt_scaler.inverse_transform(pred_norm.reshape(-1, 1)).reshape(-1).astype(np.float32)
    y_pred = np.maximum(y_pred, 0.0)

    y_naive = _compute_naive_lag1(bundle, train_end, val_end)
    y_train_actuals = _compute_train_actuals(bundle, train_end)
    return y_true, y_pred, y_naive, y_train_actuals


def _evaluate_v3() -> EvaluatorReturn:
    """v3 absolute mode TCN — feature_cols 가 v2 와 다르므로 metadata 에서 동적 로드."""
    from models.living_pop_forecast.train import WEIGHTS_DIR

    metadata_path = WEIGHTS_DIR / "living_pop_metadata_v3.json"
    artifacts = _load_tcn_artifacts(metadata_path)
    metadata = artifacts["metadata"]

    feature_cols = list(metadata["feature_columns"])
    bundle = _build_tcn_sequences(feature_cols=feature_cols, mode="absolute")

    n = len(bundle["y_raw"])
    train_end, val_end = _split_indices(n)
    X_test = bundle["X_raw"][val_end:]
    y_true = bundle["y_raw"][val_end:].astype(np.float32)

    pred_norm = _predict_tcn_test(artifacts["model"], X_test, artifacts["feat_scaler"], bundle["target_idx"])
    tgt_scaler = artifacts["tgt_scaler"]
    y_pred = tgt_scaler.inverse_transform(pred_norm.reshape(-1, 1)).reshape(-1).astype(np.float32)
    y_pred = np.maximum(y_pred, 0.0)

    y_naive = _compute_naive_lag1(bundle, train_end, val_end)
    y_train_actuals = _compute_train_actuals(bundle, train_end)
    return y_true, y_pred, y_naive, y_train_actuals


def _evaluate_v4_residual() -> EvaluatorReturn:
    """v4_residual: y_pred = last_value_actual + delta_actual."""
    from models.living_pop_forecast.train import WEIGHTS_DIR

    metadata_path = WEIGHTS_DIR / "living_pop_metadata_v4_residual.json"
    artifacts = _load_tcn_artifacts(metadata_path)
    metadata = artifacts["metadata"]

    feature_cols = list(metadata["feature_columns"])
    bundle = _build_tcn_sequences(feature_cols=feature_cols, mode="residual")

    n = len(bundle["y_raw"])
    train_end, val_end = _split_indices(n)
    X_test = bundle["X_raw"][val_end:]
    y_true = bundle["y_raw"][val_end:].astype(np.float32)
    last_value = bundle["last_value_raw"][val_end:].astype(np.float32)

    pred_norm = _predict_tcn_test(artifacts["model"], X_test, artifacts["feat_scaler"], bundle["target_idx"])
    # residual: tgt_scaler 는 delta 분포에 fit (1-feature)
    tgt_scaler = artifacts["tgt_scaler"]
    delta_actual = tgt_scaler.inverse_transform(pred_norm.reshape(-1, 1)).reshape(-1).astype(np.float32)
    y_pred = np.maximum(last_value + delta_actual, 0.0)

    y_naive = _compute_naive_lag1(bundle, train_end, val_end)
    y_train_actuals = _compute_train_actuals(bundle, train_end)
    return y_true, y_pred, y_naive, y_train_actuals


def _evaluate_residual_with_group_features(version: str) -> EvaluatorReturn:
    """v5 group-features residual evaluator (full / rel_only 공용).

    metadata 의 add_group_features / train_end_quarter / feature_columns 그대로 사용.
    """
    from models.living_pop_forecast.train import WEIGHTS_DIR

    metadata_path = WEIGHTS_DIR / f"living_pop_metadata_{version}.json"
    artifacts = _load_tcn_artifacts(metadata_path)
    metadata = artifacts["metadata"]

    feature_cols = list(metadata["feature_columns"])
    add_group = bool(metadata.get("add_group_features", False))
    train_end_quarter = metadata.get("train_end_quarter")
    bundle = _build_tcn_sequences(
        feature_cols=feature_cols,
        mode="residual",
        add_group_features=add_group,
        train_end_quarter=train_end_quarter,
    )

    n = len(bundle["y_raw"])
    train_end, val_end = _split_indices(n)
    X_test = bundle["X_raw"][val_end:]
    y_true = bundle["y_raw"][val_end:].astype(np.float32)
    last_value = bundle["last_value_raw"][val_end:].astype(np.float32)

    pred_norm = _predict_tcn_test(artifacts["model"], X_test, artifacts["feat_scaler"], bundle["target_idx"])
    tgt_scaler = artifacts["tgt_scaler"]
    delta_actual = tgt_scaler.inverse_transform(pred_norm.reshape(-1, 1)).reshape(-1).astype(np.float32)
    y_pred = np.maximum(last_value + delta_actual, 0.0)

    y_naive = _compute_naive_lag1(bundle, train_end, val_end)
    y_train_actuals = _compute_train_actuals(bundle, train_end)
    return y_true, y_pred, y_naive, y_train_actuals


def _evaluate_v5_group_residual() -> EvaluatorReturn:
    """v5_group_residual: full group features (group_mean + group_relative)."""
    return _evaluate_residual_with_group_features("v5_group_residual")


def _evaluate_v5_group_rel_only() -> EvaluatorReturn:
    """v5_group_rel_only: group_relative 만 (재시도, group_mean 제거)."""
    return _evaluate_residual_with_group_features("v5_group_rel_only")


def _evaluate_v5_group_decomp() -> EvaluatorReturn:
    """v5_group_decomp (option B): explicit decomposition.

    학습: target = (y - group_mean) / group_mean.
    추론: y_pred = group_mean × (1 + ratio_actual).
    """
    from models.living_pop_forecast.train import WEIGHTS_DIR

    metadata_path = WEIGHTS_DIR / "living_pop_metadata_v5_group_decomp.json"
    artifacts = _load_tcn_artifacts(metadata_path)
    metadata = artifacts["metadata"]

    feature_cols = list(metadata["feature_columns"])
    train_end_quarter = metadata.get("train_end_quarter")
    bundle = _build_tcn_sequences(
        feature_cols=feature_cols,
        mode="group_residual",
        add_group_features=True,
        train_end_quarter=train_end_quarter,
    )

    n = len(bundle["y_raw"])
    train_end, val_end = _split_indices(n)
    X_test = bundle["X_raw"][val_end:]
    y_true = bundle["y_raw"][val_end:].astype(np.float32)
    if bundle.get("group_mean_raw") is None:
        raise RuntimeError("v5_group_decomp 평가에는 group_mean 컬럼 필요 — bundle 누락")
    group_mean_test = bundle["group_mean_raw"][val_end:].astype(np.float32)

    pred_norm = _predict_tcn_test(artifacts["model"], X_test, artifacts["feat_scaler"], bundle["target_idx"])
    tgt_scaler = artifacts["tgt_scaler"]
    ratio_actual = tgt_scaler.inverse_transform(pred_norm.reshape(-1, 1)).reshape(-1).astype(np.float32)
    y_pred = np.maximum(group_mean_test * (1.0 + ratio_actual), 0.0)

    y_naive = _compute_naive_lag1(bundle, train_end, val_end)
    y_train_actuals = _compute_train_actuals(bundle, train_end)
    return y_true, y_pred, y_naive, y_train_actuals


def _evaluate_arima() -> EvaluatorReturn:
    """ARIMA per-group baseline.

    train 분기 (시간순 70%) 로 그룹별 auto_arima fit → test 분기 forecast 추출.
    ``arima_baseline.run_evaluate()`` 와 같은 split 정의로 train→test 평가.

    참고: ARIMA 단위는 분기당 한 row (384 그룹 × test 분기 수) 라서 TCN 의 시퀀스
    수 (~1211) 와 다른 n_test 를 가진다. 학술 metric 정의 자체는 동일 단위에서 수행.
    """
    from models.living_pop_forecast.arima_baseline import (
        fit_arima_per_group,
        forecast_arima,
    )
    from models.living_pop_forecast.data_prep import (
        MAPO_DONG_CODES,
        TARGET_COL,
        _add_dong_one_hot,
        build_timeseries,
        load_living_population,
    )

    df = load_living_population()
    df = df[df["dong_code"].isin(MAPO_DONG_CODES)].copy()
    df = build_timeseries(df)
    df = _add_dong_one_hot(df)

    quarters_sorted = sorted(df["quarter"].unique().tolist())
    n_q = len(quarters_sorted)
    n_train = max(1, int(n_q * 0.70))
    n_val = max(1, int(n_q * 0.15))
    train_q = quarters_sorted[:n_train]
    val_q = quarters_sorted[n_train : n_train + n_val]
    test_q = quarters_sorted[n_train + n_val :]

    models = fit_arima_per_group(
        df,
        train_quarters=train_q,
        seasonal=True,
        m=4,
        target_col=TARGET_COL,
        progress_every=0,
    )

    y_true_all: list[float] = []
    y_pred_all: list[float] = []
    y_naive_all: list[float] = []
    y_train_pieces: list[np.ndarray] = []

    for (dong, tz), group in df.groupby(["dong_code", "time_zone"], sort=True):
        group = group.sort_values("quarter").reset_index(drop=True)
        train_block = group[group["quarter"].isin(train_q)]
        test_block = group[group["quarter"].isin(test_q)]
        if len(test_block) == 0 or len(train_block) == 0:
            continue
        n_steps = len(val_q) + len(test_q)
        forecast = forecast_arima(models, str(dong), int(tz), n_steps=n_steps)
        last_train_value = float(train_block[TARGET_COL].iloc[-1])
        if forecast is None or len(forecast) < n_steps:
            forecast = np.full(n_steps, last_train_value, dtype=float)
        test_pred = forecast[len(val_q) :][: len(test_block)]
        y_true_all.extend(test_block[TARGET_COL].tolist())
        y_pred_all.extend(test_pred.tolist())
        prev = last_train_value
        for actual in test_block[TARGET_COL].tolist():
            y_naive_all.append(prev)
            prev = actual
        y_train_pieces.append(train_block[TARGET_COL].to_numpy(dtype=np.float32))

    y_true = np.asarray(y_true_all, dtype=np.float32)
    y_pred = np.asarray(y_pred_all, dtype=np.float32)
    y_naive = np.asarray(y_naive_all, dtype=np.float32)
    y_train_actuals = np.concatenate(y_train_pieces, axis=0) if y_train_pieces else np.asarray([], dtype=np.float32)
    return y_true, y_pred, y_naive, y_train_actuals


# ---------------------------------------------------------------------------
# Plug-in registry
# ---------------------------------------------------------------------------


EVALUATORS = {
    "naive_lag1": _evaluate_naive_lag1,
    "naive_lag4_seasonal": _evaluate_naive_lag4_seasonal,
    "v2": _evaluate_v2,
    "v3": _evaluate_v3,
    "v4_residual": _evaluate_v4_residual,
    "v5_group_residual": _evaluate_v5_group_residual,
    "v5_group_rel_only": _evaluate_v5_group_rel_only,
    "v5_group_decomp": _evaluate_v5_group_decomp,
    "arima": _evaluate_arima,
}


# ---------------------------------------------------------------------------
# 결과 정리 / 출력
# ---------------------------------------------------------------------------


def _format_markdown_table(df: pd.DataFrame) -> str:
    """MASE 오름차순 정렬 (same-period) + MASE_in_sample 컬럼 포함 markdown 표."""
    df = df.copy().sort_values("MASE", ascending=True, na_position="last").reset_index(drop=True)
    has_in_sample = "MASE_in_sample" in df.columns
    headers = [
        "version",
        "n_test",
        "MAE",
        "RMSE",
        "NRMSE %",
        "MAPE %",
        "sMAPE %",
        "R²",
        "MASE",
    ]
    align = ["left", "right", "right", "right", "right", "right", "right", "right", "right"]
    if has_in_sample:
        headers.append("MASE_in_sample")
        align.append("right")

    def fmt_row(values: list[str]) -> str:
        return "| " + " | ".join(values) + " |"

    def fmt_int(v: float) -> str:
        return f"{int(round(v)):,}" if pd.notna(v) else "—"

    def fmt_pct(v: float) -> str:
        return f"{v:6.2f}" if pd.notna(v) else "—"

    def fmt_float(v: float, prec: int = 3) -> str:
        return f"{v:.{prec}f}" if pd.notna(v) else "—"

    rows: list[str] = []
    rows.append(fmt_row([h.ljust(14) if i == 0 else h.rjust(8) for i, h in enumerate(headers)]))
    rows.append(fmt_row([":---" if a == "left" else "---:" for a in align]))
    for _, r in df.iterrows():
        cells = [
            str(r["version"]).ljust(18),
            f"{int(r['n_test']):>6,}",
            f"{fmt_int(r['MAE']):>7}",
            f"{fmt_int(r['RMSE']):>7}",
            fmt_pct(r["NRMSE_pct"]),
            fmt_pct(r["MAPE_pct"]),
            fmt_pct(r["sMAPE_pct"]),
            fmt_float(r["R2"], 4),
            fmt_float(r["MASE"], 3),
        ]
        if has_in_sample:
            cells.append(fmt_float(r.get("MASE_in_sample", float("nan")), 3))
        rows.append(fmt_row(cells))
    return "\n".join(rows)


def _check_expected_mase(version: str, mase_value: float) -> str | None:
    """사전 보고된 MASE 와 비교 → 차이 시 warning 메시지 반환."""
    expected = EXPECTED_MASE.get(version)
    if expected is None or not np.isfinite(mase_value):
        return None
    diff = abs(mase_value - expected)
    if diff > MASE_TOLERANCE:
        return (
            f"WARNING [{version}] MASE 측정값 {mase_value:.3f} 가 사전 보고 {expected:.3f} 와 "
            f"|Δ|={diff:.3f} (>tol={MASE_TOLERANCE}) — split/scaler 가정 차이 점검 필요"
        )
    return None


# ---------------------------------------------------------------------------
# 메인 파이프라인
# ---------------------------------------------------------------------------


def run_evaluators(versions: list[str]) -> tuple[pd.DataFrame, list[str]]:
    """선택된 evaluator 호출 → (DataFrame, warnings).

    DataFrame columns: version, n_test, MAE, RMSE, NRMSE_pct, MAPE_pct,
    sMAPE_pct, R2, MASE, MASE_in_sample.

    - ``MASE`` : Same-period (M4 competition style) — test set 1-step naive MAE 분모.
    - ``MASE_in_sample`` : Hyndman & Koehler (2006) — train set 1-step naive MAE 분모.
    """
    rows: list[dict] = []
    warnings: list[str] = []
    for version in versions:
        if version not in EVALUATORS:
            warnings.append(f"WARNING 알 수 없는 version 무시: {version!r}")
            continue
        logger.info("[evaluate] %s 시작", version)
        try:
            result = EVALUATORS[version]()
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"WARNING [{version}] 평가 실패: {exc}")
            logger.exception("evaluator %s 실패", version)
            continue

        # 4-tuple 표준 — 구버전 evaluator 호환을 위해 길이 체크.
        if len(result) == 4:
            y_true, y_pred, y_naive, y_train_actuals = result
        elif len(result) == 3:  # backward compat
            y_true, y_pred, y_naive = result
            y_train_actuals = None
        else:
            warnings.append(f"WARNING [{version}] evaluator 가 예상치 못한 tuple 길이 반환: {len(result)}")
            continue

        metrics = compute_metrics(
            y_true,
            y_pred,
            y_naive=y_naive,
            y_train=y_train_actuals,
        )
        row = {
            "version": version,
            "n_test": int(len(y_true)),
            "MAE": float(metrics["MAE"]),
            "RMSE": float(metrics["RMSE"]),
            "NRMSE_pct": float(metrics["NRMSE_pct"]),
            "MAPE_pct": float(metrics["MAPE_pct"]),
            "sMAPE_pct": float(metrics["sMAPE_pct"]),
            "R2": float(metrics["R2"]),
            "MASE": float(metrics["MASE"]),
            "MASE_in_sample": float(metrics.get("MASE_in_sample", float("nan"))),
        }
        rows.append(row)
        logger.info(
            "[evaluate] %s 완료: n_test=%d, MAE=%.2f, RMSE=%.2f, MASE=%.3f, MASE_in_sample=%.3f",
            version,
            row["n_test"],
            row["MAE"],
            row["RMSE"],
            row["MASE"],
            row["MASE_in_sample"],
        )
        msg = _check_expected_mase(version, row["MASE"])
        if msg:
            warnings.append(msg)

    df = pd.DataFrame(
        rows,
        columns=[
            "version",
            "n_test",
            "MAE",
            "RMSE",
            "NRMSE_pct",
            "MAPE_pct",
            "sMAPE_pct",
            "R2",
            "MASE",
            "MASE_in_sample",
        ],
    )
    return df, warnings


def _resolve_versions(versions_arg: str | None, filter_arg: str | None) -> list[str]:
    """--versions 우선, 없으면 default. --filter 는 부분 매치."""
    if versions_arg:
        names = [v.strip() for v in versions_arg.split(",") if v.strip()]
    else:
        names = list(DEFAULT_VERSIONS)
    if filter_arg:
        f = filter_arg.lower()
        names = [v for v in names if f in v.lower()]
    return names


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="모든 D 모델 변형 통합 평가")
    parser.add_argument(
        "--versions",
        type=str,
        default=None,
        help="콤마 구분 evaluator 명단 (예: naive_lag1,v2). 미지정 시 모두 평가",
    )
    parser.add_argument(
        "--filter",
        type=str,
        default=None,
        help="이름 부분 매치 (예: --filter v4 → v4_residual 만)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_CSV_PATH),
        help=f"CSV 출력 경로 (default: {DEFAULT_CSV_PATH})",
    )
    parser.add_argument(
        "--no-markdown",
        action="store_true",
        help="markdown 표 stdout 출력 비활성",
    )
    parser.add_argument(
        "--update-report",
        action="store_true",
        help="docs/abm-simulation/living-pop-forecast-v2-vs-v3-report.md § 10.2 표 갱신 (수동 옵션)",
    )
    args = parser.parse_args(argv)

    versions = _resolve_versions(args.versions, args.filter)
    if not versions:
        logger.error("평가할 evaluator 가 없습니다.")
        return 2

    logger.info("평가 대상: %s", versions)

    df, warnings = run_evaluators(versions)

    # CSV 저장
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, float_format="%.6f")
    logger.info("CSV 저장: %s (%d rows)", out_path, len(df))

    # Markdown 표
    if not args.no_markdown and not df.empty:
        table = _format_markdown_table(df)
        print()
        print(table)
        print()

    for w in warnings:
        print(w, file=sys.stderr)

    if args.update_report:
        try:
            _update_report_table(df)
            logger.info("리포트 갱신 완료")
        except Exception as exc:  # noqa: BLE001
            logger.warning("리포트 갱신 실패: %s", exc)

    return 0


# ---------------------------------------------------------------------------
# 리포트 갱신 헬퍼 (D 옵션)
# ---------------------------------------------------------------------------


REPORT_PATH = PROJECT_ROOT / "docs" / "abm-simulation" / "living-pop-forecast-v2-vs-v3-report.md"


def _update_report_table(df: pd.DataFrame) -> None:
    """리포트 § 10.2 의 표 부분을 evaluate_all 결과로 교체.

    --update-report 플래그가 있을 때만 호출. 자동 덮어쓰기 X.
    """
    if not REPORT_PATH.exists():
        raise FileNotFoundError(f"리포트 미발견: {REPORT_PATH}")
    text = REPORT_PATH.read_text(encoding="utf-8")
    table = _format_markdown_table(df)
    marker_start = "<!-- evaluate_all:start -->"
    marker_end = "<!-- evaluate_all:end -->"
    if marker_start in text and marker_end in text:
        before, _, rest = text.partition(marker_start)
        _, _, after = rest.partition(marker_end)
        new = f"{before}{marker_start}\n{table}\n{marker_end}{after}"
        REPORT_PATH.write_text(new, encoding="utf-8")
    else:
        # marker 없으면 안전하게 append (덮어쓰기 X)
        REPORT_PATH.write_text(
            text + f"\n\n{marker_start}\n{table}\n{marker_end}\n",
            encoding="utf-8",
        )


__all__ = [
    "DEFAULT_CSV_PATH",
    "DEFAULT_VERSIONS",
    "EVALUATORS",
    "main",
    "run_evaluators",
]


if __name__ == "__main__":
    raise SystemExit(main())
