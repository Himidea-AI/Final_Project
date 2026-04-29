"""
생활인구 유동인구 D 모델 추론 — 특정 동의 향후 n분기 시간대별 유동인구 예측.

Production status (2026-04-28):
    학술 평가 6 라운드 결과 v2 / v3 / v4_residual / v5 (3 변형) / ARIMA / v6 / v7
    모두 naive baseline (lag-1) 을 능가하지 못해 production endpoint 는 naive 채택.

    - predict_peak() : naive baseline (lag-1) 사용 — backend 에서 호출하는 핵심 함수.
                      기존 v2 TCN 가중치 로딩 로직은 archive (deprecated) 처리.
    - predict()      : v2 TCN 추론 (legacy) — backend 미사용. 학술 비교용으로 보존.
                      _v2_predict_legacy 로 위임.

    가중치 파일 (v2/v4_residual/v7_daily_residual) 은 reference only 로 보존.
    naive 정확도 (분기 lag-1): MAE 665, MAPE 2.62%, R² 0.9964.

Usage:
    from models.living_pop_forecast.predict import predict, predict_peak

    # 특정 동의 피크 시간 예측 (24h 모두 반환, naive baseline)
    peak = predict_peak("합정동", n_quarters=4)

    # 특정 동의 특정 시간대 v2 TCN legacy (학술 비교용)
    results = predict("합정동", time_zone=15, n_quarters=4)

담당: B2 — 수지니
참조: models/tcn_forecast/predict.py (구조 동일)
"""

from __future__ import annotations

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

# 가중치 경로 — v2 (dong_one_hot 포함, input_size=21)가 표준.
# v1 (input_size=5)은 archive 용도로만 보존, 추론에는 사용하지 않음.
WEIGHTS_PATH_V2 = WEIGHTS_DIR / "living_pop_tcn_v2.pt"
WEIGHTS_PATH_V1 = WEIGHTS_DIR / "living_pop_tcn.pt"
SCALERS_PATH_V2 = WEIGHTS_DIR / "living_pop_scalers_v2.pkl"
SCALERS_PATH_V1 = WEIGHTS_DIR / "living_pop_scalers.pkl"


def _resolve_weights_path() -> Path:
    """v2 가중치 (dong_one_hot 포함) 경로를 반환한다.

    v2 가중치가 없으면 명확한 RuntimeError를 던진다 (옵션 B 정책).
    legacy v1 fallback은 의도적으로 비활성화 — input_size 불일치로
    인한 silent failure를 방지하기 위함.
    """
    if WEIGHTS_PATH_V2.exists():
        return WEIGHTS_PATH_V2
    raise RuntimeError(
        f"v2 가중치 미발견: {WEIGHTS_PATH_V2}\n"
        f"먼저 학습을 실행하세요:\n"
        f"  python -m models.living_pop_forecast.train --epochs 100 --patience 15 --seed 2026"
    )


def _resolve_scalers_path() -> Path:
    """v2 스케일러 경로를 반환한다.

    v2 스케일러가 없으면 명확한 RuntimeError를 던진다 (옵션 B 정책 일관 적용).
    legacy v1 fallback은 의도적으로 비활성화 — v1 스케일러는 input_size=5 이지만
    v2 가중치는 21차원이라 weight shape mismatch 로 silent failure 발생 가능.
    """
    if SCALERS_PATH_V2.exists():
        return SCALERS_PATH_V2
    raise RuntimeError(
        f"v2 scaler 미발견: {SCALERS_PATH_V2}\n"
        f"v1 scaler({SCALERS_PATH_V1})는 input_size 5 이지만 v2 가중치는 21차원이라 호환 불가.\n"
        f"먼저 학습을 실행하세요:\n"
        f"  python -m models.living_pop_forecast.train --epochs 100 --patience 15 --seed 2026"
    )


DEFAULT_PREDICT_CONFIG: dict = {
    "db_url": DB_URL,
    "csv_path": None,
    # weights_path/scalers_path는 _load_model_and_scalers에서 _resolve_*_path()로 해결.
    # 명시 오버라이드가 필요한 호출자만 config에 전달.
    "weights_path": None,
    "scalers_path": None,
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

# DataFrame 캐시 — predict/predict_peak가 매번 living_population 풀스캔(마포 16동 × 24h × N분기)으로 DB I/O 누적.
# db_url 키로 결과 캐시. DB 데이터 변경 시 서버 재시작 필요.
_DF_CACHE: dict[str, pd.DataFrame] = {}


def _cached_load_living_pop(db_url: str, csv_path: str | None = None) -> pd.DataFrame:
    """load_living_population 결과를 모듈 레벨에 캐시. 두 번째 호출부터 0ms (DB I/O 없음)."""
    cache_key = f"{db_url}::{csv_path or ''}"
    if cache_key in _DF_CACHE:
        return _DF_CACHE[cache_key]
    df = load_living_population(db_url=db_url, csv_path=csv_path)
    _DF_CACHE[cache_key] = df
    return df


def _load_model_and_scalers(cfg: dict) -> tuple[TCNForecaster, object, object]:
    # config 명시 오버라이드 우선, 없으면 v2 우선 resolver.
    weights_path = Path(cfg["weights_path"]) if cfg.get("weights_path") else _resolve_weights_path()
    scalers_path = Path(cfg["scalers_path"]) if cfg.get("scalers_path") else _resolve_scalers_path()

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

    # v2 가중치는 input_size=21 (5 POP_FEATURES + 16 dong_one_hot).
    # 차원 불일치 시 추론 시퀀스 빌드와 모델이 어긋나 silent failure.
    expected_input_size = len(ALL_FEATURES)
    if input_size != expected_input_size:
        logger.warning(
            "스케일러 input_size=%d, 기대값=%d (v2 ALL_FEATURES). v1 legacy 스케일러일 수 있음 — v2로 재학습 권장.",
            input_size,
            expected_input_size,
        )

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
    except ValueError as exc:
        raise ValueError(
            f"target_col '{target_col}' 이 feature_cols 에 없습니다. "
            f"feature_cols={feature_cols[:5]}... (총 {len(feature_cols)}개). "
            f"autoregressive 추론에서 잘못된 인덱스를 사용할 수 있어 즉시 중단."
        ) from exc

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

    df = _cached_load_living_pop(cfg["db_url"], cfg.get("csv_path"))
    df = build_timeseries(df)

    target_col = cfg["target_col"]
    window_size = cfg["window_size"]

    # 스케일러 차원에 따라 feature_cols 결정 (v2=21 / legacy v1=5)
    scaler_dim = len(feat_scaler.scale_)
    use_dong_one_hot = scaler_dim == len(ALL_FEATURES)
    if cfg.get("feature_cols"):
        feature_cols = cfg["feature_cols"]
    elif use_dong_one_hot:
        feature_cols = ALL_FEATURES
    else:
        feature_cols = [c for c in POP_FEATURES if c in df.columns]

    group = df[(df["dong_name"] == dong_name) & (df["time_zone"] == time_zone)].sort_values("quarter")

    if group.empty:
        available = df["dong_name"].unique().tolist()
        raise ValueError(f"데이터 없음: dong_name='{dong_name}', time_zone={time_zone}\n사용 가능한 동: {available}")
    if len(group) < window_size:
        raise ValueError(f"과거 데이터 부족: {len(group)}분기 (최소 {window_size}분기 필요)")

    # v2 추론 시퀀스 빌드: dong_one_hot 16-dim 추가
    if use_dong_one_hot:
        group = _add_dong_one_hot(group)

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
    """특정 동의 향후 n분기 피크 시간대와 유동인구를 예측한다 (production naive baseline).

    학술 평가 6 라운드 (v2/v3/v4_residual/v5 변형/ARIMA/v6/v7) 모두 naive lag-1 을
    능가하지 못해 production 은 naive 채택. 본 함수는 backend 호환성을 위해
    시그니처는 유지하되 내부 구현을 ``predict_peak_naive`` 로 위임한다.

    Parameters
    ----------
    dong_name : str
        행정동명 (예: '합정동') 또는 dong_code (예: '11440680').
        backward compat 을 위해 두 형식 모두 허용.
    n_quarters : int
        예측 분기 수.
    config : dict, optional
        ``db_url`` / ``csv_path`` 오버라이드 (테스트용). 그 외 키는 무시됨.

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
    from .predict_naive import predict_peak_naive

    cfg = {**DEFAULT_PREDICT_CONFIG, **(config or {})}
    return predict_peak_naive(
        dong_name,
        n_quarters=n_quarters,
        db_url=cfg.get("db_url", DB_URL),
        csv_path=cfg.get("csv_path"),
    )


def _v2_predict_peak_legacy(
    dong_name: str,
    n_quarters: int = 4,
    config: dict | None = None,
) -> list[dict]:
    """[DEPRECATED — archive only] v2 TCN 24h × n_quarters 추론.

    학술 비교용 보존. naive baseline 미달로 production 미사용.
    """
    cfg = {**DEFAULT_PREDICT_CONFIG, **(config or {})}
    device = torch.device("cpu")

    # 모델·스케일러·데이터를 한 번만 로드 (24시간대 공용)
    model, feat_scaler, tgt_scaler = _load_model_and_scalers(cfg)
    model.to(device)

    df = _cached_load_living_pop(cfg["db_url"], cfg.get("csv_path"))
    df = build_timeseries(df)

    target_col = cfg["target_col"]
    window_size = cfg["window_size"]

    # 스케일러 차원에 따라 feature_cols 결정 (v2=21 / legacy v1=5)
    scaler_dim = len(feat_scaler.scale_)
    use_dong_one_hot = scaler_dim == len(ALL_FEATURES)
    if cfg.get("feature_cols"):
        feature_cols = cfg["feature_cols"]
    elif use_dong_one_hot:
        feature_cols = ALL_FEATURES
    else:
        feature_cols = [c for c in POP_FEATURES if c in df.columns]

    if dong_name not in df["dong_name"].values:
        available = df["dong_name"].unique().tolist()
        raise ValueError(f"데이터 없음: dong_name='{dong_name}'\n사용 가능한 동: {available}")

    # 24시간대 예측 수행
    all_tz_preds: dict[int, list[dict]] = {}
    for tz in range(24):
        group = df[(df["dong_name"] == dong_name) & (df["time_zone"] == tz)].sort_values("quarter")
        if len(group) < window_size:
            continue
        # v2 추론 시퀀스 빌드: dong_one_hot 16-dim 추가
        if use_dong_one_hot:
            group = _add_dong_one_hot(group)
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
