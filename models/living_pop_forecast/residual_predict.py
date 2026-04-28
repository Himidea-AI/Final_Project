"""Residual model 추론: y_pred = last_value + denormalize(model(x))."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from models.tcn_forecast.model import TCNForecaster

from .data_prep import (
    ALL_FEATURES,
    DB_URL,
    POP_FEATURES,
    TARGET_COL,
    _add_dong_one_hot,
    build_timeseries,
    load_living_population,
)
from .train import WEIGHTS_DIR, load_scalers

logger = logging.getLogger(__name__)

WEIGHTS_PATH_V4 = WEIGHTS_DIR / "living_pop_tcn_v4_residual.pt"
SCALERS_PATH_V4 = WEIGHTS_DIR / "living_pop_scalers_v4_residual.pkl"
METADATA_PATH_V4 = WEIGHTS_DIR / "living_pop_metadata_v4_residual.json"


DEFAULT_RESIDUAL_PREDICT_CONFIG: dict = {
    "db_url": DB_URL,
    "csv_path": None,
    "weights_path": None,
    "scalers_path": None,
    "metadata_path": None,
    "window_size": 8,
    "n_channels": 64,
    "kernel_size": 2,
    "dilations": [1, 2, 4],
    "dropout": 0.2,
    "target_col": TARGET_COL,
    "feature_cols": None,
    "confidence_z": 1.96,
}


# 모듈 레벨 캐시 (predict.py 와 동일 패턴)
_RES_MODEL_CACHE: dict[str, tuple[TCNForecaster, object, object, dict]] = {}
_RES_DF_CACHE: dict[str, pd.DataFrame] = {}


def _cached_load_living_pop(db_url: str, csv_path: str | None = None) -> pd.DataFrame:
    cache_key = f"{db_url}::{csv_path or ''}"
    if cache_key in _RES_DF_CACHE:
        return _RES_DF_CACHE[cache_key]
    df = load_living_population(db_url=db_url, csv_path=csv_path)
    _RES_DF_CACHE[cache_key] = df
    return df


def _resolve_residual_paths(cfg: dict) -> tuple[Path, Path, Path]:
    weights_path = Path(cfg["weights_path"]) if cfg.get("weights_path") else WEIGHTS_PATH_V4
    scalers_path = Path(cfg["scalers_path"]) if cfg.get("scalers_path") else SCALERS_PATH_V4
    metadata_path = Path(cfg["metadata_path"]) if cfg.get("metadata_path") else METADATA_PATH_V4
    if not weights_path.exists():
        raise RuntimeError(
            f"residual 가중치 미발견: {weights_path}\n"
            f"먼저 학습을 실행하세요:\n"
            f"  python -m models.living_pop_forecast.residual_train --epochs 100 --patience 15 --seed 2026"
        )
    if not scalers_path.exists():
        raise RuntimeError(f"residual scaler 미발견: {scalers_path}")
    if not metadata_path.exists():
        raise RuntimeError(f"residual metadata 미발견: {metadata_path}")
    return weights_path, scalers_path, metadata_path


def _load_residual_model(cfg: dict) -> tuple[TCNForecaster, object, object, dict]:
    weights_path, scalers_path, metadata_path = _resolve_residual_paths(cfg)
    cache_key = f"{weights_path}::{scalers_path}"
    if cache_key in _RES_MODEL_CACHE:
        return _RES_MODEL_CACHE[cache_key]

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("mode") != "residual":
        raise RuntimeError(f"metadata mode 불일치: 기대 'residual', 실제 {metadata.get('mode')!r}")

    feat_scaler, tgt_scaler = load_scalers(scalers_path)
    input_size = len(feat_scaler.scale_)

    model = TCNForecaster(
        input_size=input_size,
        n_channels=int(metadata.get("n_channels", cfg["n_channels"])),
        kernel_size=int(metadata.get("kernel_size", cfg["kernel_size"])),
        dilations=list(metadata.get("dilations", cfg["dilations"])),
        dropout=float(metadata.get("dropout", cfg["dropout"])),
    )
    model.load_weights(weights_path)
    model.eval()
    _RES_MODEL_CACHE[cache_key] = (model, feat_scaler, tgt_scaler, metadata)
    return _RES_MODEL_CACHE[cache_key]


def _last_value_from_seq(
    seq_norm: np.ndarray,
    feat_scaler: object,
    target_idx: int,
) -> float:
    """정규화된 window 의 마지막 step → 실제 인구 단위 last_value 복원."""
    last_norm = float(seq_norm[-1, target_idx])
    # MinMaxScaler 는 모든 피처에 대해 fit. inverse 는 동일 차원 입력 필요 →
    # target 차원만 추출하기 위해 zero vector 에 last_norm 채워서 inverse 후 [target_idx] 만 사용.
    n_feat = len(feat_scaler.scale_)  # type: ignore[attr-defined]
    placeholder = np.zeros((1, n_feat), dtype=np.float32)
    placeholder[0, target_idx] = last_norm
    inv = feat_scaler.inverse_transform(placeholder)  # type: ignore[attr-defined]
    return float(inv[0, target_idx])


def _autoregressive_residual_predict(
    model: TCNForecaster,
    seq_norm: np.ndarray,
    feat_scaler: object,
    tgt_scaler: object,
    feature_cols: list[str],
    target_col: str,
    n_quarters: int,
    confidence_z: float,
    device: torch.device,
) -> list[dict]:
    """Residual model 자기회귀 추론.

    각 step:
        delta_norm = model(window)
        delta_actual = tgt_scaler.inverse_transform(delta_norm)
        last_value = inverse(window[-1, target_idx])  (단, autoregressive 에서는 직전 prediction 사용)
        y_pred = last_value + delta_actual
    """
    try:
        target_idx = feature_cols.index(target_col)
    except ValueError as exc:
        raise ValueError(
            f"target_col '{target_col}' 이 feature_cols 에 없습니다. "
            f"feature_cols={feature_cols[:5]}... (총 {len(feature_cols)}개)."
        ) from exc

    predictions: list[float] = []
    current_seq = torch.from_numpy(seq_norm.copy()).unsqueeze(0).to(device)
    last_value_actual = _last_value_from_seq(seq_norm, feat_scaler, target_idx)

    with torch.no_grad():
        for _ in range(n_quarters):
            delta_norm = model(current_seq).cpu().numpy().flatten()[0]
            delta_actual = float(tgt_scaler.inverse_transform([[delta_norm]])[0][0])
            y_pred = max(0.0, last_value_actual + delta_actual)
            predictions.append(y_pred)

            # window roll: 다음 step 의 last_value = y_pred
            # current_seq 는 normalized 상태이므로 y_pred 를 feat_scaler 로 다시 normalize.
            # MinMaxScaler 는 element-wise 라 target 차원만 변환 가능: (y - min)/(max-min)
            scale = float(feat_scaler.scale_[target_idx])  # type: ignore[attr-defined]
            mn = float(feat_scaler.min_[target_idx])  # type: ignore[attr-defined]
            # MinMaxScaler.transform: X_scaled = X * scale + min_  (sklearn 내부식)
            y_pred_norm = float(y_pred * scale + mn)

            new_step = current_seq[0, -1, :].clone()
            new_step[target_idx] = y_pred_norm
            current_seq = torch.cat([current_seq[:, 1:, :], new_step.unsqueeze(0).unsqueeze(0)], dim=1)
            last_value_actual = y_pred

    results: list[dict] = []
    for i, pop in enumerate(predictions):
        uncertainty = min(0.03 * (i + 1), 0.25)
        margin = pop * uncertainty * confidence_z
        results.append(
            {
                "quarter_offset": i + 1,
                "predicted_pop": round(pop, 0),
                "confidence_lower": round(max(0.0, pop - margin), 0),
                "confidence_upper": round(pop + margin, 0),
            }
        )
    return results


def _build_predict_seq(
    df: pd.DataFrame,
    dong_name: str,
    time_zone: int,
    feature_cols: list[str],
    feat_scaler: object,
    window_size: int,
    use_dong_one_hot: bool,
) -> tuple[np.ndarray, list[str]]:
    group = df[(df["dong_name"] == dong_name) & (df["time_zone"] == time_zone)].sort_values("quarter")
    if group.empty:
        available = df["dong_name"].unique().tolist()
        raise ValueError(f"데이터 없음: dong_name='{dong_name}', time_zone={time_zone}\n사용 가능한 동: {available}")
    if len(group) < window_size:
        raise ValueError(f"과거 데이터 부족: {len(group)}분기 (최소 {window_size}분기 필요)")

    if use_dong_one_hot:
        group = _add_dong_one_hot(group)
    actual_features = [c for c in feature_cols if c in group.columns]
    seq = feat_scaler.transform(group[actual_features].values[-window_size:].astype(np.float32))  # type: ignore[attr-defined]
    return seq, actual_features


def predict_residual(
    dong_name: str,
    time_zone: int,
    n_quarters: int = 4,
    config: dict | None = None,
) -> list[dict]:
    """Residual model 단일 시간대 추론."""
    cfg = {**DEFAULT_RESIDUAL_PREDICT_CONFIG, **(config or {})}
    device = torch.device("cpu")
    model, feat_scaler, tgt_scaler, metadata = _load_residual_model(cfg)
    model.to(device)

    df = _cached_load_living_pop(cfg["db_url"], cfg.get("csv_path"))
    add_group_features = bool(metadata.get("add_group_features", False))
    train_end_quarter = metadata.get("train_end_quarter")
    df = build_timeseries(df, add_group_features=add_group_features, train_end_quarter=train_end_quarter)

    target_col = cfg["target_col"]
    window_size = cfg["window_size"]

    feature_cols = cfg.get("feature_cols") or metadata.get("feature_columns") or ALL_FEATURES
    use_dong_one_hot = len(feature_cols) == len(ALL_FEATURES) or "dong_11440555" in feature_cols
    if not use_dong_one_hot:
        feature_cols = [c for c in POP_FEATURES if c in df.columns]

    seq, actual_features = _build_predict_seq(
        df, dong_name, time_zone, feature_cols, feat_scaler, window_size, use_dong_one_hot
    )

    return _autoregressive_residual_predict(
        model,
        seq,
        feat_scaler,
        tgt_scaler,
        actual_features,
        target_col,
        n_quarters,
        cfg["confidence_z"],
        device,
    )


def predict_peak_residual(
    dong_name: str,
    n_quarters: int = 4,
    config: dict | None = None,
) -> list[dict]:
    """Residual model 24시간 전체 예측 후 분기별 피크 시간대 반환.

    반환 형식은 predict.py.predict_peak() 와 동일 (backend 호환).
    """
    cfg = {**DEFAULT_RESIDUAL_PREDICT_CONFIG, **(config or {})}
    device = torch.device("cpu")
    model, feat_scaler, tgt_scaler, metadata = _load_residual_model(cfg)
    model.to(device)

    df = _cached_load_living_pop(cfg["db_url"], cfg.get("csv_path"))
    add_group_features = bool(metadata.get("add_group_features", False))
    train_end_quarter = metadata.get("train_end_quarter")
    df = build_timeseries(df, add_group_features=add_group_features, train_end_quarter=train_end_quarter)

    target_col = cfg["target_col"]
    window_size = cfg["window_size"]

    feature_cols = cfg.get("feature_cols") or metadata.get("feature_columns") or ALL_FEATURES
    use_dong_one_hot = len(feature_cols) == len(ALL_FEATURES) or "dong_11440555" in feature_cols
    if not use_dong_one_hot:
        feature_cols = [c for c in POP_FEATURES if c in df.columns]

    if dong_name not in df["dong_name"].values:
        available = df["dong_name"].unique().tolist()
        raise ValueError(f"데이터 없음: dong_name='{dong_name}'\n사용 가능한 동: {available}")

    all_tz_preds: dict[int, list[dict]] = {}
    for tz in range(24):
        try:
            seq, actual_features = _build_predict_seq(
                df, dong_name, tz, feature_cols, feat_scaler, window_size, use_dong_one_hot
            )
        except ValueError:
            continue
        all_tz_preds[tz] = _autoregressive_residual_predict(
            model,
            seq,
            feat_scaler,
            tgt_scaler,
            actual_features,
            target_col,
            n_quarters,
            cfg["confidence_z"],
            device,
        )

    if not all_tz_preds:
        raise ValueError(f"'{dong_name}' 예측 가능한 시간대가 없습니다.")

    results: list[dict] = []
    for q_idx in range(n_quarters):
        hourly = [
            {
                "time_zone": tz,
                "predicted_pop": all_tz_preds[tz][q_idx]["predicted_pop"],
                "confidence_lower": all_tz_preds[tz][q_idx]["confidence_lower"],
                "confidence_upper": all_tz_preds[tz][q_idx]["confidence_upper"],
            }
            for tz in sorted(all_tz_preds)
        ]
        peak = max(hourly, key=lambda x: x["predicted_pop"])
        results.append(
            {
                "quarter_offset": q_idx + 1,
                "peak_time_zone": peak["time_zone"],
                "peak_pop": peak["predicted_pop"],
                "all_hours": hourly,
            }
        )
    return results


__all__ = [
    "predict_residual",
    "predict_peak_residual",
    "WEIGHTS_PATH_V4",
    "SCALERS_PATH_V4",
    "METADATA_PATH_V4",
]
