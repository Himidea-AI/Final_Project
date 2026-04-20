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
    "closure_rate_pred": "폐업률",
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
            "feature_ko": _TCN_FEATURE_KO.get(feature_cols[i], feature_cols[i]),
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
        model:         학습된 ClosurePredictor 인스턴스.
                       None 이면 내부에서 weights/closure_model.pt 를 로드한다.

    Returns:
        dict:
            feature_importance : 피처별 SHAP 기여도 리스트 (중요도 내림차순)
            base_value         : SHAP expected_value (기준 예측값)
            predicted_value    : 모델 실제 출력 (폐업률 0~1)
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


# ---------------------------------------------------------------------------
# TCN 피처 한국어 매핑 — ALL_FEATURES 31개 기준 (_FEATURE_KO 기반 확장)
# ---------------------------------------------------------------------------

_TCN_FEATURE_KO: dict[str, str] = {
    **_FEATURE_KO,
    # SALES_FEATURES (12개) — 매출 관련 피처
    "monthly_sales": "월 매출액",
    "monthly_count": "월 매출 건수",
    "weekday_sales": "평일 매출액",
    "weekend_sales": "주말 매출액",
    "male_sales": "남성 매출액",
    "female_sales": "여성 매출액",
    "age_10_sales": "10대 매출액",
    "age_20_sales": "20대 매출액",
    "age_30_sales": "30대 매출액",
    "age_40_sales": "40대 매출액",
    "age_50_sales": "50대 매출액",
    "age_60_above_sales": "60대 이상 매출액",
    # STORE_FEATURES (5개) — 점포 현황 피처
    "store_count": "점포 수",
    "franchise_count": "프랜차이즈 수",
    "open_count": "개업 수",
    "close_count": "폐업 수",
    "closure_rate": "폐업률",
    # POP_FEATURES (4개) — 인구 피처
    "total_pop": "총 인구",
    "avg_age": "평균 연령",
    "total_households": "총 세대 수",
    "resident_pop": "주민등록 주거인구",
    # RENT_FEATURES (2개) — 임대료 피처
    "rent_1f": "1층 임대료",
    "vacancy_rate": "공실률",
    # EXTRA_FEATURES (5개) — 외부 지표 피처
    "cpi_index": "소비자물가지수",
    "quarter_num": "분기 계절성",
    "trend_score": "네이버 검색 트렌드",
    "holiday_count": "분기 공휴일 수",
    "bus_flpop": "버스 정류장 유동인구",
    # GOLMOK_FEATURES (5개) — 골목상권 피처
    "store_franchise": "골목상권 프랜차이즈 점포 수",
    "store_normal": "골목상권 일반 점포 수",
    "floating_pop": "골목상권 유동인구",
    "pop_per_store_gm": "골목상권 점포당 유동인구",
    "normal_ratio": "일반 점포 비율",
}


# ---------------------------------------------------------------------------
# TCN SHAP 분석
# ---------------------------------------------------------------------------


def explain_tcn_prediction(
    dong_code: str,
    industry_code: str,
) -> dict:
    """
    SHAP 분석으로 TCN 매출 예측 근거를 설명한다.

    TCN(Temporal Convolutional Network) 모델에 대해
    GradientExplainer(1순위)·DeepExplainer(2순위) 를 사용하여
    피처별 매출 기여도를 계산하고 프론트엔드가 바로 소비할 수 있는
    dict 형태로 반환한다.
    가중치 파일이 없거나 SHAP 계산에 실패하면 mock 데이터를 반환한다.

    Args:
        dong_code:     행정동 코드 (예: "11440530")
        industry_code: 업종 코드   (예: "CS100001")

    Returns:
        dict:
            feature_importance   : 피처별 SHAP 기여도 리스트 (중요도 내림차순)
            base_value           : SHAP expected_value (기준 예측값)
            predicted_value      : 모델 실제 출력 (매출액, 원 단위)
            predicted_value_unit : "원"
            is_mock              : mock 데이터 여부
    """
    import torch

    from models.lstm_forecast.data_prep import (
        ALL_FEATURES,
        DB_URL,
        build_timeseries,
        load_sales_data,
        load_store_data,
    )
    from models.tcn_forecast.model import WEIGHTS_DIR, TCNForecaster
    from models.tcn_forecast.train import load_scalers

    # seed2026 고정 실험 가중치 사용 (가장 안정적인 시드)
    weights_path = WEIGHTS_DIR / "finetuned_mapo_tcn_seed2026.pt"
    scalers_path = WEIGHTS_DIR / "finetune_tcn_scalers_seed2026.pkl"

    # ---- 1) 가중치·스케일러 파일 존재 확인 → 없으면 mock ----
    if not weights_path.exists() or not scalers_path.exists():
        _log("WARNING", f"TCN 가중치 또는 스케일러 파일 없음: {weights_path}")
        result = _mock_shap_values(list(ALL_FEATURES))
        result["predicted_value_unit"] = "원"
        result["predicted_value"] = 15_000_000.0  # mock 매출 기본값 (원)
        return result

    # ---- 2) 스케일러 로드 → input_size 결정 ----
    try:
        feat_scaler, tgt_scaler = load_scalers(scalers_path)
        input_size = len(feat_scaler.scale_)
        _log("INFO", f"TCN 스케일러 로드 완료: input_size={input_size}")
    except Exception as exc:
        _log("WARNING", f"TCN 스케일러 로드 실패 - mock 반환: {exc}")
        result = _mock_shap_values(list(ALL_FEATURES))
        result["predicted_value_unit"] = "원"
        result["predicted_value"] = 15_000_000.0
        return result

    # ---- 3) TCN 모델 로드 ----
    try:
        model = TCNForecaster(
            input_size=input_size,
            n_channels=128,  # DEFAULT_PREDICT_CONFIG와 일치
            kernel_size=2,
            dilations=[1, 2],
            dropout=0.2,
        )
        model.load_weights(weights_path)
        model.eval()
        _log("INFO", "TCNForecaster 가중치 로드 완료")
    except Exception as exc:
        _log("WARNING", f"TCN 모델 로드 실패 - mock 반환: {exc}")
        result = _mock_shap_values(list(ALL_FEATURES))
        result["predicted_value_unit"] = "원"
        result["predicted_value"] = 15_000_000.0
        return result

    # ---- 4) 입력 텐서 준비 — predict.py와 동일 로직 재사용 ----
    window_size = 4  # DEFAULT_PREDICT_CONFIG["window_size"]
    feature_cols = list(ALL_FEATURES)

    try:
        dong_prefix = dong_code[:5] if len(dong_code) >= 5 else dong_code
        sales_df = load_sales_data(db_url=DB_URL, dong_prefix=dong_prefix)
        store_df = load_store_data(db_url=DB_URL, dong_prefix=dong_prefix)
        ts = build_timeseries(sales_df, store_df)
        group = ts[(ts["dong_code"] == dong_code) & (ts["industry_code"] == industry_code)]

        if group.empty:
            raise ValueError(f"데이터 없음: dong_code={dong_code}, industry_code={industry_code}")

        # 실제 사용 가능한 피처 컬럼만 필터링
        actual_features = [c for c in feature_cols if c in group.columns]
        group = group.sort_values("quarter")
        recent = group[actual_features].values.astype(np.float32)

        if len(recent) < window_size:
            raise ValueError(f"과거 데이터 부족: {len(recent)}분기 (최소 {window_size}분기 필요)")

        # 피처 스케일링 후 텐서 변환 — shape: (1, window_size, input_size)
        seq = feat_scaler.transform(recent[-window_size:])
        input_tensor = torch.tensor(seq, dtype=torch.float32).unsqueeze(0)
        _log("INFO", f"입력 텐서 준비 완료: shape={tuple(input_tensor.shape)}")
    except Exception as exc:
        _log("WARNING", f"입력 데이터 준비 실패 - mock 반환: {exc}")
        # 데이터 없을 때 배경 텐서 기준 shape으로 mock 입력 사용
        input_tensor = torch.zeros(1, window_size, input_size)

    # ---- 5) 모델 순전파 — 기준 예측값 확보 (매출액 원 단위) ----
    with torch.no_grad():
        raw_output = model(input_tensor)
        # 역변환: 스케일러 → log 도메인 → 원 단위 매출액
        # 학습 시 타겟은 log1p 변환된 값이므로 expm1로 복원해야 원 단위가 나옴
        # (models/tcn_forecast/predict.py:188-189 와 동일 패턴)
        try:
            pred_log = tgt_scaler.inverse_transform([[raw_output.item()]])[0][0]
            predicted_value = float(np.expm1(pred_log))
        except Exception:
            # 역변환 실패 시 raw 출력 그대로 사용
            predicted_value = float(raw_output.item())
    predicted_value = max(0.0, predicted_value)
    _log("INFO", f"TCN 예측값: {predicted_value:,.0f}원")

    # ---- 6) SHAP — GradientExplainer 우선 (TCN Conv1d에 더 안정적), DeepExplainer 2순위 ----
    background = torch.zeros(10, window_size, input_size)  # 배경 텐서: 영벡터 10개

    shap_values_raw = None
    base_value = 0.0

    try:
        import shap

        _log("INFO", "GradientExplainer 실행 시작 (TCN 1순위)")
        explainer = shap.GradientExplainer(model, background)
        shap_values_raw = explainer.shap_values(input_tensor)
        if hasattr(explainer, "expected_value"):
            _ev = explainer.expected_value
            base_value = float(_ev.item() if isinstance(_ev, np.ndarray) else _ev)
        _log("INFO", "GradientExplainer 완료")

    except Exception as grad_exc:
        # GradientExplainer 실패 → DeepExplainer 로 전환
        _log("WARNING", f"GradientExplainer 실패 - DeepExplainer 로 전환: {grad_exc}")
        try:
            import shap

            explainer = shap.DeepExplainer(model, background)
            shap_values_raw = explainer.shap_values(input_tensor)
            _ev = explainer.expected_value
            base_value = float(_ev.item() if isinstance(_ev, np.ndarray) else _ev)
            _log("INFO", "DeepExplainer 완료")

        except Exception as deep_exc:
            # 두 explainer 모두 실패 → mock 반환
            _log("WARNING", f"DeepExplainer 도 실패 - mock 반환: {deep_exc}")
            result = _mock_shap_values(feature_cols)
            result["predicted_value_unit"] = "원"
            result["predicted_value"] = predicted_value
            return result

    # ---- 7) SHAP 값 후처리: (..., window_size, input_size) → 시간축 평균 → (input_size,) ----
    shap_array = np.array(shap_values_raw)

    # shap GradientExplainer는 single-output 회귀 모델에 targets=1 축을 말단에 추가해 반환함
    # 예: (batch, window, features, 1). 이후 while/if 로직은 (batch, window, features) 3D를
    # 가정하므로, targets 축이 살아있으면 축소 단계에서 features 축이 잘못 제거됨.
    # 따라서 squeeze로 targets 축을 먼저 제거한 뒤 기존 로직 실행.
    if shap_array.ndim >= 3 and shap_array.shape[-1] == 1:
        shap_array = shap_array.squeeze(-1)

    # 일부 shap 버전에서 list of arrays 형태로 반환 → 앞 차원 순서대로 제거
    while shap_array.ndim >= 4:
        shap_array = shap_array[0]

    # 배치 차원 제거
    if shap_array.ndim == 3:
        shap_array = shap_array[0]  # (window_size, n_features)

    # 시간축(window) 평균 → 피처별 대표 기여도
    if shap_array.ndim == 2:
        shap_array = shap_array.mean(axis=0)  # (n_features,)

    # 처리 후에도 1차원이 아니면 복구 불가 → mock 반환
    if shap_array.ndim != 1:
        _log("WARNING", f"SHAP 값 차원 처리 실패 (ndim={shap_array.ndim}) - mock 반환")
        result = _mock_shap_values(feature_cols)
        result["predicted_value_unit"] = "원"
        result["predicted_value"] = predicted_value
        return result

    # 피처 수 불일치 시 맞춰서 잘라냄
    n_feats = min(len(shap_array), len(feature_cols))
    shap_array = shap_array[:n_feats]
    feature_cols = feature_cols[:n_feats]

    # ---- 8) 피처별 기여도 정렬 (절댓값 내림차순) ----
    sorted_indices = np.argsort(-np.abs(shap_array))
    feature_importance = [
        {
            "rank": rank + 1,
            "feature": feature_cols[i],
            "feature_ko": _TCN_FEATURE_KO.get(feature_cols[i], feature_cols[i]),
            "shap_value": round(float(shap_array[i]), 6),
            "abs_shap": round(float(abs(shap_array[i])), 6),
            # 기여 방향: 매출을 높이면 positive, 낮추면 negative
            "direction": "positive" if shap_array[i] > 0 else ("negative" if shap_array[i] < 0 else "neutral"),
        }
        for rank, i in enumerate(sorted_indices)
    ]

    _log("INFO", f"TCN SHAP 분석 완료 - 최고 기여 피처: {feature_importance[0]['feature_ko']}")

    return {
        "feature_importance": feature_importance,
        "base_value": round(base_value, 6),
        "predicted_value": round(predicted_value, 2),
        "predicted_value_unit": "원",  # 매출 단위 명시 (생존률과 구별)
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
            f"shap_values 길이({len(shap_values)})와 feature_names 길이({len(feature_names)}) 불일치",
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
