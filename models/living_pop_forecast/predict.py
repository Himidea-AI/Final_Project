"""
생활인구 유동인구 TCN 추론 — 특정 동의 향후 n분기 시간대별 유동인구 예측

Usage:
    from models.living_pop_forecast.predict import predict, predict_peak

    # 특정 동의 특정 시간대 예측
    results = predict("합정동", time_zone=15, n_quarters=4)

    # 특정 동의 피크 시간 예측 (전체 시간대 중 최대값 시간대 반환)
    peak = predict_peak("합정동", n_quarters=4)

담당: B2 — 수지니
참조: models/tcn_forecast/predict.py (구조 동일)
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import torch

from models.tcn_forecast.model import TCNForecaster

from .data_prep import (
    DB_URL,
    POP_FEATURES,
    TARGET_COL,
    build_timeseries,
    load_living_population,
)
from .train import WEIGHTS_DIR, load_scalers

logger = logging.getLogger(__name__)

DEFAULT_PREDICT_CONFIG: dict = {
    "db_url": DB_URL,
    "csv_path": None,
    "weights_path": str(WEIGHTS_DIR / "living_pop_tcn.pt"),
    "scalers_path": str(WEIGHTS_DIR / "living_pop_scalers.pkl"),
    "window_size": 8,
    "n_channels": 64,
    "kernel_size": 2,
    "dilations": [1, 2, 4],
    "dropout": 0.2,
    "target_col": TARGET_COL,
    "feature_cols": None,
    "confidence_z": 1.96,
}


# 모듈 레벨 캐시 — predict_peak가 24×n_quarters forward pass라 시뮬마다 모델
# 새로 로딩하면 latency 크게 누적됨. weights_path 기반 키로 캐시. 가중치 파일 변경 시 서버 재시작 필요.
_MODEL_CACHE: dict[str, tuple[TCNForecaster, object, object]] = {}


def _load_model_and_scalers(cfg: dict) -> tuple[TCNForecaster, object, object]:
    weights_path = Path(cfg["weights_path"])
    scalers_path = Path(cfg["scalers_path"])

    cache_key = f"{weights_path}::{scalers_path}"
    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]

    if not weights_path.exists():
        raise FileNotFoundError(
            f"모델 가중치 없음: {weights_path}\n먼저 학습을 실행하세요:\n  python -m models.living_pop_forecast.train"
        )
    if not scalers_path.exists():
        raise FileNotFoundError(f"스케일러 파일 없음: {scalers_path}")

    feat_scaler, tgt_scaler = load_scalers(scalers_path)
    input_size = len(feat_scaler.scale_)

    model = TCNForecaster(
        input_size=input_size,
        n_channels=cfg["n_channels"],
        kernel_size=cfg["kernel_size"],
        dilations=cfg["dilations"],
        dropout=cfg["dropout"],
    )
    model.load_weights(weights_path)
    model.eval()

    _MODEL_CACHE[cache_key] = (model, feat_scaler, tgt_scaler)
    return _MODEL_CACHE[cache_key]


def _autoregressive_predict(
    model: TCNForecaster,
    seq: np.ndarray,
    feat_scaler: object,
    tgt_scaler: object,
    feature_cols: list[str],
    target_col: str,
    n_quarters: int,
    confidence_z: float,
    device: torch.device,
) -> list[dict]:
    """자기회귀 방식으로 n_quarters 예측 후 결과 반환."""
    try:
        target_idx = feature_cols.index(target_col)
    except ValueError:
        target_idx = 0

    predictions: list[float] = []
    with torch.no_grad():
        current_seq = torch.from_numpy(seq).unsqueeze(0).to(device)
        for _ in range(n_quarters):
            pred_scaled = model(current_seq).cpu().numpy().flatten()[0]
            pred_val = float(tgt_scaler.inverse_transform([[pred_scaled]])[0][0])
            pred_val = max(0.0, pred_val)
            predictions.append(pred_val)

            new_step = current_seq[0, -1, :].clone()
            new_step[target_idx] = float(pred_scaled)
            current_seq = torch.cat([current_seq[:, 1:, :], new_step.unsqueeze(0).unsqueeze(0)], dim=1)

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


def predict(
    dong_name: str,
    time_zone: int,
    n_quarters: int = 4,
    config: dict | None = None,
) -> list[dict]:
    """특정 동의 특정 시간대 향후 n분기 유동인구를 예측한다.

    Parameters
    ----------
    dong_name : str
        행정동명 (예: '합정동', '연남동').
    time_zone : int
        시간대 (0~23).
    n_quarters : int
        예측 분기 수 (기본 4 = 1년).
    config : dict, optional
        설정 오버라이드.

    Returns
    -------
    list[dict]
        각 원소: {
            "quarter_offset": int,
            "predicted_pop": float,   # 예측 유동인구
            "confidence_lower": float,
            "confidence_upper": float,
        }
    """
    cfg = {**DEFAULT_PREDICT_CONFIG, **(config or {})}
    device = torch.device("cpu")

    model, feat_scaler, tgt_scaler = _load_model_and_scalers(cfg)
    model.to(device)

    df = load_living_population(db_url=cfg["db_url"], csv_path=cfg.get("csv_path"))
    df = build_timeseries(df)

    feature_cols = cfg.get("feature_cols") or [c for c in POP_FEATURES if c in df.columns]
    target_col = cfg["target_col"]
    window_size = cfg["window_size"]

    group = df[(df["dong_name"] == dong_name) & (df["time_zone"] == time_zone)].sort_values("quarter")

    if group.empty:
        available = df["dong_name"].unique().tolist()
        raise ValueError(f"데이터 없음: dong_name='{dong_name}', time_zone={time_zone}\n사용 가능한 동: {available}")
    if len(group) < window_size:
        raise ValueError(f"과거 데이터 부족: {len(group)}분기 (최소 {window_size}분기 필요)")

    actual_features = [c for c in feature_cols if c in group.columns]
    seq = feat_scaler.transform(group[actual_features].values[-window_size:].astype(np.float32))

    return _autoregressive_predict(
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


def predict_peak(
    dong_name: str,
    n_quarters: int = 4,
    config: dict | None = None,
) -> list[dict]:
    """특정 동의 향후 n분기 피크 시간대와 유동인구를 예측한다.

    24시간대를 한꺼번에 예측하고 분기별로 최대값 시간대를 반환한다.
    모델/데이터는 한 번만 로드한 뒤 24시간대에 재사용한다.

    Parameters
    ----------
    dong_name : str
        행정동명 (예: '합정동').
    n_quarters : int
        예측 분기 수.
    config : dict, optional
        설정 오버라이드.

    Returns
    -------
    list[dict]
        각 원소: {
            "quarter_offset": int,
            "peak_time_zone": int,   # 피크 시간대 (0~23)
            "peak_pop": float,       # 피크 시간대 예측 유동인구
            "all_hours": list[dict], # 24시간 전체 예측
        }
    """
    cfg = {**DEFAULT_PREDICT_CONFIG, **(config or {})}
    device = torch.device("cpu")

    # 모델·스케일러·데이터를 한 번만 로드 (24시간대 공용)
    model, feat_scaler, tgt_scaler = _load_model_and_scalers(cfg)
    model.to(device)

    df = load_living_population(db_url=cfg["db_url"], csv_path=cfg.get("csv_path"))
    df = build_timeseries(df)

    feature_cols = cfg.get("feature_cols") or [c for c in POP_FEATURES if c in df.columns]
    target_col = cfg["target_col"]
    window_size = cfg["window_size"]

    if dong_name not in df["dong_name"].values:
        available = df["dong_name"].unique().tolist()
        raise ValueError(f"데이터 없음: dong_name='{dong_name}'\n사용 가능한 동: {available}")

    # 24시간대 예측 수행
    all_tz_preds: dict[int, list[dict]] = {}
    for tz in range(24):
        group = df[(df["dong_name"] == dong_name) & (df["time_zone"] == tz)].sort_values("quarter")
        if len(group) < window_size:
            continue
        actual_features = [c for c in feature_cols if c in group.columns]
        seq = feat_scaler.transform(group[actual_features].values[-window_size:].astype(np.float32))
        all_tz_preds[tz] = _autoregressive_predict(
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

    # 분기별 피크 시간대 산출
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
