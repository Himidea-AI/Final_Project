"""
폐업위험도 추론 — LightGBM + TCNClassifier 앙상블

predict(dong_code, industry_code) → closure_risk dict

담당: B2 — 수지니
"""

from __future__ import annotations

import logging
import pickle

import numpy as np
import torch

from models.closure_risk.model import WEIGHTS_DIR, TCNClassifier
from models.lstm_forecast.data_prep import ALL_FEATURES, DB_URL, build_timeseries, load_sales_data, load_store_data

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 위험도 등급
# ---------------------------------------------------------------------------

RISK_LEVELS = [
    (0.65, "danger"),
    (0.40, "caution"),
    (0.00, "safe"),
]


def _classify(score: float) -> str:
    for threshold, level in RISK_LEVELS:
        if score >= threshold:
            return level
    return "safe"


# ---------------------------------------------------------------------------
# 모델 캐시 (호출마다 재로드 방지)
# ---------------------------------------------------------------------------

_cache: dict = {}


def _load_models() -> tuple:
    """LightGBM, TCNClassifier, 앙상블 가중치 로드 (캐시)."""
    global _cache  # noqa: PLW0603

    if _cache:
        return _cache["lgbm"], _cache["tcn"], _cache["weights"]

    lgbm_path = WEIGHTS_DIR / "closure_risk_lgbm.pkl"
    tcn_path = WEIGHTS_DIR / "closure_risk_tcn.pt"
    ew_path = WEIGHTS_DIR / "ensemble_weights.pkl"

    if not lgbm_path.exists() or not tcn_path.exists():
        raise FileNotFoundError(
            f"폐업위험도 모델 가중치를 찾을 수 없습니다.\n"
            f"먼저 학습을 실행하세요: python -m models.closure_risk.train\n"
            f"LightGBM: {lgbm_path}\nTCN: {tcn_path}"
        )

    with open(lgbm_path, "rb") as f:
        lgbm = pickle.load(f)  # noqa: S301

    ensemble_w = {"w_lgbm": 0.5, "w_tcn": 0.5}
    if ew_path.exists():
        with open(ew_path, "rb") as f:
            ensemble_w = pickle.load(f)  # noqa: S301

    # TCN 모델 — input_size는 ensemble_weights에 저장된 값 사용 (기본 33)
    input_size = ensemble_w.get("input_size", 33)
    tcn = TCNClassifier(input_size=input_size)
    tcn.load_weights(tcn_path)
    tcn.eval()

    _cache.update({"lgbm": lgbm, "tcn": tcn, "weights": ensemble_w})
    return lgbm, tcn, ensemble_w


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
    "rent_1f": "1층 임대료",
    "vacancy_rate": "공실률",
    "quarter_num": "분기(계절성)",
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
                "contribution": round(float(vals[i]), 4),
            }
            for i in top_idx
        ]
    except Exception:
        return []


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
            "risk_score": float,      # 폐업 위험 확률 (0~1)
            "risk_level": str,        # "safe" / "caution" / "danger"
            "top_signals": list[dict],# 상위 기여 피처 (SHAP)
            "model": str,             # "lgbm_tcn_ensemble"
            "is_mock": bool,
        }
    """
    cfg = config or {}
    db_url = cfg.get("db_url", DB_URL)
    window_size = 4

    try:
        lgbm_model, tcn_model, ensemble_w = _load_models()
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
    x_lgbm = np.array([latest.get(f, 0.0) for f in LGBM_FEATURES], dtype=np.float32)
    p_lgbm = float(lgbm_model.predict_proba(x_lgbm.reshape(1, -1))[0, 1])

    # --- TCN 브랜치 ---
    from sklearn.preprocessing import MinMaxScaler

    # 누락 피처는 0으로 패딩 — 학습 시 input_size(len(ALL_FEATURES))와 일치 보장
    group = group.copy()
    for col in ALL_FEATURES:
        if col not in group.columns:
            group[col] = 0.0

    scaler = MinMaxScaler()
    recent = group[ALL_FEATURES].values.astype(np.float32)
    seq = scaler.fit_transform(recent[-window_size:])

    tcn_model.eval()
    with torch.no_grad():
        x_tcn = torch.from_numpy(seq).unsqueeze(0)  # (1, 4, features)
        p_tcn = float(torch.sigmoid(tcn_model(x_tcn)).cpu().numpy().flatten()[0])

    # --- 앙상블 ---
    w_lgbm = ensemble_w.get("w_lgbm", 0.5)
    w_tcn = ensemble_w.get("w_tcn", 0.5)
    risk_score = round((w_lgbm * p_lgbm + w_tcn * p_tcn) / (w_lgbm + w_tcn), 4)

    top_signals = _top_signals(lgbm_model, x_lgbm, LGBM_FEATURES)

    return {
        "risk_score": risk_score,
        "risk_level": _classify(risk_score),
        "top_signals": top_signals,
        "model": "lgbm_tcn_ensemble",
        "is_mock": False,
    }


def _mock_result() -> dict:
    return {
        "risk_score": 0.42,
        "risk_level": "caution",
        "top_signals": [
            {"feature": "직전 분기 폐업률", "contribution": 0.18},
            {"feature": "점포 수 증감", "contribution": -0.12},
            {"feature": "매출 전년동기 변화율", "contribution": -0.09},
        ],
        "model": "lgbm_tcn_ensemble",
        "is_mock": True,
    }
