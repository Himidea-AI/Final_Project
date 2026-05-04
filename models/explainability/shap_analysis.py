"""
SHAP 기반 예측 근거 시각화 — TCN 매출 예측 결과의 설명 가능성 제공

TCNForecaster 모델에 대해 GradientExplainer / DeepExplainer를 사용하여
피처별 매출 기여도를 계산하고, 프론트엔드에서 바로 사용할 수 있는 dict 형태로 반환한다.
가중치 파일이 없는 개발 환경에서는 mock SHAP 값을 반환한다.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 프로세스 단위 모델 캐시 — 같은 가중치 경로는 한 번만 로드
# ---------------------------------------------------------------------------
_SHAP_MODEL_CACHE: dict = {}

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


def _mock_shap_values(feature_cols: list[str], predicted_value: float = 15_000_000.0) -> dict:
    """가중치 파일이 없는 환경에서 반환하는 mock SHAP 결과.

    predicted_value(원 단위)를 기준으로 shap_value를 비율 스케일링하여
    UI formatKrw()가 "0원"이 아닌 의미 있는 값을 표시할 수 있도록 한다.
    """
    _log("WARNING", "모델 가중치 없음 - mock SHAP 값을 반환합니다")

    # 재현 가능한 균등 랜덤값 (0.1 ~ 1.0 범위) — 0 방지
    rng = np.random.default_rng(seed=42)
    raw_vals = rng.uniform(0.1, 1.0, size=len(feature_cols))

    # predicted_value 합계로 비율 스케일링 — sum(shap_vals) = predicted_value
    raw_sum = float(np.sum(raw_vals))
    if abs(raw_sum) > 1e-10:
        shap_vals = raw_vals * (predicted_value / raw_sum)
    else:
        shap_vals = np.zeros(len(feature_cols), dtype=np.float32)

    # 절댓값 기준 내림차순 정렬
    sorted_indices = np.argsort(-np.abs(shap_vals))
    feature_importance = [
        {
            "rank": rank + 1,
            "feature": feature_cols[i],
            "feature_ko": _TCN_FEATURE_KO.get(feature_cols[i], feature_cols[i]),
            "shap_value": round(float(shap_vals[i]), 2),
            "abs_shap": round(float(abs(shap_vals[i])), 2),
            # 기여 방향: 실제 경로와 동일한 필드 구조 유지
            "direction": "positive" if shap_vals[i] > 0 else ("negative" if shap_vals[i] < 0 else "neutral"),
        }
        for rank, i in enumerate(sorted_indices)
    ]

    return {
        "feature_importance": feature_importance,
        "base_value": 0.0,
        "predicted_value": round(predicted_value, 2),
        "summary": [],
        "is_mock": True,
    }


# ---------------------------------------------------------------------------
# TCN 피처 한국어 매핑 — ALL_FEATURES 34개 기준 (_FEATURE_KO 기반 확장)
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
    # EXTRA_FEATURES (6개) — 외부 지표 피처
    "cpi_index": "소비자물가지수",
    "quarter_num": "분기 계절성",
    "trend_score": "네이버 검색 트렌드",
    "holiday_count": "분기 공휴일 수",
    "bus_flpop": "버스 정류장 유동인구",
    "adstrd_flpop": "행정동 유동인구",
    # GOLMOK_FEATURES (5개) — 골목상권 피처
    "store_franchise": "골목상권 프랜차이즈 점포 수",
    "store_normal": "골목상권 일반 점포 수",
    "floating_pop": "골목상권 유동인구",
    "pop_per_store_gm": "골목상권 점포당 유동인구",
    "normal_ratio": "일반 점포 비율",
    # TCN-only 추가 피처 (2026-05-04) — TCN ALL_FEATURES 에 포함, SHAP top_signals 노출
    "opr_sale_mt_avg": "동 평균 개업 수",
    "cls_sale_mt_avg": "동 평균 폐업 수",
    "industry_trend": "업종 검색 트렌드",
}


# ---------------------------------------------------------------------------
# TCN SHAP 자연어 요약 템플릿
# ---------------------------------------------------------------------------

_TCN_SUMMARY_TEMPLATES: dict[str, dict[str, str]] = {
    "monthly_sales": {
        "positive": "최근 매출액이 높아 향후 매출 예측에 긍정적으로 작용하고 있습니다.",
        "negative": "최근 매출액이 낮아 향후 매출 예측에 부정적으로 작용하고 있습니다.",
    },
    "monthly_count": {
        "positive": "방문 건수 증가가 향후 매출 상승에 기여하고 있습니다.",
        "negative": "방문 건수 감소가 향후 매출에 부정적 영향을 주고 있습니다.",
    },
    "weekday_sales": {
        "positive": "평일 매출이 안정적으로 높아 매출 예측에 긍정적입니다.",
        "negative": "평일 매출 부진이 전체 매출 예측을 낮추고 있습니다.",
    },
    "weekend_sales": {
        "positive": "주말 매출 호조가 매출 예측 상승에 기여하고 있습니다.",
        "negative": "주말 매출 부진이 매출 예측에 부정적 영향을 줍니다.",
    },
    "male_sales": {
        "positive": "남성 고객 매출이 증가해 전체 매출에 기여하고 있습니다.",
        "negative": "남성 고객 매출 감소가 전체 매출에 영향을 줍니다.",
    },
    "female_sales": {
        "positive": "여성 고객 매출이 증가해 전체 매출에 기여하고 있습니다.",
        "negative": "여성 고객 매출 감소가 전체 매출에 영향을 줍니다.",
    },
    "age_20_sales": {
        "positive": "20대 고객 매출 증가로 젊은 소비층 유입이 활발합니다.",
        "negative": "20대 고객 매출 감소가 신규 소비층 유입 약화를 나타냅니다.",
    },
    "age_30_sales": {
        "positive": "30대 주력 소비층 매출이 증가해 매출에 긍정적입니다.",
        "negative": "30대 주력 소비층 매출 감소가 전체 매출에 영향을 줍니다.",
    },
    "age_40_sales": {
        "positive": "40대 고객 매출 증가가 안정적 수익 기반에 기여합니다.",
        "negative": "40대 고객 매출 감소가 수익 기반 약화로 이어집니다.",
    },
    "age_50_sales": {
        "positive": "50대 고객 매출이 증가해 매출에 기여하고 있습니다.",
        "negative": "50대 고객 매출 감소가 전체 매출에 영향을 줍니다.",
    },
    "age_60_above_sales": {
        "positive": "60대 이상 고객 매출이 증가해 매출에 기여하고 있습니다.",
        "negative": "60대 이상 고객 매출 감소가 전체 매출에 영향을 줍니다.",
    },
    "store_count": {
        "positive": "점포 수 증가로 상권이 활성화되어 매출에 긍정적입니다.",
        "negative": "점포 수 감소로 상권이 위축되어 매출에 부정적입니다.",
    },
    "closure_rate": {
        "positive": "경쟁 업소 감소가 매출에 긍정적으로 작용하고 있습니다.",
        "negative": "경쟁 심화가 매출 예측에 부정적으로 작용하고 있습니다.",
    },
    "total_pop": {
        "positive": "주변 인구 증가가 잠재 고객 확대로 이어지고 있습니다.",
        "negative": "주변 인구 감소가 잠재 고객 축소로 이어지고 있습니다.",
    },
    "rent_1f": {
        "positive": "임대료 여건이 매출 예측에 긍정적으로 반영되고 있습니다.",
        "negative": "높은 임대료 부담이 순익을 압박할 수 있습니다.",
    },
    "vacancy_rate": {
        "positive": "공실이 적어 상권 활력이 매출에 긍정적으로 반영됩니다.",
        "negative": "공실률 상승이 상권 침체 신호로 매출에 영향을 줍니다.",
    },
    "trend_score": {
        "positive": "업종 검색 트렌드 호조가 수요 증가에 기여하고 있습니다.",
        "negative": "업종 검색 트렌드 감소가 수요 위축 신호로 작용합니다.",
    },
    "bus_flpop": {
        "positive": "대중교통 이용 유동인구 증가가 매출에 긍정적입니다.",
        "negative": "대중교통 이용 유동인구 감소가 매출에 부정적입니다.",
    },
    "floating_pop": {
        "positive": "골목상권 유동인구 증가가 매출 상승에 기여하고 있습니다.",
        "negative": "골목상권 유동인구 감소가 매출에 부정적 영향을 줍니다.",
    },
    "cpi_index": {
        "positive": "물가 지수 변화가 소비 심리에 긍정적으로 작용합니다.",
        "negative": "물가 상승이 소비 심리를 위축시켜 매출에 부정적입니다.",
    },
    "quarter_num": {
        "positive": "현재 분기 계절성이 매출에 유리하게 작용하고 있습니다.",
        "negative": "현재 분기 계절성이 매출에 비우호적으로 작용하고 있습니다.",
    },
}


def _generate_tcn_summary(feature_importance: list[dict], top_n: int = 3, threshold: float = 10_000.0) -> list[str]:
    """TCN SHAP 결과를 자연어 문장으로 요약한다.

    feature_importance는 abs_shap 내림차순으로 정렬된 상태여야 한다.
    abs_shap >= threshold(원 단위)인 상위 top_n개 피처에 대해서만 문장을 생성한다.
    threshold 기본값 10,000원 — 1만원 미만 기여도는 요약 제외.
    """
    sentences = []
    for item in feature_importance[:top_n]:
        if item["abs_shap"] < threshold:
            break
        feat = item["feature"]
        direction = item["direction"]
        if direction == "neutral":
            continue
        template = _TCN_SUMMARY_TEMPLATES.get(feat)
        if template:
            sentences.append(template[direction])
        else:
            feat_ko = item.get("feature_ko", feat)
            direction_ko = "높이는" if direction == "positive" else "낮추는"
            sentences.append(f"{feat_ko}이(가) 매출 예측을 {direction_ko} 방향으로 작용하고 있습니다.")
    return sentences


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
        load_timeseries,
    )
    from models.tcn_forecast.model import TCNForecaster
    from models.tcn_forecast.predict import DEFAULT_PREDICT_CONFIG
    from models.tcn_forecast.train import load_scalers

    # 본 예측(predict.py)과 동일 cfg 공유 — v3 자기회귀(37f, output_size=1, window=4).
    # 2026-05-04: v2 DMS 경로에서 v3 자기회귀로 정합. predict.py 변경 시 SHAP도 자동 추종.
    cfg = DEFAULT_PREDICT_CONFIG
    weights_path = Path(cfg["weights_path"])
    scalers_path = Path(cfg["scalers_path"])

    # ---- 1) 가중치·스케일러 파일 존재 확인 → 없으면 mock ----
    if not weights_path.exists() or not scalers_path.exists():
        _log("WARNING", f"TCN 가중치 또는 스케일러 파일 없음: {weights_path}")
        result = _mock_shap_values(list(ALL_FEATURES), predicted_value=15_000_000.0)
        result["predicted_value_unit"] = "원"
        result["summary"] = []
        return result

    # ---- 2) 스케일러 로드 (캐시 우선) ----
    # NOTE: model은 캐시하지 않음 — asyncio.gather로 4개 동이 동시 실행될 때
    # GradientExplainer가 동일 model 인스턴스에 forward_hook을 동시 등록하면
    # hook 간섭으로 SHAP 값이 오염됨. 스케일러만 캐시하고 model은 호출마다 신규 생성.
    # (weights 파일은 OS 페이지 캐시에 올라온 이후 재로드 ~50ms로 무시 가능)
    _cache_key = (str(weights_path), str(scalers_path))
    if _cache_key in _SHAP_MODEL_CACHE:
        feat_scaler, tgt_scaler, input_size = _SHAP_MODEL_CACHE[_cache_key]
        _log("INFO", f"스케일러 캐시 히트 — input_size={input_size}")
    else:
        try:
            feat_scaler, tgt_scaler = load_scalers(scalers_path)
            input_size = len(feat_scaler.scale_)
            _log("INFO", f"TCN 스케일러 로드 완료: input_size={input_size}")
            _SHAP_MODEL_CACHE[_cache_key] = (feat_scaler, tgt_scaler, input_size)
        except Exception as exc:
            _log("WARNING", f"TCN 스케일러 로드 실패 - mock 반환: {exc}")
            result = _mock_shap_values(list(ALL_FEATURES), predicted_value=15_000_000.0)
            result["predicted_value_unit"] = "원"
            result["summary"] = []
            return result

    # ---- 3) TCN 모델 로드 (호출마다 신규 인스턴스 — hook 간섭 방지) ----
    # 모델 하이퍼파라미터는 predict.py DEFAULT_PREDICT_CONFIG와 1:1 일치.
    try:
        model = TCNForecaster(
            input_size=input_size,
            n_channels=cfg["n_channels"],
            kernel_size=cfg["kernel_size"],
            dilations=cfg["dilations"],
            dropout=cfg["dropout"],
            output_size=cfg["output_size"],  # v3 자기회귀: 1
        )
        model.load_weights(weights_path)
        model.to(torch.device("cuda" if torch.cuda.is_available() else "cpu"))
        model.eval()
        _log("INFO", "TCNForecaster 가중치 로드 완료")
    except Exception as exc:
        _log("WARNING", f"TCN 모델 로드 실패 - mock 반환: {exc}")
        result = _mock_shap_values(list(ALL_FEATURES), predicted_value=15_000_000.0)
        result["predicted_value_unit"] = "원"
        result["summary"] = []
        return result

    # ---- 4) 입력 텐서 준비 — predict.py와 동일 로직 재사용 ----
    window_size = cfg["window_size"]  # v3: 4
    feature_cols = list(ALL_FEATURES)

    try:
        dong_prefix = dong_code[:5] if len(dong_code) >= 5 else dong_code
        ts = load_timeseries(db_url=DB_URL, dong_prefix=dong_prefix)
        group = ts[(ts["dong_code"] == dong_code) & (ts["industry_code"] == industry_code)]

        if group.empty:
            raise ValueError(f"데이터 없음: dong_code={dong_code}, industry_code={industry_code}")

        # 실제 사용 가능한 피처 컬럼만 필터링
        actual_features = [c for c in feature_cols if c in group.columns]

        # 피처 수 불일치: feat_scaler.transform() shape mismatch 방지 → early mock return
        if len(actual_features) != input_size:
            _log(
                "WARNING",
                f"피처 수 불일치 — actual={len(actual_features)}, expected={input_size}. "
                "DB 피처 컬럼 누락 가능성. mock 반환.",
            )
            result = _mock_shap_values(list(feature_cols), predicted_value=15_000_000.0)
            result["predicted_value_unit"] = "원"
            result["summary"] = []
            return result

        group = group.sort_values("quarter")
        recent = group[actual_features].values.astype(np.float32)

        if len(recent) < window_size:
            raise ValueError(f"과거 데이터 부족: {len(recent)}분기 (최소 {window_size}분기 필요)")

        # 피처 스케일링 후 텐서 변환 — shape: (1, window_size, input_size)
        seq = feat_scaler.transform(recent[-window_size:])
        _dev = next(model.parameters()).device
        input_tensor = torch.tensor(seq, dtype=torch.float32).unsqueeze(0).to(_dev)
        _log("INFO", f"입력 텐서 준비 완료: shape={tuple(input_tensor.shape)}")
    except Exception as exc:
        _log("WARNING", f"입력 데이터 준비 실패 - mock 반환: {exc}")
        result = _mock_shap_values(list(feature_cols), predicted_value=15_000_000.0)
        result["predicted_value_unit"] = "원"
        result["summary"] = []
        return result

    # ---- 5) 모델 순전파 — 기준 예측값 확보 (매출액 원 단위) ----
    # v3 자기회귀(output_size=1): 1step 예측에 대한 SHAP 분석.
    # (4step 누적 SHAP은 자기회귀 재주입 그래프가 끊겨 GradientExplainer가 처리 못 함.
    #  사용자에겐 "다음 분기 매출 신호"가 본질이므로 1step만 분석해도 의사결정 충분.)
    with torch.no_grad():
        raw_output = model(input_tensor)
        try:
            raw_arr = raw_output.detach().cpu().numpy().reshape(-1, 1)
            pred_log = float(tgt_scaler.inverse_transform(raw_arr).mean())
            predicted_value = float(np.expm1(pred_log))
        except Exception:
            predicted_value = float(raw_output.mean().item())
    predicted_value = max(0.0, predicted_value)
    _log("INFO", f"TCN 예측값: {predicted_value:,.0f}원")

    # ---- 6) SHAP — GradientExplainer 우선 (TCN Conv1d에 더 안정적), DeepExplainer 2순위 ----
    # background tensor: 종전 zeros 였으나 모든 SHAP 부호가 한 방향으로 쏠리는 트리비얼
    # 패턴(매출 변수만 양수 top3) 발생. StandardScaler 후 입력 분포는 평균0/std1에 근사하므로
    # randn(10,...)을 baseline으로 두면 양/음 기여가 자연스럽게 출현 + 음수 리스크 시그널 노출.
    _dev = next(model.parameters()).device
    _gen = torch.Generator(device="cpu").manual_seed(42)  # 재현성
    background = torch.randn(10, window_size, input_size, generator=_gen).to(_dev)

    shap_values_raw = None
    base_value = 0.0

    try:
        import shap

        _log("INFO", "GradientExplainer 실행 시작 (TCN 1순위)")
        explainer = shap.GradientExplainer(model, background)
        shap_values_raw = explainer.shap_values(input_tensor)
        if hasattr(explainer, "expected_value"):
            _ev = explainer.expected_value
            if isinstance(_ev, np.ndarray):
                base_value = float(_ev.flat[0])
            elif hasattr(_ev, "detach"):  # torch.Tensor
                base_value = float(_ev.detach().cpu().numpy().flat[0])
            else:
                base_value = float(_ev)
        _log("INFO", "GradientExplainer 완료")

    except Exception as grad_exc:
        # GradientExplainer 실패 → DeepExplainer 로 전환
        _log("WARNING", f"GradientExplainer 실패 - DeepExplainer 로 전환: {grad_exc}")
        try:
            import shap

            explainer = shap.DeepExplainer(model, background)
            shap_values_raw = explainer.shap_values(input_tensor)
            _ev = explainer.expected_value
            if isinstance(_ev, np.ndarray):
                base_value = float(_ev.flat[0])
            elif hasattr(_ev, "detach"):  # torch.Tensor
                base_value = float(_ev.detach().cpu().numpy().flat[0])
            else:
                base_value = float(_ev)
            _log("INFO", "DeepExplainer 완료")

        except Exception as deep_exc:
            # 두 explainer 모두 실패 → mock 반환
            _log("WARNING", f"DeepExplainer 도 실패 - mock 반환: {deep_exc}")
            result = _mock_shap_values(feature_cols, predicted_value=predicted_value)
            result["predicted_value_unit"] = "원"
            result["summary"] = []
            return result

    # ---- 7) SHAP 값 후처리: (..., window_size, input_size) → 시간축 평균 → (input_size,) ----
    # v2 DMS (output_size=4): GradientExplainer가 list of 4 arrays 반환 → 4분기 평균
    if isinstance(shap_values_raw, list) and len(shap_values_raw) > 1:
        shap_array = np.mean(np.array(shap_values_raw), axis=0)
    else:
        shap_array = np.array(shap_values_raw)

    # single-output 모델에서 targets=1 축이 말단에 추가되는 경우 squeeze 처리
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
        result = _mock_shap_values(feature_cols, predicted_value=predicted_value)
        result["predicted_value_unit"] = "원"
        result["summary"] = []
        return result

    # 피처 수 불일치 시 맞춰서 잘라냄
    n_feats = min(len(shap_array), len(feature_cols))
    shap_array = shap_array[:n_feats]
    feature_cols = feature_cols[:n_feats]

    # ---- 7.5) SHAP 값을 원(₩) 단위로 변환 ----
    # 모델 출력은 StandardScaler(log1p(revenue)) 공간이므로 shap_value가 수십만~수억 원이 아닌
    # ±0.001~±1.0 수준의 스케일링된 값으로 반환됨.
    # UI formatKrw()는 원 단위를 기대하므로, predicted_value - base_value_won 비율로 선형 스케일링.
    # sum(shap_won) = predicted_value - base_value_won 가산성 보존.
    try:
        base_log = tgt_scaler.inverse_transform([[base_value]])[0][0]
        base_value_won = float(np.expm1(base_log))
        base_value_won = max(0.0, base_value_won)
        delta_won = predicted_value - base_value_won
        shap_sum = float(np.sum(shap_array))
        if abs(shap_sum) > 1e-10:
            shap_array = shap_array * (delta_won / shap_sum)
        else:
            shap_array = np.zeros_like(shap_array)
        base_value = base_value_won
        _log("INFO", f"SHAP 원 단위 변환: base={base_value_won:,.0f}원, delta={delta_won:,.0f}원")
    except Exception as _e:
        _log("WARNING", f"SHAP 원 단위 변환 실패 - predicted_value 비율 적용: {_e}")
        shap_sum = float(np.sum(shap_array))
        if abs(shap_sum) > 1e-10:
            shap_array = shap_array * (predicted_value / shap_sum)
        else:
            shap_array = np.zeros_like(shap_array)
        base_value = 0.0

    # ---- 8) 피처별 기여도 정렬 (절댓값 내림차순) ----
    sorted_indices = np.argsort(-np.abs(shap_array))
    feature_importance = [
        {
            "rank": rank + 1,
            "feature": feature_cols[i],
            "feature_ko": _TCN_FEATURE_KO.get(feature_cols[i], feature_cols[i]),
            "shap_value": round(float(shap_array[i]), 2),
            "abs_shap": round(float(abs(shap_array[i])), 2),
            # 기여 방향: 매출을 높이면 positive, 낮추면 negative
            "direction": "positive" if shap_array[i] > 0 else ("negative" if shap_array[i] < 0 else "neutral"),
        }
        for rank, i in enumerate(sorted_indices)
    ]

    if not feature_importance:
        _log("WARNING", "feature_importance 리스트 비어있음 - mock 반환")
        result = _mock_shap_values(feature_cols, predicted_value=predicted_value)
        result["predicted_value_unit"] = "원"
        result["summary"] = []
        return result

    _log("INFO", f"TCN SHAP 분석 완료 - 최고 기여 피처: {feature_importance[0]['feature_ko']}")

    return {
        "feature_importance": feature_importance,
        "base_value": round(base_value, 2),
        "predicted_value": round(predicted_value, 2),
        "predicted_value_unit": "원",  # 매출 단위 명시 (생존률과 구별)
        "summary": _generate_tcn_summary(feature_importance),
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
            "feature_ko": _TCN_FEATURE_KO.get(feat, feat),
            "feature_en": feat,
            "shap_value": round(float(val), 6),
            "direction": "positive" if val >= 0 else "negative",
        }
        for feat, val in pairs
    ]

    _log("INFO", f"plot_shap_summary 생성 완료 - {len(data)}개 피처")

    return {
        "chart_type": "bar",
        "title": "피처별 SHAP 기여도 (매출 예측)",
        "data": data,
        "x_label": "SHAP 값 (매출 기여도)",
        "y_label": "입력 피처",
    }
