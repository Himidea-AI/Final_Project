"""
LSTM 시계열 추론 -- 특정 동x업종의 향후 n개월(분기) 매출 예측

파인튜닝된 모델 가중치를 로드하여 자기회귀(autoregressive) 방식으로
1분기씩 순차 예측한다.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import torch

from .data_prep import (
    ALL_FEATURES,
    DB_URL,
    build_timeseries,
    load_sales_data,
    load_store_data,
)
from .model import WEIGHTS_DIR, LSTMForecaster
from .train import load_scalers

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 기본 설정
# ---------------------------------------------------------------------------

DEFAULT_PREDICT_CONFIG: dict = {
    "db_url": DB_URL,
    "weights_path": str(WEIGHTS_DIR / "finetuned_mapo_v6b.pt"),
    "scalers_path": str(WEIGHTS_DIR / "finetune_v6b_scalers.pkl"),
    "window_size": 6,
    "hidden_size": 256,
    "num_layers": 2,
    "dropout": 0.2,
    "target_col": "monthly_sales",
    "feature_cols": None,
    "confidence_z": 1.96,  # 95% 신뢰구간
}


# ---------------------------------------------------------------------------
# 추론 함수
# ---------------------------------------------------------------------------


def predict(
    dong_code: str,
    industry_code: str,
    n_months: int = 4,
    config: dict | None = None,
) -> list[dict]:
    """특정 동x업종의 향후 n분기 매출을 예측한다.

    Parameters
    ----------
    dong_code : str
        행정동 코드 (예: '1144053').
    industry_code : str
        업종 코드 (예: 'CS100001').
    n_months : int
        예측할 분기 수 (기본 4 = 1년).
    config : dict, optional
        설정 오버라이드.

    Returns
    -------
    list[dict]
        각 원소: {
            "quarter_offset": int,  # 1, 2, 3, ...
            "predicted_sales": float,
            "confidence_lower": float,
            "confidence_upper": float,
        }
    """
    cfg = {**DEFAULT_PREDICT_CONFIG, **(config or {})}
    device = torch.device("cpu")  # 추론은 CPU에서 수행

    weights_path = Path(cfg["weights_path"])
    scalers_path = Path(cfg["scalers_path"])
    window_size = cfg["window_size"]
    target_col = cfg["target_col"]
    feature_cols = cfg.get("feature_cols")

    # 가중치 로드
    if not weights_path.exists():
        raise FileNotFoundError(
            f"모델 가중치를 찾을 수 없습니다: {weights_path}\n먼저 학습(pretrain/finetune)을 실행하세요."
        )

    # 스케일러 로드
    if not scalers_path.exists():
        raise FileNotFoundError(f"스케일러 파일을 찾을 수 없습니다: {scalers_path}")

    feat_scaler, tgt_scaler = load_scalers(scalers_path)

    # 피처 컬럼 결정
    if feature_cols is None:
        feature_cols = ALL_FEATURES
    input_size = len(feat_scaler.scale_)  # 스케일러에서 실제 피처 수 추론

    # 모델 로드
    model = LSTMForecaster(
        input_size=input_size,
        hidden_size=cfg["hidden_size"],
        num_layers=cfg["num_layers"],
        dropout=cfg["dropout"],
    )
    model.load_weights(weights_path)
    model.to(device)
    model.eval()

    # 과거 데이터 로드
    dong_prefix = dong_code[:5] if len(dong_code) >= 5 else dong_code
    sales_df = load_sales_data(db_url=cfg["db_url"], dong_prefix=dong_prefix)
    store_df = load_store_data(db_url=cfg["db_url"], dong_prefix=dong_prefix)

    # 해당 동x업종 시계열 추출
    ts = build_timeseries(sales_df, store_df)
    group = ts[(ts["dong_code"] == dong_code) & (ts["industry_code"] == industry_code)]

    if group.empty:
        raise ValueError(f"데이터가 없습니다: dong_code={dong_code}, industry_code={industry_code}")

    # 피처 컬럼 매칭
    actual_features = [c for c in feature_cols if c in group.columns]
    if not actual_features:
        raise ValueError("사용 가능한 피처 컬럼이 없습니다.")

    # 정렬 후 마지막 window_size 분기를 입력으로 사용
    group = group.sort_values("quarter")
    recent = group[actual_features].values.astype(np.float32)

    if len(recent) < window_size:
        raise ValueError(f"과거 데이터가 부족합니다: {len(recent)}분기 (최소 {window_size}분기 필요)")

    # 스케일링
    seq = feat_scaler.transform(recent[-window_size:])

    # 타겟 컬럼의 인덱스 (자기회귀 시 예측값을 다시 입력에 넣기 위해)
    try:
        target_idx = actual_features.index(target_col)
    except ValueError:
        target_idx = 0

    # 자기회귀 예측
    predictions: list[float] = []

    with torch.no_grad():
        current_seq = torch.from_numpy(seq).unsqueeze(0).to(device)  # (1, window, features)

        for _ in range(n_months):
            pred_scaled = model(current_seq)  # (1, 1)
            pred_val = pred_scaled.cpu().numpy().flatten()[0]

            # 역변환 (스케일러 → 로그 역변환)
            pred_log = tgt_scaler.inverse_transform([[pred_val]])[0][0]
            pred_original = float(np.expm1(pred_log))  # log1p 역변환
            predictions.append(pred_original)

            # 다음 입력 시퀀스 구성 (sliding window)
            new_step = current_seq[0, -1, :].clone()  # 마지막 타임스텝 복사
            new_step[target_idx] = float(pred_val)  # 예측값으로 타겟 피처 업데이트
            new_step = new_step.unsqueeze(0).unsqueeze(0)  # (1, 1, features)
            current_seq = torch.cat([current_seq[:, 1:, :], new_step], dim=1)

    # 신뢰구간 계산 (단순 추정: 예측 불확실성은 스텝이 멀어질수록 증가)
    confidence_z = cfg["confidence_z"]
    results: list[dict] = []

    for i, pred_sales in enumerate(predictions):
        # 불확실성 증가 계수: 스텝이 멀어질수록 선형 증가
        uncertainty_factor = 0.05 * (i + 1)  # 5%, 10%, 15%, ...
        margin = abs(pred_sales) * uncertainty_factor * confidence_z

        results.append(
            {
                "quarter_offset": i + 1,
                "predicted_sales": round(pred_sales, 0),
                "confidence_lower": round(max(0, pred_sales - margin), 0),
                "confidence_upper": round(pred_sales + margin, 0),
            }
        )

    return results


# ---------------------------------------------------------------------------
# 편의 함수
# ---------------------------------------------------------------------------


def forecast(
    input_sequence: list,
    months: int = 4,
    config: dict | None = None,
) -> list[dict]:
    """과거 매출 시퀀스를 직접 입력받아 예측한다.

    Parameters
    ----------
    input_sequence : list[float]
        과거 매출 시계열 (최소 window_size 길이).
    months : int
        예측할 분기 수.
    config : dict, optional
        설정 오버라이드.

    Returns
    -------
    list[dict]
        predict()와 동일한 형식.
    """
    cfg = {**DEFAULT_PREDICT_CONFIG, **(config or {})}
    device = torch.device("cpu")

    weights_path = Path(cfg["weights_path"])
    scalers_path = Path(cfg["scalers_path"])
    window_size = cfg["window_size"]

    if not weights_path.exists():
        raise FileNotFoundError(f"모델 가중치를 찾을 수 없습니다: {weights_path}")
    if not scalers_path.exists():
        raise FileNotFoundError(f"스케일러 파일을 찾을 수 없습니다: {scalers_path}")

    feat_scaler, tgt_scaler = load_scalers(scalers_path)
    input_size = len(feat_scaler.scale_)

    model = LSTMForecaster(
        input_size=input_size,
        hidden_size=cfg["hidden_size"],
        num_layers=cfg["num_layers"],
        dropout=cfg["dropout"],
    )
    model.load_weights(weights_path)
    model.to(device)
    model.eval()

    # 입력 시퀀스를 피처 배열로 변환 (단일 피처 = 매출만)
    seq_arr = np.array(input_sequence[-window_size:], dtype=np.float32).reshape(-1, 1)

    # 피처가 1개보다 많은 모델이면, 나머지 피처는 0으로 패딩
    if input_size > 1:
        padded = np.zeros((len(seq_arr), input_size), dtype=np.float32)
        padded[:, 0] = seq_arr.flatten()
        seq_arr = padded

    seq_scaled = feat_scaler.transform(seq_arr)

    predictions: list[float] = []
    confidence_z = cfg.get("confidence_z", 1.96)

    with torch.no_grad():
        current_seq = torch.from_numpy(seq_scaled).unsqueeze(0).to(device)

        for _ in range(months):
            pred_scaled = model(current_seq)
            pred_val = pred_scaled.cpu().numpy().flatten()[0]
            pred_original = tgt_scaler.inverse_transform([[pred_val]])[0][0]
            predictions.append(float(pred_original))

            new_step = current_seq[0, -1, :].clone()
            new_step[0] = pred_val
            new_step = new_step.unsqueeze(0).unsqueeze(0)
            current_seq = torch.cat([current_seq[:, 1:, :], new_step], dim=1)

    results: list[dict] = []
    for i, pred_sales in enumerate(predictions):
        uncertainty_factor = 0.05 * (i + 1)
        margin = abs(pred_sales) * uncertainty_factor * confidence_z

        results.append(
            {
                "quarter_offset": i + 1,
                "predicted_sales": round(pred_sales, 0),
                "confidence_lower": round(max(0, pred_sales - margin), 0),
                "confidence_upper": round(pred_sales + margin, 0),
            }
        )

    return results
