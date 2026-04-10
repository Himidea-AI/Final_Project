"""
SHAP 기반 예측 근거 시각화 — 생존률 예측 결과의 설명 가능성 제공

SurvivalPredictor (LSTM) 모델에 대해 DeepExplainer / GradientExplainer를 사용하여
피처별 기여도를 계산하고, 프론트엔드에서 바로 사용할 수 있는 dict 형태로 반환한다.
가중치 파일이 없는 개발 환경에서는 mock SHAP 값을 반환한다.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 한국어 피처명 매핑 (docs/glossary.md 및 data_prep.FEATURE_COLS 기준)
# ---------------------------------------------------------------------------

_FEATURE_KO: dict[str, str] = {
    "store_count": "점포 수",
    "open_count": "개업 수",
    "close_count": "폐업 수",
    "closure_rate": "폐업률",
    "franchise_count": "프랜차이즈 수",
    "store_change_rate": "점포 증감률",
    "franchise_ratio": "프랜차이즈 비율",
    "survival_rate": "생존률",
}


# ---------------------------------------------------------------------------
# 내부 로그 헬퍼 — [시각][ShapAnalysis][STATUS] - 메시지 형식
# ---------------------------------------------------------------------------


def _log(level: str, message: str) -> None:
    """지정 형식으로 로그를 출력한다."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}][ShapAnalysis][{level}] - {message}"
    if level == "INFO":
        logger.info(formatted)
    elif level == "WARNING":
        logger.warning(formatted)
    elif level == "ERROR":
        logger.error(formatted)
    else:
        logger.debug(formatted)


# ---------------------------------------------------------------------------
# mock SHAP 값 생성 — 가중치 없는 개발 환경용
# ---------------------------------------------------------------------------


def _mock_shap_values(feature_cols: list[str]) -> dict:
    """가중치 파일이 없는 환경에서 반환하는 mock SHAP 결과."""
    _log("WARNING", "모델 가중치 없음 - mock SHAP 값을 반환합니다")

    # 재현 가능한 균등 랜덤값 (0.0 ~ 0.1 범위)
    rng = np.random.default_rng(seed=42)
    shap_vals = rng.uniform(0.0, 0.1, size=len(feature_cols))

    # 절댓값 기준 내림차순 정렬
    sorted_indices = np.argsort(-np.abs(shap_vals))
    feature_importance = [
        {
            "rank": rank + 1,
            "feature": feature_cols[i],
            "feature_ko": _FEATURE_KO.get(feature_cols[i], feature_cols[i]),
            "shap_value": round(float(shap_vals[i]), 6),
            "abs_shap": round(float(abs(shap_vals[i])), 6),
            # 기여 방향: 실제 경로와 동일한 필드 구조 유지
            "direction": "positive" if shap_vals[i] > 0 else ("negative" if shap_vals[i] < 0 else "neutral"),
        }
        for rank, i in enumerate(sorted_indices)
    ]

    return {
        "feature_importance": feature_importance,
        "base_value": 0.5,
        "predicted_value": 0.5,
        "is_mock": True,
    }


# ---------------------------------------------------------------------------
# 메인 함수
# ---------------------------------------------------------------------------


def explain_prediction(
    dong_code: str,
    industry_code: str,
    model: Any | None = None,
) -> dict:
    """
    SHAP 분석으로 생존률 예측 근거를 설명한다.

    predict.py 의 _load_model / _prepare_input 을 재사용하므로
    scaler.pkl 로드 및 데이터 전처리는 별도 구현하지 않는다.

    Args:
        dong_code:     행정동 코드 (예: "11440530")
        industry_code: 업종 코드   (예: "CS100001")
        model:         학습된 SurvivalPredictor 인스턴스.
                       None 이면 내부에서 weights/survival_model.pt 를 로드한다.

    Returns:
        dict:
            feature_importance : 피처별 SHAP 기여도 리스트 (중요도 내림차순)
            base_value         : SHAP expected_value (기준 예측값)
            predicted_value    : 모델 실제 출력 (생존률 0~1)
            is_mock            : mock 데이터 여부
    """
    import torch

    # predict.py 의 내부 헬퍼 재사용 (복사 금지)
    from models.revenue_predictor.data_prep import FEATURE_COLS
    from models.revenue_predictor.predict import _load_model, _prepare_input

    # ---- 1) 모델 로드 ----
    if model is None:
        try:
            model = _load_model()
            _log("INFO", "SurvivalPredictor 가중치 로드 완료")
        except FileNotFoundError as exc:
            _log("WARNING", f"가중치 파일 없음: {exc}")
            return _mock_shap_values(FEATURE_COLS)

    # ---- 2) 입력 데이터 준비 (scaler 적용 포함) ----
    try:
        input_data = _prepare_input(dong_code, industry_code)
    except Exception as prep_exc:
        # DB/CSV 로드 실패 등 내부 예외를 catch 하여 mock 으로 전환
        _log("WARNING", f"입력 데이터 준비 중 예외 발생 - mock 반환: {prep_exc}")
        return _mock_shap_values(FEATURE_COLS)
    if input_data is None:
        _log("WARNING", f"입력 데이터 준비 실패 (dong={dong_code}, industry={industry_code}) - mock 반환")
        return _mock_shap_values(FEATURE_COLS)

    # input_data: shape (1, WINDOW_SIZE, 8) np.ndarray
    input_tensor = torch.tensor(input_data, dtype=torch.float32)

    # ---- 3) 모델 순전파 — 기준 예측값 확보 ----
    model.eval()
    with torch.no_grad():
        predicted_value = float(model(input_tensor).item())
        predicted_value = max(0.0, min(1.0, predicted_value))

    # ---- 4) SHAP — DeepExplainer 우선, 실패 시 GradientExplainer ----
    # 배경 데이터: 영벡터 10개 (DeepExplainer 요구사항)
    background = torch.zeros(10, input_tensor.shape[1], input_tensor.shape[2])

    try:
        import shap

        _log("INFO", "DeepExplainer 실행 시작")
        explainer = shap.DeepExplainer(model, background)
        shap_values_raw = explainer.shap_values(input_tensor)
        # expected_value 가 np.ndarray 로 반환되는 shap 버전 대응
        _ev = explainer.expected_value
        base_value = float(_ev.item() if isinstance(_ev, np.ndarray) else _ev)
        _log("INFO", "DeepExplainer 완료")

    except Exception as deep_exc:
        # DeepExplainer 실패 → GradientExplainer 로 전환
        _log("WARNING", f"DeepExplainer 실패 - GradientExplainer 로 전환: {deep_exc}")
        try:
            import shap

            explainer = shap.GradientExplainer(model, background)
            shap_values_raw = explainer.shap_values(input_tensor)
            # expected_value 가 np.ndarray 로 반환되는 shap 버전 대응
            if hasattr(explainer, "expected_value"):
                _ev = explainer.expected_value
                base_value = float(_ev.item() if isinstance(_ev, np.ndarray) else _ev)
            else:
                base_value = 0.5
            _log("INFO", "GradientExplainer 완료")

        except Exception as grad_exc:
            # 두 explainer 모두 실패 → mock 반환
            _log("WARNING", f"GradientExplainer 도 실패 - mock 반환: {grad_exc}")
            return _mock_shap_values(FEATURE_COLS)

    # ---- 5) SHAP 값 후처리: (..., WINDOW_SIZE, 8) → 시간축 평균 → (8,) ----
    shap_array = np.array(shap_values_raw)

    # ndim >= 4: 일부 shap 버전에서 list of arrays 형태로 반환 → 앞 차원 순서대로 제거
    while shap_array.ndim >= 4:
        shap_array = shap_array[0]

    # 배치 차원 제거 (있는 경우)
    if shap_array.ndim == 3:
        shap_array = shap_array[0]  # (WINDOW_SIZE, n_features)

    # 시간축(분기) 평균 → 피처별 대표 기여도
    if shap_array.ndim == 2:
        shap_array = shap_array.mean(axis=0)  # (n_features,)

    # 처리 후에도 1차원이 아니면 복구 불가 → mock 반환
    if shap_array.ndim != 1:
        _log("WARNING", f"SHAP 값 차원 처리 실패 (ndim={shap_array.ndim}) - mock 반환")
        return _mock_shap_values(FEATURE_COLS)

    # ---- 6) 피처별 기여도 정렬 (절댓값 내림차순) ----
    sorted_indices = np.argsort(-np.abs(shap_array))
    feature_importance = [
        {
            "rank": rank + 1,
            "feature": FEATURE_COLS[i],
            "feature_ko": _FEATURE_KO.get(FEATURE_COLS[i], FEATURE_COLS[i]),
            "shap_value": round(float(shap_array[i]), 6),
            "abs_shap": round(float(abs(shap_array[i])), 6),
            # 기여 방향: 생존률을 높이면 positive, 낮추면 negative
            "direction": "positive" if shap_array[i] > 0 else ("negative" if shap_array[i] < 0 else "neutral"),
        }
        for rank, i in enumerate(sorted_indices)
    ]

    _log("INFO", f"SHAP 분석 완료 - 최고 기여 피처: {feature_importance[0]['feature_ko']}")

    return {
        "feature_importance": feature_importance,
        "base_value": round(base_value, 6),
        "predicted_value": round(predicted_value, 6),
        "is_mock": False,
    }


def plot_shap_summary(
    shap_values: list[float],
    feature_names: list[str],
) -> dict:
    """
    SHAP 요약 차트용 데이터를 생성한다.

    matplotlib/Streamlit 렌더링 없이 프론트엔드가 직접 소비할 수 있는
    dict 구조를 반환한다. explain_prediction() 결과의 shap_value 리스트와
    FEATURE_COLS 를 그대로 넘기면 된다.

    Args:
        shap_values:   피처별 SHAP 값 리스트 (feature_names 와 동일 순서)
        feature_names: 피처명 리스트 (영문, FEATURE_COLS 순서 기준)

    Returns:
        dict:
            chart_type : "bar"
            title      : 차트 제목 (한국어)
            data       : [{feature_ko, feature_en, shap_value, direction}, ...]
            x_label    : x 축 레이블
            y_label    : y 축 레이블
    """
    if len(shap_values) != len(feature_names):
        _log(
            "WARNING",
            f"shap_values 길이({len(shap_values)})와 "
            f"feature_names 길이({len(feature_names)}) 불일치",
        )

    # 절댓값 기준 내림차순 정렬 (중요도 높은 피처가 위로)
    pairs = sorted(
        zip(feature_names, shap_values),
        key=lambda x: abs(x[1]),
        reverse=True,
    )

    data = [
        {
            "feature_ko": _FEATURE_KO.get(feat, feat),
            "feature_en": feat,
            "shap_value": round(float(val), 6),
            "direction": "positive" if val >= 0 else "negative",
        }
        for feat, val in pairs
    ]

    _log("INFO", f"plot_shap_summary 생성 완료 - {len(data)}개 피처")

    return {
        "chart_type": "bar",
        "title": "피처별 SHAP 기여도 (생존률 예측)",
        "data": data,
        "x_label": "SHAP 값 (생존률 기여도)",
        "y_label": "입력 피처",
    }
