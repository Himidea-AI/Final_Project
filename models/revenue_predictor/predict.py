"""
생존률 예측 추론 함수

predict(dong_code, industry_code) → 생존률 예측 결과
B2(수지니)의 12개월 시뮬레이션 입력으로 사용된다.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import torch

from models.revenue_predictor.data_prep import FEATURE_COLS, engineer_features, load_store_data
from models.revenue_predictor.model import build_model

logger = logging.getLogger(__name__)

WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"
WINDOW_SIZE = 6

# 모듈 수준 캐시 — 모델/scaler를 한 번만 로드
_cached_model: torch.nn.Module | None = None
_cached_scaler = None


# ---------------------------------------------------------------------------
# 모델 로드
# ---------------------------------------------------------------------------


def _load_model() -> torch.nn.Module:
    """학습된 모델을 로드한다 (캐시 지원)."""
    global _cached_model  # noqa: PLW0603

    if _cached_model is not None:
        return _cached_model

    model_path = WEIGHTS_DIR / "survival_model.pt"
    if not model_path.exists():
        raise FileNotFoundError(f"학습된 모델 가중치를 찾을 수 없습니다: {model_path}")

    n_features = len(FEATURE_COLS)
    model = build_model(input_size=n_features)
    model.load_state_dict(torch.load(model_path, map_location="cpu", weights_only=True))
    model.eval()
    _cached_model = model
    logger.info("모델 로드 완료: %s", model_path)
    return model


def _load_scaler():
    """학습 시 저장된 scaler를 로드한다."""
    global _cached_scaler  # noqa: PLW0603

    if _cached_scaler is not None:
        return _cached_scaler

    scaler_path = WEIGHTS_DIR / "scaler.pkl"
    if not scaler_path.exists():
        logger.warning("scaler 파일 없음 — 정규화 없이 추론합니다")
        return None

    import joblib

    _cached_scaler = joblib.load(scaler_path)
    logger.info("scaler 로드 완료")
    return _cached_scaler


# ---------------------------------------------------------------------------
# 입력 데이터 준비
# ---------------------------------------------------------------------------


def _prepare_input(dong_code: str | int, industry_code: str) -> np.ndarray | None:
    """
    특정 동×업종의 최근 WINDOW_SIZE 분기 데이터를 추출하여 모델 입력 형태로 반환.

    Returns:
        np.ndarray shape (1, WINDOW_SIZE, n_features) 또는 데이터 부족 시 None
    """
    df = load_store_data(seoul=False)
    df = engineer_features(df)

    dong_code = str(dong_code)
    mask = (df["dong_code"].astype(str) == dong_code) & (df["industry_code"].astype(str) == industry_code)
    subset = df.loc[mask].sort_values("quarter").tail(WINDOW_SIZE)

    if len(subset) < WINDOW_SIZE:
        logger.warning(
            "데이터 부족: dong=%s, industry=%s — %d/%d 분기",
            dong_code,
            industry_code,
            len(subset),
            WINDOW_SIZE,
        )
        # 부족한 경우 패딩 (첫 번째 행 반복)
        if len(subset) == 0:
            return None
        while len(subset) < WINDOW_SIZE:
            subset = subset._append(subset.iloc[0:1], ignore_index=True)  # noqa: SLF001
        subset = subset.tail(WINDOW_SIZE)

    features = subset[FEATURE_COLS].values.astype(np.float32)

    # scaler 적용
    scaler = _load_scaler()
    if scaler is not None:
        features = scaler.transform(features)

    return features.reshape(1, WINDOW_SIZE, len(FEATURE_COLS)).astype(np.float32)


# ---------------------------------------------------------------------------
# 위험도 분류
# ---------------------------------------------------------------------------


def _classify_risk(survival_rate: float) -> str:
    """생존률 기반 위험도 분류."""
    if survival_rate >= 0.7:
        return "safe"
    elif survival_rate >= 0.4:
        return "caution"
    else:
        return "danger"


# ---------------------------------------------------------------------------
# 12개월 월별 생존률 보간
# ---------------------------------------------------------------------------


def _interpolate_monthly(quarterly_survival: float, months: int = 12) -> list[float]:
    """
    분기 생존률을 12개월 월별 생존률로 보간한다.

    분기 생존률을 월별 감쇄율로 변환하여 누적 적용.
    """
    # 분기 생존률 → 월별 생존률 (3개월 단위)
    monthly_decay = quarterly_survival ** (1 / 3)

    monthly_rates = []
    cumulative = 1.0
    for _ in range(months):
        cumulative *= monthly_decay
        monthly_rates.append(round(max(0.0, min(1.0, cumulative)), 4))

    return monthly_rates


# ---------------------------------------------------------------------------
# 자기회귀 예측 (4분기 선행)
# ---------------------------------------------------------------------------


def _autoregressive_predict(
    model: torch.nn.Module,
    initial_input: np.ndarray,
    steps: int = 4,
) -> list[float]:
    """
    자기회귀 방식으로 여러 분기의 생존률을 예측한다.

    Args:
        model: 학습된 모델
        initial_input: (1, WINDOW_SIZE, n_features)
        steps: 예측 분기 수

    Returns:
        list of predicted survival rates (분기별)
    """
    predictions: list[float] = []
    current_input = torch.tensor(initial_input, dtype=torch.float32)

    with torch.no_grad():
        for _ in range(steps):
            pred = model(current_input).item()
            pred = max(0.0, min(1.0, pred))
            predictions.append(pred)

            # 다음 입력: 시퀀스를 한 칸 밀고 예측값으로 마지막 행 업데이트
            new_row = current_input[0, -1, :].clone()
            # survival_rate 인덱스는 FEATURE_COLS의 마지막
            survival_idx = FEATURE_COLS.index("survival_rate")
            new_row[survival_idx] = pred

            current_input = torch.cat([current_input[:, 1:, :], new_row.unsqueeze(0).unsqueeze(0)], dim=1)

    return predictions


# ---------------------------------------------------------------------------
# 메인 예측 함수
# ---------------------------------------------------------------------------


def predict(dong_code: str | int, industry_code: str) -> dict:
    """
    특정 동×업종의 생존률을 예측한다.

    Args:
        dong_code:    행정동 코드 (예: "11440530")
        industry_code: 업종 코드 (예: "CS100001")

    Returns:
        dict:
            survival_rate:        향후 1분기 생존 확률 (0~1)
            closure_risk_level:   위험도 ("safe" / "caution" / "danger")
            monthly_survival_rates: 12개월 월별 생존률 리스트
            quarterly_predictions:  4분기 생존률 리스트
    """
    model = _load_model()
    input_data = _prepare_input(dong_code, industry_code)

    if input_data is None:
        logger.warning("입력 데이터를 준비할 수 없습니다 — 기본값 반환")
        return {
            "survival_rate": 0.5,
            "closure_risk_level": "caution",
            "monthly_survival_rates": [0.5] * 12,
            "quarterly_predictions": [0.5] * 4,
        }

    # 자기회귀 4분기 예측
    quarterly_preds = _autoregressive_predict(model, input_data, steps=4)

    # 첫 분기 예측값을 기준 생존률로 사용
    survival_rate = quarterly_preds[0]
    risk_level = _classify_risk(survival_rate)

    # 12개월 월별 생존률 보간
    monthly_rates = _interpolate_monthly(survival_rate, months=12)

    return {
        "survival_rate": round(survival_rate, 4),
        "closure_risk_level": risk_level,
        "monthly_survival_rates": monthly_rates,
        "quarterly_predictions": [round(p, 4) for p in quarterly_preds],
    }
