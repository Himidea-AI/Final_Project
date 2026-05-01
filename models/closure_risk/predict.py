"""
폐업위험도 추론 — LightGBM + TCNClassifier 앙상블

predict(dong_code, industry_code) → closure_risk dict

담당: B2 — 수지니
"""

from __future__ import annotations

import json
import logging
import math
import pickle
from functools import lru_cache

import numpy as np
import torch

from models.closure_risk.model import WEIGHTS_DIR, TCNClassifier
from models.lstm_forecast.data_prep import (
    ALL_FEATURES,
    DB_URL,
    EXCLUDE_COMBOS,
    ExcludedComboError,
    build_timeseries,
    load_sales_data,
    load_store_data,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 위험도 등급
# ---------------------------------------------------------------------------

RISK_LEVELS = [
    (0.65, "danger"),
    (0.40, "caution"),
    (0.00, "safe"),
]


@lru_cache(maxsize=1)
def _load_risk_levels() -> tuple[tuple[float, str], ...]:
    """metrics.json 에서 fit 된 quantile threshold load.

    metrics.json 미존재 / 손상 / thresholds 키 없음 → default fallback.

    Returns:
        ((danger_thr, "danger"), (caution_thr, "caution"), (0.0, "safe"))
    """
    metrics_path = WEIGHTS_DIR / "metrics.json"
    if metrics_path.exists():
        try:
            with open(metrics_path, encoding="utf-8") as f:
                m = json.load(f)
            t = m.get("thresholds", {})
            if "danger" in t and "caution" in t:
                return (
                    (float(t["danger"]), "danger"),
                    (float(t["caution"]), "caution"),
                    (0.0, "safe"),
                )
        except (json.JSONDecodeError, OSError, ValueError) as e:
            logger.warning("metrics.json threshold load 실패 — default fallback: %s", e)
    return ((0.65, "danger"), (0.40, "caution"), (0.0, "safe"))


def _classify(score: float) -> str:
    """위험도 점수 → 레벨. metrics.json fit threshold 우선."""
    for threshold, level in _load_risk_levels():
        if score >= threshold:
            return level
    return "safe"


# ---------------------------------------------------------------------------
# 모델 캐시 (호출마다 재로드 방지)
# ---------------------------------------------------------------------------

_cache: dict = {}


def _load_models() -> tuple:
    """LightGBM, TCNClassifier, 앙상블 가중치, scaler, Stage 1 prior, calibrator 로드 (캐시).

    Returns 6-tuple: (lgbm, tcn, ensemble_w, scaler, stage1_data, calibrator)
    stage1_data is dict {"model": LGBMRegressor, "agg": pd.DataFrame} or None if pkl missing.
    calibrator is sklearn.isotonic.IsotonicRegression or None (D-3, 2026-05-01).
    """
    global _cache  # noqa: PLW0603

    if _cache:
        return (
            _cache["lgbm"],
            _cache["tcn"],
            _cache["weights"],
            _cache["scaler"],
            _cache.get("stage1"),
            _cache.get("calibrator"),
            _cache.get("b3_lookup"),
        )

    lgbm_path = WEIGHTS_DIR / "closure_risk_lgbm.pkl"
    tcn_path = WEIGHTS_DIR / "closure_risk_tcn.pt"
    ew_path = WEIGHTS_DIR / "ensemble_weights.pkl"
    scaler_path = WEIGHTS_DIR / "closure_risk_tcn_scaler.pkl"

    if not lgbm_path.exists() or not tcn_path.exists() or not scaler_path.exists():
        raise FileNotFoundError(
            f"폐업위험도 모델 가중치를 찾을 수 없습니다.\n"
            f"먼저 학습을 실행하세요: python -m models.closure_risk.train\n"
            f"LightGBM: {lgbm_path}\nTCN: {tcn_path}\nScaler: {scaler_path}"
        )

    with open(lgbm_path, "rb") as f:
        lgbm = pickle.load(f)  # noqa: S301

    ensemble_w = {"w_lgbm": 0.5, "w_tcn": 0.5}
    if ew_path.exists():
        with open(ew_path, "rb") as f:
            ensemble_w = pickle.load(f)  # noqa: S301

    import torch as _torch

    _device = _torch.device("cuda" if _torch.cuda.is_available() else "cpu")
    input_size = ensemble_w.get("input_size", 34)
    tcn = TCNClassifier(input_size=input_size)
    tcn.load_weights(tcn_path)
    tcn.to(_device)
    tcn.eval()

    with open(scaler_path, "rb") as f:
        tcn_scaler = pickle.load(f)  # noqa: S301

    # A-2 Stage 1 prior — graceful fallback if missing
    stage1_path = WEIGHTS_DIR / "stage1_industry_prior.pkl"
    stage1_data = None
    if stage1_path.exists():
        try:
            with open(stage1_path, "rb") as f:
                stage1_data = pickle.load(f)  # noqa: S301
            logger.info("Stage 1 industry prior 로드: %s", stage1_path)
        except Exception as e:
            logger.warning("Stage 1 pkl load 실패 — fallback 0.0: %s", e)
            stage1_data = None

    # D-3 isotonic calibrator — graceful fallback (2026-05-01)
    cal_path = WEIGHTS_DIR / "ensemble_calibrator.pkl"
    calibrator = None
    if cal_path.exists():
        try:
            with open(cal_path, "rb") as f:
                calibrator = pickle.load(f)  # noqa: S301
            if calibrator is not None:
                logger.info("ensemble calibrator 로드: %s", cal_path)
        except Exception as e:
            logger.warning("calibrator pkl load 실패 — raw proba 사용: %s", e)
            calibrator = None

    # Sprint 9 (2026-05-01): B-3 dong residual lookup — graceful fallback
    b3_path = WEIGHTS_DIR / "b3_dong_residual_lookup.pkl"
    b3_lookup = None
    if b3_path.exists():
        try:
            with open(b3_path, "rb") as f:
                b3_lookup = pickle.load(f)  # noqa: S301
            logger.info("B-3 dong residual lookup 로드: %s", b3_path)
        except Exception as e:
            logger.warning("B-3 lookup pkl load 실패 — residual=0 fallback: %s", e)
            b3_lookup = None

    _cache.update(
        {
            "lgbm": lgbm,
            "tcn": tcn,
            "weights": ensemble_w,
            "scaler": tcn_scaler,
            "stage1": stage1_data,
            "calibrator": calibrator,
            "b3_lookup": b3_lookup,
        }
    )
    return lgbm, tcn, ensemble_w, tcn_scaler, stage1_data, calibrator, b3_lookup


# ---------------------------------------------------------------------------
# SHAP 상위 기여 피처 추출 (LightGBM)
# ---------------------------------------------------------------------------

_FEATURE_KO = {
    "closure_rate_lag1": "직전 분기 폐업률",
    "closure_rate_lag2": "2분기 전 폐업률",
    "closure_rate_diff": "폐업률 변화량",
    "store_count_lag1": "직전 분기 점포 수",
    "store_change": "점포 수 증감",
    "franchise_ratio": "프랜차이즈 비율",
    "sales_yoy_change": "매출 전년동기 변화율",
    "monthly_sales_lag1": "직전 분기 매출",
    "bus_flpop": "버스 정류장 유동인구",
    "quarter_num": "분기(계절성)",
    "rent_1f_lag1": "직전 분기 1층 임대료",
    "rent_change": "임대료 변화율",
    "vacancy_rate": "공실률",
    "trend_score": "네이버 검색 트렌드",
    "adstrd_flpop": "행정동 유동인구",
    # B-1 신규 (2026-05-01)
    "weekday_sales_yoy": "평일 매출 전년동기 변화율",
    "weekend_sales_yoy": "주말 매출 전년동기 변화율",
    "age_20_sales_ratio": "20대 매출 비중",
    "age_60_sales_ratio": "60대+ 매출 비중",
    "open_close_ratio_lag1": "직전 분기 창업/폐업 비율",
    "total_pop_yoy": "거주인구 전년동기 변화율",
    "holiday_count": "분기 공휴일 수",
    "cpi_index_yoy": "물가 전년동기 변화율",
}

_RISK_SUMMARY_TEMPLATES: dict[str, dict[str, str]] = {
    "closure_rate_lag1": {
        "positive": "직전 분기 폐업률이 높아 위험 신호가 지속되고 있습니다.",
        "negative": "직전 분기 폐업률이 낮아 안정적인 상권 환경입니다.",
    },
    "closure_rate_lag2": {
        "positive": "2분기 전 폐업률이 높아 중기 위험 추세가 나타납니다.",
        "negative": "2분기 전 폐업률이 낮아 안정적 추세가 이어지고 있습니다.",
    },
    "closure_rate_diff": {
        "positive": "폐업률이 증가 추세여서 위험도가 높아지고 있습니다.",
        "negative": "폐업률이 감소 추세여서 위험도가 낮아지고 있습니다.",
    },
    "store_count_lag1": {
        "positive": "점포 수가 많아 경쟁이 치열한 환경입니다.",
        "negative": "점포 수가 적어 경쟁 압력이 낮습니다.",
    },
    "store_change": {
        "positive": "점포 수 감소로 상권 위축 신호가 나타납니다.",
        "negative": "점포 수 증가로 상권이 활성화되고 있습니다.",
    },
    "franchise_ratio": {
        "positive": "프랜차이즈 비율이 높아 경쟁이 심화되고 있습니다.",
        "negative": "프랜차이즈 비율이 낮아 독자적 경쟁 우위가 유지됩니다.",
    },
    "sales_yoy_change": {
        "positive": "전년 동기 대비 매출이 감소해 위험도가 높아집니다.",
        "negative": "전년 동기 대비 매출이 증가해 양호한 상태입니다.",
    },
    "monthly_sales_lag1": {
        "positive": "직전 분기 매출 수준이 높아 기초 체력이 양호합니다.",
        "negative": "직전 분기 매출이 낮아 수익 기반이 취약합니다.",
    },
    "bus_flpop": {
        "positive": "버스 이용 유동인구가 많아 고객 유입이 활발합니다.",
        "negative": "버스 이용 유동인구 감소로 고객 유입이 줄고 있습니다.",
    },
    "quarter_num": {
        "positive": "현재 분기 계절 요인이 폐업 위험에 영향을 주고 있습니다.",
        "negative": "현재 분기 계절 요인이 폐업 위험을 낮추고 있습니다.",
    },
    "rent_1f_lag1": {
        "positive": "임대료 수준이 높아 고정비 부담이 큽니다.",
        "negative": "임대료가 낮아 고정비 부담이 적습니다.",
    },
    "rent_change": {
        "positive": "임대료가 상승세여서 향후 부담이 커질 수 있습니다.",
        "negative": "임대료가 안정적이거나 하락 중입니다.",
    },
    "vacancy_rate": {
        "positive": "공실률이 높아 상권 침체 신호가 있습니다.",
        "negative": "공실률이 낮아 상권이 활발한 상태입니다.",
    },
    "trend_score": {
        "positive": "업종 수요가 감소 중입니다.",
        "negative": "업종 검색 트렌드가 양호합니다.",
    },
    "adstrd_flpop": {
        "positive": "유동인구가 많아 경쟁 환경이 치열합니다.",
        "negative": "유동인구 감소로 고객 유입이 줄고 있습니다.",
    },
    # B-1 신규
    "weekday_sales_yoy": {
        "positive": "평일 매출이 전년 대비 감소해 직장 상권 위험 신호가 나타납니다.",
        "negative": "평일 매출이 전년 대비 증가해 직장 상권이 활성화되고 있습니다.",
    },
    "weekend_sales_yoy": {
        "positive": "주말 매출이 전년 대비 감소해 주거 상권 위험 신호가 나타납니다.",
        "negative": "주말 매출이 전년 대비 증가해 주거 상권이 활성화되고 있습니다.",
    },
    "age_20_sales_ratio": {
        "positive": "20대 매출 비중이 높아 트렌드 의존도가 큽니다.",
        "negative": "20대 매출 비중이 낮아 변동성이 적습니다.",
    },
    "age_60_sales_ratio": {
        "positive": "60대+ 매출 비중이 높아 안정적이나 성장 한계가 있습니다.",
        "negative": "60대+ 매출 비중이 낮아 젊은 고객 유입이 활발합니다.",
    },
    "open_close_ratio_lag1": {
        "positive": "창업이 폐업보다 많아 상권 활성화 흐름입니다.",
        "negative": "폐업이 창업보다 많아 상권 위축 신호입니다.",
    },
    "total_pop_yoy": {
        "positive": "거주인구가 증가해 잠재 수요가 늘고 있습니다.",
        "negative": "거주인구가 감소해 수요 기반이 약해지고 있습니다.",
    },
    "holiday_count": {
        "positive": "공휴일 수가 많아 외식/소비 기회가 증가합니다.",
        "negative": "공휴일 수가 적어 평상 영업일 의존도가 큽니다.",
    },
    "cpi_index_yoy": {
        "positive": "물가 상승으로 비용 압박이 커지고 있습니다.",
        "negative": "물가 안정으로 비용 부담이 적습니다.",
    },
}


def _top_signals(lgbm_model, x_row: np.ndarray, feature_names: list[str], top_n: int = 3) -> list[dict]:
    """LightGBM SHAP 기반 상위 기여 피처 반환."""
    try:
        import shap

        explainer = shap.TreeExplainer(lgbm_model)
        shap_vals = explainer.shap_values(x_row.reshape(1, -1))
        # 이진 분류: shap_values[1] = 고위험 방향 기여
        vals = shap_vals[1][0] if isinstance(shap_vals, list) else shap_vals[0]
        top_idx = np.argsort(np.abs(vals))[::-1][:top_n]
        return [
            {
                "feature": _FEATURE_KO.get(feature_names[i], feature_names[i]),
                "feature_key": feature_names[i],
                "contribution": round(float(vals[i]), 4),
            }
            for i in top_idx
        ]
    except Exception:
        return []


class _TCNWithSigmoid(torch.nn.Module):
    """GradientExplainer용 sigmoid 래퍼 — 확률 단위로 SHAP 계산."""

    def __init__(self, model: torch.nn.Module) -> None:
        super().__init__()
        self.model = model

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.sigmoid(self.model(x))


def _top_signals_tcn(
    tcn_model: torch.nn.Module,
    x_seq: torch.Tensor,
    feature_names: list[str],
    top_n: int = 3,
) -> list[dict]:
    """TCN SHAP 기반 상위 기여 피처 반환 (GradientExplainer → DeepExplainer fallback)."""
    from models.explainability.shap_analysis import _TCN_FEATURE_KO

    try:
        import shap

        wrapped = _TCNWithSigmoid(tcn_model)
        wrapped.eval()
        _dev = next(tcn_model.parameters()).device
        window_size = x_seq.shape[1]
        input_size = x_seq.shape[2]
        background = torch.zeros(10, window_size, input_size).to(_dev)
        x_seq = x_seq.to(_dev)

        shap_values_raw = None
        try:
            explainer = shap.GradientExplainer(wrapped, background)
            shap_values_raw = explainer.shap_values(x_seq)
        except Exception:
            explainer = shap.DeepExplainer(wrapped, background)
            shap_values_raw = explainer.shap_values(x_seq)

        shap_array = np.array(shap_values_raw)
        if shap_array.ndim >= 3 and shap_array.shape[-1] == 1:
            shap_array = shap_array.squeeze(-1)
        while shap_array.ndim >= 4:
            shap_array = shap_array[0]
        if shap_array.ndim == 3:
            shap_array = shap_array[0]
        if shap_array.ndim == 2:
            shap_array = shap_array.mean(axis=0)
        if shap_array.ndim != 1:
            return []

        n_feats = min(len(shap_array), len(feature_names))
        shap_array = shap_array[:n_feats]
        feat_names = feature_names[:n_feats]

        top_idx = np.argsort(np.abs(shap_array))[::-1][:top_n]
        return [
            {
                "feature": _TCN_FEATURE_KO.get(feat_names[i], feat_names[i]),
                "feature_key": feat_names[i],
                "contribution": round(float(shap_array[i]), 4),
            }
            for i in top_idx
        ]
    except Exception:
        return []


def _generate_risk_summary(top_signals: list[dict], threshold: float = 0.005) -> list[str]:
    """폐업위험도 SHAP 결과를 자연어 문장으로 요약한다."""
    sentences = []
    for item in top_signals:
        contribution = item.get("contribution", 0.0)
        if abs(contribution) < threshold:
            continue
        feat_key = item.get("feature_key", "")
        direction = "positive" if contribution > 0 else "negative"
        template = _RISK_SUMMARY_TEMPLATES.get(feat_key)
        if template:
            sentences.append(template[direction])
        else:
            feat_ko = item.get("feature", feat_key)
            direction_ko = "높이는" if direction == "positive" else "낮추는"
            sentences.append(f"{feat_ko}이(가) 폐업 위험도를 {direction_ko} 방향으로 작용하고 있습니다.")
    return sentences


# ---------------------------------------------------------------------------
# 메인 추론 함수
# ---------------------------------------------------------------------------


def predict(
    dong_code: str,
    industry_code: str,
    config: dict | None = None,
) -> dict:
    """특정 동x업종의 폐업위험도를 예측한다.

    Parameters
    ----------
    dong_code : str
        행정동 코드 (예: '11440555').
    industry_code : str
        업종 코드 (예: 'CS100001').
    config : dict, optional
        설정 오버라이드 (db_url 등).

    Returns
    -------
    dict
        {
            "risk_score": float,           # 폐업 위험 확률 (0~1). 실패 시 None.
            "risk_level": str,             # "safe" / "caution" / "danger" / "unknown"
            "top_signals_lgbm": list[dict],# LightGBM SHAP 상위 기여 피처 (과거 패턴 기반)
            "summary_lgbm": list[str],     # LightGBM SHAP 자연어 요약
            "top_signals_tcn": list[dict], # TCN SHAP 상위 기여 피처 (시계열 흐름 기반)
            "summary_tcn": list[str],      # TCN SHAP 자연어 요약
            "model": str,                  # "lgbm_tcn_ensemble"
            "is_mock": bool,
        }
    """
    cfg = config or {}

    # EXCLUDE_COMBOS 차단 — 학습 제외 조합은 추론도 제공하지 않음
    if (dong_code, industry_code) in EXCLUDE_COMBOS:
        raise ExcludedComboError(
            f"해당 조합은 데이터 부족으로 예측을 제공하지 않습니다: "
            f"dong_code={dong_code}, industry_code={industry_code}"
        )

    db_url = cfg.get("db_url", DB_URL)
    window_size = 4

    try:
        lgbm_model, tcn_model, ensemble_w, tcn_scaler, stage1_data, calibrator, b3_lookup = _load_models()
    except FileNotFoundError as e:
        logger.warning("모델 없음 — mock 반환: %s", e)
        return _mock_result()

    # 과거 데이터 로드
    dong_prefix = dong_code[:5] if len(dong_code) >= 5 else dong_code
    try:
        sales_df = load_sales_data(db_url=db_url, dong_prefix=dong_prefix)
        store_df = load_store_data(db_url=db_url, dong_prefix=dong_prefix)
        ts = build_timeseries(sales_df, store_df)
    except Exception as e:
        logger.warning("데이터 로드 실패 — mock 반환: %s", e)
        return _mock_result()

    group = ts[(ts["dong_code"] == dong_code) & (ts["industry_code"] == industry_code)]
    if group.empty or len(group) < window_size:
        logger.warning("데이터 부족: %s/%s", dong_code, industry_code)
        return _mock_result()

    group = group.sort_values("quarter")

    # --- LightGBM 브랜치 피처 계산 ---
    from models.closure_risk.data_prep import LGBM_FEATURES, _engineer_lag_features

    ts_eng = _engineer_lag_features(ts)
    grp_eng = ts_eng[(ts_eng["dong_code"] == dong_code) & (ts_eng["industry_code"] == industry_code)]
    grp_eng = grp_eng.sort_values("quarter")

    if grp_eng.empty:
        return _mock_result()

    latest = grp_eng.iloc[-1]

    # A-2 Stage 1 prior lookup
    industry_prior_pred = 0.0
    if stage1_data is not None:
        agg = stage1_data["agg"]
        latest_quarter = int(latest["quarter"])
        matching = agg[(agg["industry_code"] == industry_code) & (agg["quarter"] == latest_quarter)]
        if len(matching) > 0:
            if "industry_prior_pred" in matching.columns:
                industry_prior_pred = float(matching["industry_prior_pred"].iloc[0])
            else:
                # agg 에 prediction 미저장 → on-the-fly
                from models.closure_risk.stage1_industry_prior import STAGE1_FEATURES

                X_stage1 = matching[STAGE1_FEATURES].fillna(0).values
                industry_prior_pred = float(stage1_data["model"].predict(X_stage1)[0])

    # Sprint 9 (2026-05-01): B-3 dong residual lookup at inference
    dong_residual_lag1 = 0.0
    if b3_lookup is not None:
        ind_mean = b3_lookup.get("industry_mean_lag1", {}).get(industry_code, b3_lookup.get("global_mean_lag1", 0.0))
        closure_lag1 = float(latest.get("closure_rate_lag1", 0.0) or 0.0)
        dong_residual_lag1 = closure_lag1 - ind_mean

    def _feature_value(f: str) -> float:
        if f == "industry_prior_pred":
            return industry_prior_pred
        if f == "dong_closure_rate_residual_lag1":
            return dong_residual_lag1
        return float(latest.get(f, 0.0) or 0.0)

    x_lgbm = np.array([_feature_value(f) for f in LGBM_FEATURES], dtype=np.float32)
    p_lgbm = float(lgbm_model.predict_proba(x_lgbm.reshape(1, -1))[0, 1])

    # --- TCN 브랜치 ---
    # ALL_FEATURES 전체 사용 — 누락 피처는 0으로 패딩
    tcn_features = list(ALL_FEATURES)
    group = group.copy()
    for col in tcn_features:
        if col not in group.columns:
            group[col] = 0.0

    recent = group[tcn_features].values.astype(np.float32)
    seq = tcn_scaler.transform(recent[-window_size:])

    tcn_model.eval()
    _dev = next(tcn_model.parameters()).device
    x_tcn = torch.from_numpy(seq).unsqueeze(0).to(_dev)  # (1, 4, features)
    with torch.no_grad():
        p_tcn = float(torch.sigmoid(tcn_model(x_tcn)).cpu().numpy().flatten()[0])

    # --- 앙상블 ---
    w_lgbm = ensemble_w.get("w_lgbm", 0.5)
    w_tcn = ensemble_w.get("w_tcn", 0.5)
    raw_score = (w_lgbm * p_lgbm + w_tcn * p_tcn) / (w_lgbm + w_tcn)

    # D-3 isotonic calibration (2026-05-01) — graceful fallback if calibrator None
    if calibrator is not None:
        risk_score = float(calibrator.transform([raw_score])[0])
    else:
        risk_score = raw_score
    risk_score = round(risk_score, 4)

    # --- SHAP (LightGBM + TCN 분리) ---
    # LightGBM: 전체 피처(15개) SHAP 모두 반환 — frontend heatmap 에서 작은 contribution 도
    # alpha 약하게 시각화하여 "이 피처는 위험에 영향 없음" 도 정직히 표현.
    lgbm_signals = _top_signals(lgbm_model, x_lgbm, LGBM_FEATURES, top_n=len(LGBM_FEATURES))
    tcn_signals = _top_signals_tcn(tcn_model, x_tcn, tcn_features)

    return {
        "risk_score": risk_score,
        "risk_level": _classify(risk_score),
        "top_signals_lgbm": lgbm_signals,
        "summary_lgbm": _generate_risk_summary(lgbm_signals),
        "top_signals_tcn": tcn_signals,
        "summary_tcn": _generate_risk_summary(tcn_signals),
        "model": "lgbm_tcn_ensemble",
        "is_mock": False,
    }


def _mock_result() -> dict:
    return {
        "risk_score": None,
        "risk_level": "unknown",
        "top_signals_lgbm": [],
        "summary_lgbm": [],
        "top_signals_tcn": [],
        "summary_tcn": [],
        "model": "lgbm_tcn_ensemble",
        "is_mock": True,
    }


def predict_topk(
    targets: list[tuple[str, str]],
    k_pct: int = 10,
    config: dict | None = None,
) -> list[dict]:
    """다수 (dong, industry) 조합에서 위험도 top K% 추천.

    Args:
        targets: (dong_code, industry_code) tuple list. EXCLUDE_COMBOS 자동 제외.
            빈 list 입력 → [] 반환.
        k_pct: 상위 K% (1~100). 1 미만 → 1, 100 초과 → 100 으로 clamp.
        config: db_url 등 override (predict() 의 config 와 동일).

    Returns:
        list[dict] — 각 dict 키:
            "dong_code": str,
            "industry_code": str,
            "risk_score": float | None,
            "risk_level": str,
            "rank": int (1부터, top=1),
            "top_signals_lgbm": list[dict],
            "top_signals_tcn": list[dict],
            "summary_lgbm": list[str],
            "summary_tcn": list[str],
            "is_mock": bool,
            "model": str,

        길이 = max(1, ceil(n_valid * k_pct / 100)).
        risk_score=None (is_mock=True) 결과는 sort 시 마지막.

    Note:
        - EXCLUDE_COMBOS 의 target 은 자동 제외 + log info
        - cache (`_load_models`) 재사용 — N=160 (마포 16동 × 10업종) 도 1회 model load
    """
    if not targets:
        return []

    k_pct = max(1, min(100, k_pct))

    valid = [(d, i) for (d, i) in targets if (d, i) not in EXCLUDE_COMBOS]
    excluded_n = len(targets) - len(valid)
    if excluded_n > 0:
        logger.info("predict_topk: EXCLUDE_COMBOS %d targets 제외", excluded_n)

    if not valid:
        return []

    results = []
    for dong, industry in valid:
        try:
            res = predict(dong, industry, config=config)
        except ExcludedComboError:
            continue
        results.append({"dong_code": dong, "industry_code": industry, **res})

    def _sort_key(r):
        score = r.get("risk_score")
        return (1 if score is None else 0, -(score if score is not None else 0))

    results.sort(key=_sort_key)

    n = len(results)
    k = max(1, math.ceil(n * k_pct / 100))
    top = results[:k]

    for i, r in enumerate(top, start=1):
        r["rank"] = i

    return top
