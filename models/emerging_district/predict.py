"""
신흥 상권 조기 감지 추론

predict(dong_code, industry_code) → EmergingResult

담당: B2 — 수지니
"""

from __future__ import annotations

import logging
import pickle
from typing import TypedDict

import numpy as np
import torch
from sklearn.preprocessing import MinMaxScaler

from models.emerging_district.model import WEIGHTS_DIR, LSTMAutoencoder

logger = logging.getLogger(__name__)


class EmergingResult(TypedDict):
    dong_code: str
    industry_code: str
    anomaly_score: float  # 0~1 정규화 이상도 (1에 가까울수록 이상)
    signal: str  # "emerging" | "declining" | "normal"
    consecutive_anomaly_quarters: int
    summary: str  # 자연어 설명
    is_mock: bool


_SIGNAL_KO = {
    "emerging": "신흥 상권",
    "declining": "쇠퇴 상권",
    "normal": "정상",
}

_cache: dict = {}


def _load_model() -> tuple[LSTMAutoencoder, dict]:
    """LSTMAutoencoder + 메타 로드 (캐시)."""
    global _cache  # noqa: PLW0603

    if _cache:
        return _cache["model"], _cache["meta"]

    weights_path = WEIGHTS_DIR / "autoencoder.pt"
    meta_path = WEIGHTS_DIR / "autoencoder_meta.pkl"

    if not weights_path.exists() or not meta_path.exists():
        raise FileNotFoundError(
            f"신흥 상권 모델 가중치를 찾을 수 없습니다.\n"
            f"먼저 학습을 실행하세요: python -m models.emerging_district.train\n"
            f"가중치: {weights_path}"
        )

    with open(meta_path, "rb") as f:
        meta = pickle.load(f)  # noqa: S301

    import torch as _torch
    _device = _torch.device("cuda" if _torch.cuda.is_available() else "cpu")
    model = LSTMAutoencoder(
        input_size=meta["input_size"],
        hidden_size=meta["hidden_size"],
        num_layers=meta["num_layers"],
    )
    model.load_weights(weights_path)
    model.to(_device)
    model.eval()

    _cache.update({"model": model, "meta": meta})
    return model, meta


def _anomaly_score(reconstruction_error: float, threshold: float) -> float:
    """reconstruction error → 0~1 이상도 점수 (threshold 기준 정규화, 최대 1.0 클리핑)."""
    score = reconstruction_error / (threshold + 1e-9)
    return round(min(float(score), 1.0), 4)


def _detect_signal(group_df, window: int = 3) -> str:
    """최근 window 분기 추세로 신흥/쇠퇴 구분.

    신흥: 매출 기울기 > 0 AND 점포 수 기울기 >= 0
    쇠퇴: 매출 기울기 < 0 OR 점포 수 기울기 < 0
    그 외: normal
    """
    if len(group_df) < window:
        return "normal"

    recent = group_df.sort_values("quarter").tail(window)
    x = np.arange(window, dtype=float)
    sales_slope = float(np.polyfit(x, recent["monthly_sales"].values.astype(float), 1)[0])
    store_slope = float(np.polyfit(x, recent["store_count"].values.astype(float), 1)[0])

    if sales_slope > 0 and store_slope >= 0:
        return "emerging"
    if sales_slope < 0 or store_slope < 0:
        return "declining"
    return "normal"


def _count_consecutive_anomalies(
    group_df,
    model: LSTMAutoencoder,
    meta: dict,
    scaler: MinMaxScaler,
) -> int:
    """뒤에서부터 연속 이상 분기(window) 수 카운트."""
    window_size = meta["window_size"]
    feature_names = meta["feature_names"]
    threshold = meta["threshold"]

    group_df = group_df.sort_values("quarter")
    feat_vals = group_df[feature_names].values.astype(np.float32)

    if len(feat_vals) < window_size:
        return 0

    feat_scaled = scaler.transform(feat_vals)
    count = 0

    for i in range(len(feat_scaled) - window_size, -1, -1):
        seq = feat_scaled[i : i + window_size]
        _dev = next(model.parameters()).device
        x_t = torch.from_numpy(seq).unsqueeze(0).to(_dev)  # (1, window, features)
        with torch.no_grad():
            recon = model(x_t)
        err = float(((recon - x_t) ** 2).mean().item())
        if err > threshold:
            count += 1
        else:
            break

    return count


def predict(
    dong_code: str,
    industry_code: str,
    config: dict | None = None,
) -> EmergingResult:
    """특정 동×업종의 신흥 상권 가능성을 추론한다.

    Parameters
    ----------
    dong_code : str
        행정동 코드 (예: '11440660').
    industry_code : str
        업종 코드 (예: 'CS100001').
    config : dict, optional
        db_url 등 설정 오버라이드.

    Returns
    -------
    EmergingResult
        anomaly_score, signal, consecutive_anomaly_quarters, summary.
    """
    cfg = config or {}

    try:
        model, meta = _load_model()
    except FileNotFoundError as e:
        logger.warning("모델 없음 — mock 반환: %s", e)
        return _mock_result(dong_code, industry_code)

    window_size = meta["window_size"]
    feature_names = meta["feature_names"]
    threshold = meta["threshold"]

    # 데이터 로드
    from models.emerging_district.data_prep import DB_URL as _DB_URL  # noqa: E402
    from models.emerging_district.data_prep import load_emerging_data

    db_url = cfg.get("db_url", _DB_URL)
    dong_prefix = dong_code[:5] if len(dong_code) >= 5 else dong_code

    try:
        df = load_emerging_data(db_url=db_url, dong_prefix=dong_prefix)
    except Exception as e:
        logger.warning("데이터 로드 실패 — mock 반환: %s", e)
        return _mock_result(dong_code, industry_code)

    group = df[(df["dong_code"] == dong_code) & (df["industry_code"] == industry_code)].copy()

    if group.empty or len(group) < window_size:
        logger.warning("데이터 부족: %s/%s (%d행)", dong_code, industry_code, len(group))
        return _mock_result(dong_code, industry_code)

    group = group.sort_values("quarter")

    # 그룹 단위 MinMaxScaler (학습 시와 동일한 방식)
    scaler = MinMaxScaler()
    feat_vals = group[feature_names].values.astype(np.float32)
    feat_scaled = scaler.fit_transform(feat_vals)

    # 최근 window_size 분기로 reconstruction error 계산
    recent_seq = feat_scaled[-window_size:]
    _dev = next(model.parameters()).device
    x_t = torch.from_numpy(recent_seq).unsqueeze(0).to(_dev)
    with torch.no_grad():
        recon = model(x_t)
    reconstruction_error = float(((recon - x_t) ** 2).mean().item())

    score = _anomaly_score(reconstruction_error, threshold)

    # 신흥/쇠퇴 구분 (이상 감지 시에만)
    signal = _detect_signal(group) if reconstruction_error > threshold else "normal"

    # 연속 이상 분기 수
    consecutive = _count_consecutive_anomalies(group, model, meta, scaler)

    # 자연어 요약 — dong_code/industry_code 대신 한글명 사용 (사용자 응답 노출)
    from models.interface import _resolve_dong_name, _resolve_industry_name

    dong_name = _resolve_dong_name(dong_code)
    industry_name = _resolve_industry_name(industry_code)

    signal_ko = _SIGNAL_KO.get(signal, signal)
    if signal == "normal":
        summary = f"{dong_name} {industry_name}: 정상 상권 패턴 (이상도 {score:.2f})"
    else:
        q_str = f"최근 {consecutive}분기 연속 이상 감지 " if consecutive > 0 else ""
        summary = f"{dong_name} {industry_name}: {q_str}(이상도 {score:.2f}) — {signal_ko} 가능성"

    return EmergingResult(
        dong_code=dong_code,
        industry_code=industry_code,
        anomaly_score=score,
        signal=signal,
        consecutive_anomaly_quarters=consecutive,
        summary=summary,
        is_mock=False,
    )


def _mock_result(dong_code: str, industry_code: str) -> EmergingResult:
    from models.interface import _resolve_dong_name, _resolve_industry_name

    dong_name = _resolve_dong_name(dong_code)
    industry_name = _resolve_industry_name(industry_code)
    return EmergingResult(
        dong_code=dong_code,
        industry_code=industry_code,
        anomaly_score=0.5,
        signal="normal",
        consecutive_anomaly_quarters=0,
        summary=f"{dong_name} {industry_name}: 모델 미학습 상태 (mock)",
        is_mock=True,
    )
