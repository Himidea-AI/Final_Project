"""
TCN 시계열 추론 — 특정 동x업종의 향후 n분기 매출 예측

GRU predict.py 대비 변경점:
- GRUForecaster → TCNForecaster import
- 가중치 로드 경로: tcn_forecast/weights/finetuned_mapo_tcn.pt
- n_channels=128, dilations=[1,2], kernel_size=2 (train config와 일치)
- data_prep은 lstm_forecast에서 직접 import 재사용 (GRU와 동일)
- 자기회귀 4분기 추론 구조 완전 동일
- 신뢰구간 계산 방식 완전 동일

담당: B2 — 수지니
참조: models/gru_forecast/predict.py (구조 동일)
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import torch

# data_prep은 lstm_forecast에서 재사용 — 동일한 피처/전처리 적용
from models.lstm_forecast.data_prep import (
    ALL_FEATURES,
    DB_URL,
    build_timeseries,
    load_sales_data,
    load_store_data,
)

from .model import WEIGHTS_DIR, TCNForecaster
from .train import load_scalers

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 기본 설정
# ---------------------------------------------------------------------------

DEFAULT_PREDICT_CONFIG: dict = {
    "db_url": DB_URL,
    # TCN 파인튜닝 가중치 경로
    "weights_path": str(WEIGHTS_DIR / "finetuned_mapo_tcn.pt"),
    "scalers_path": str(WEIGHTS_DIR / "finetune_tcn_scalers.pkl"),
    # train config와 일치: window_size=4, n_channels=128
    "window_size": 4,
    "n_channels": 128,
    "kernel_size": 2,
    "dilations": [1, 2],
    "dropout": 0.2,
    "target_col": "monthly_sales",
    "feature_cols": None,
    "confidence_z": 1.96,   # 95% 신뢰구간 (GRU/LSTM과 동일)
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
    """특정 동x업종의 향후 n분기 매출을 자기회귀 방식으로 예측한다.

    자기회귀(autoregressive) 예측:
    - 1분기 예측 → 예측값을 입력 시퀀스 끝에 추가 → 2분기 예측 → ...
    - 스텝이 멀어질수록 불확실성 증가 (5% × step × z)
    GRU/LSTM과 완전히 동일한 추론 구조 — 공정한 비교를 위해.

    Parameters
    ----------
    dong_code : str
        행정동 코드 (예: '11440555').
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
            "quarter_offset": int,     # 1, 2, 3, 4
            "predicted_sales": float,
            "confidence_lower": float,
            "confidence_upper": float,
        }
    """
    cfg = {**DEFAULT_PREDICT_CONFIG, **(config or {})}
    device = torch.device("cpu")   # 추론은 CPU에서 수행

    weights_path = Path(cfg["weights_path"])
    scalers_path = Path(cfg["scalers_path"])
    window_size = cfg["window_size"]
    target_col = cfg["target_col"]
    feature_cols = cfg.get("feature_cols")

    # 가중치 파일 존재 확인
    if not weights_path.exists():
        raise FileNotFoundError(
            f"TCN 모델 가중치를 찾을 수 없습니다: {weights_path}\n"
            "먼저 학습(pretrain/finetune)을 실행하세요."
        )

    # 스케일러 파일 존재 확인
    if not scalers_path.exists():
        raise FileNotFoundError(f"스케일러 파일을 찾을 수 없습니다: {scalers_path}")

    # 스케일러 로드 — 역변환(inverse_transform)에 사용
    feat_scaler, tgt_scaler = load_scalers(scalers_path)

    # 피처 컬럼 결정 — 스케일러에서 실제 사용된 피처 수 추론
    if feature_cols is None:
        feature_cols = ALL_FEATURES
    input_size = len(feat_scaler.scale_)

    # TCN 모델 로드
    model = TCNForecaster(
        input_size=input_size,
        n_channels=cfg["n_channels"],
        kernel_size=cfg["kernel_size"],
        dilations=cfg["dilations"],
        dropout=cfg["dropout"],
    )
    model.load_weights(weights_path)
    model.to(device)
    model.eval()

    # 과거 데이터 로드 — 마포구 동 코드 앞 5자리로 필터링
    dong_prefix = dong_code[:5] if len(dong_code) >= 5 else dong_code
    sales_df = load_sales_data(db_url=cfg["db_url"], dong_prefix=dong_prefix)
    store_df = load_store_data(db_url=cfg["db_url"], dong_prefix=dong_prefix)

    # 해당 동x업종 시계열 추출 (guide-density Hot Deck 보간 포함)
    ts = build_timeseries(sales_df, store_df)
    group = ts[(ts["dong_code"] == dong_code) & (ts["industry_code"] == industry_code)]

    if group.empty:
        raise ValueError(f"데이터가 없습니다: dong_code={dong_code}, industry_code={industry_code}")

    # 실제 사용 가능한 피처 컬럼 매칭
    actual_features = [c for c in feature_cols if c in group.columns]
    if not actual_features:
        raise ValueError("사용 가능한 피처 컬럼이 없습니다.")

    # 분기 정렬 후 마지막 window_size 분기를 입력으로 사용
    group = group.sort_values("quarter")
    recent = group[actual_features].values.astype(np.float32)

    if len(recent) < window_size:
        raise ValueError(
            f"과거 데이터가 부족합니다: {len(recent)}분기 (최소 {window_size}분기 필요)"
        )

    # 피처 스케일링
    seq = feat_scaler.transform(recent[-window_size:])

    # 타겟 컬럼의 인덱스 — 자기회귀 시 예측값을 다음 입력에 반영하기 위해 필요
    try:
        target_idx = actual_features.index(target_col)
    except ValueError:
        target_idx = 0

    # ---------------------------------------------------------------------------
    # 자기회귀 예측 루프
    # ---------------------------------------------------------------------------
    predictions: list[float] = []

    with torch.no_grad():
        # 초기 입력 시퀀스: (1, window_size, input_size)
        current_seq = torch.from_numpy(seq).unsqueeze(0).to(device)

        for _ in range(n_months):
            # TCN 순전파 → 스케일된 예측값
            pred_scaled = model(current_seq)            # (1, 1)
            pred_val = pred_scaled.cpu().numpy().flatten()[0]

            # 역변환: 스케일 → 로그 → 원래 매출 단위
            pred_log = tgt_scaler.inverse_transform([[pred_val]])[0][0]
            pred_original = float(np.expm1(pred_log))  # log1p 역변환
            predictions.append(pred_original)

            # 다음 입력 시퀀스 구성 (sliding window)
            # 마지막 타임스텝을 복사하고 타겟 피처만 예측값으로 교체
            new_step = current_seq[0, -1, :].clone()
            new_step[target_idx] = float(pred_val)
            new_step = new_step.unsqueeze(0).unsqueeze(0)  # (1, 1, features)
            current_seq = torch.cat([current_seq[:, 1:, :], new_step], dim=1)

    # ---------------------------------------------------------------------------
    # 신뢰구간 계산
    # ---------------------------------------------------------------------------
    # 단순 추정: 스텝이 멀어질수록 불확실성 선형 증가 (GRU/LSTM과 동일)
    confidence_z = cfg["confidence_z"]
    results: list[dict] = []

    for i, pred_sales in enumerate(predictions):
        # 불확실성 증가 계수: 5%, 10%, 15%, 20%
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
