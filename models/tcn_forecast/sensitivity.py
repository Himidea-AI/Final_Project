"""
TCN 시나리오 시뮬레이터 — 사전 배치 섭동 분석

슬라이더 5개(임대료/공실률/유동인구/트렌드/계절)에 대해
156개 (동×업종) 조합의 탄성치 테이블을 사전 계산하여 JSON으로 저장한다.

실행 방법:
    python -m models.tcn_forecast.sensitivity

저장 위치:
    models/tcn_forecast/weights/sensitivity_cache.json
    models/tcn_forecast/weights/feature_correlations.json

담당: B2 — 수지니
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    import sklearn.preprocessing
    import torch

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

# 슬라이더명 → 실제 TCN 피처 목록 (유동인구는 3개 동시 적용)
SLIDER_FEATURES: dict[str, list[str]] = {
    "rent_1f": ["rent_1f"],
    "vacancy_rate": ["vacancy_rate"],
    "floating_pop": ["bus_flpop", "adstrd_flpop", "floating_pop"],
    "trend_score": ["trend_score"],
}

# ±% 섭동 레벨 (quarter_num 제외)
PERTURBATION_LEVELS: list[int] = [-30, -20, -10, 0, 10, 20, 30]

# quarter_num 슬라이더용 분기 값 (categorical)
QUARTER_VALUES: dict[str, int] = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}

# Pearson 상관계수 계산 대상 피처 쌍
CORRELATION_PAIRS: list[tuple[str, str]] = [
    ("floating_pop", "rent_1f"),
    ("floating_pop", "vacancy_rate"),
    ("rent_1f", "vacancy_rate"),
]


# ---------------------------------------------------------------------------
# 헬퍼 함수 (단위 테스트 가능)
# ---------------------------------------------------------------------------


def get_feature_indices(feature_names: list[str], target_features: list[str]) -> list[int]:
    """feature_names 리스트에서 target_features의 인덱스를 반환한다.

    Parameters
    ----------
    feature_names : list[str]
        TCN 입력 피처 전체 목록 (ALL_FEATURES 순서).
    target_features : list[str]
        인덱스를 찾을 피처명 목록.

    Returns
    -------
    list[int]
        target_features 각각의 feature_names 내 인덱스.
        없는 피처는 무시한다.
    """
    name_to_idx = {name: i for i, name in enumerate(feature_names)}
    return [name_to_idx[f] for f in target_features if f in name_to_idx]


def compute_correlations(df: pd.DataFrame) -> dict[str, float]:
    """학습 데이터 DataFrame에서 슬라이더 피처 간 Pearson 상관계수를 계산한다.

    Parameters
    ----------
    df : pd.DataFrame
        슬라이더 피처 컬럼을 포함하는 데이터프레임.

    Returns
    -------
    dict[str, float]
        {"floating_pop→rent_1f": 0.63, ...} 형태의 상관계수 딕셔너리.
        소수점 4자리 반올림.
    """
    result: dict[str, float] = {}
    for f1, f2 in CORRELATION_PAIRS:
        if f1 in df.columns and f2 in df.columns:
            valid = df[[f1, f2]].dropna()
            if len(valid) >= 2:
                corr = valid[f1].corr(valid[f2])
                result[f"{f1}→{f2}"] = round(float(corr), 4)
    return result


# ---------------------------------------------------------------------------
# 섭동 추론
# ---------------------------------------------------------------------------


def perturb_and_predict(
    seq_scaled: np.ndarray,
    feature_indices: list[int],
    delta_pct: float,
    model: torch.nn.Module,
    tgt_scaler: sklearn.preprocessing.StandardScaler,
    device: torch.device,
) -> float:
    """특정 피처를 delta_pct% 변화시킨 후 TCN v2로 예측하여 4분기 평균 매출(원)을 반환한다.

    Parameters
    ----------
    seq_scaled : np.ndarray
        shape (window_size, n_features). feat_scaler로 스케일링된 입력 시퀀스.
    feature_indices : list[int]
        섭동할 피처 인덱스 목록 (유동인구는 3개 동시 섭동).
    delta_pct : float
        변화율 (%). 예: 10.0 → +10%, -20.0 → -20%.
    model : TCNForecaster
        eval 모드의 TCN v2 모델 인스턴스.
    tgt_scaler : StandardScaler
        타겟 역변환용 스케일러.
    device : torch.device
        추론 디바이스 (CPU/CUDA).

    Returns
    -------
    float
        4분기 예측 매출 평균 (원 단위).
    """
    import torch

    seq_perturbed = seq_scaled.copy()
    for idx in feature_indices:
        seq_perturbed[:, idx] *= 1.0 + delta_pct / 100.0

    with torch.no_grad():
        t = torch.tensor(seq_perturbed, dtype=torch.float32).unsqueeze(0).to(device)
        raw = model(t)  # (1, 4)
        raw_arr = raw.cpu().numpy().reshape(-1, 1)  # (4, 1)
        pred_log = float(tgt_scaler.inverse_transform(raw_arr).mean())
        return max(0.0, float(np.expm1(pred_log)))


def perturb_quarter_and_predict(
    seq_scaled: np.ndarray,
    quarter_idx: int,
    quarter_value: int,
    feat_scaler: sklearn.preprocessing.StandardScaler,
    model: torch.nn.Module,
    tgt_scaler: sklearn.preprocessing.StandardScaler,
    device: torch.device,
) -> float:
    """quarter_num을 특정 분기값으로 설정 후 예측하여 4분기 평균 매출(원)을 반환한다.

    quarter_num은 ±% 섭동이 아닌 절댓값(1~4)으로 교체한다.
    feat_scaler로 다시 역변환 후 재스케일링하는 대신, 스케일링된 공간에서
    (quarter_value - scaler_mean) / scaler_std 로 직접 치환한다.

    Parameters
    ----------
    seq_scaled : np.ndarray
        shape (window_size, n_features). feat_scaler로 스케일링된 입력 시퀀스.
    quarter_idx : int
        ALL_FEATURES 내 quarter_num의 인덱스.
    quarter_value : int
        설정할 분기값 (1, 2, 3, 4).
    feat_scaler : StandardScaler
        피처 스케일러 (mean_, scale_ 접근용).
    model, tgt_scaler, device : 위와 동일.

    Returns
    -------
    float
        4분기 예측 매출 평균 (원 단위).
    """
    import torch

    seq_perturbed = seq_scaled.copy()
    # StandardScaler: scaled = (x - mean) / std
    mean_val = float(feat_scaler.mean_[quarter_idx])
    std_val = float(feat_scaler.scale_[quarter_idx])
    scaled_quarter = (quarter_value - mean_val) / std_val if std_val > 1e-10 else 0.0
    seq_perturbed[:, quarter_idx] = scaled_quarter

    with torch.no_grad():
        t = torch.tensor(seq_perturbed, dtype=torch.float32).unsqueeze(0).to(device)
        raw = model(t)  # (1, 4)
        raw_arr = raw.cpu().numpy().reshape(-1, 1)
        pred_log = float(tgt_scaler.inverse_transform(raw_arr).mean())
        return max(0.0, float(np.expm1(pred_log)))


# ---------------------------------------------------------------------------
# 배치 메인 러너
# ---------------------------------------------------------------------------


def run_batch(
    output_cache_path: Path | None = None,
    output_corr_path: Path | None = None,
) -> None:
    """156개 (동×업종) 조합 전체의 탄성치 테이블과 상관계수를 계산하여 JSON으로 저장한다.

    Parameters
    ----------
    output_cache_path : Path, optional
        탄성치 캐시 저장 경로. 기본: weights/sensitivity_cache.json
    output_corr_path : Path, optional
        상관계수 저장 경로. 기본: weights/feature_correlations.json
    """
    import torch

    from models.lstm_forecast.data_prep import (
        ALL_FEATURES,
        DB_URL,
        EXCLUDE_COMBOS,
        load_timeseries,
    )
    from models.tcn_forecast.model import WEIGHTS_DIR, TCNForecaster
    from models.tcn_forecast.train import load_scalers

    if output_cache_path is None:
        output_cache_path = WEIGHTS_DIR / "sensitivity_cache.json"
    if output_corr_path is None:
        output_corr_path = WEIGHTS_DIR / "feature_correlations.json"

    weights_path = WEIGHTS_DIR / "finetuned_mapo_tcn_v2.pt"
    scalers_path = WEIGHTS_DIR / "finetune_tcn_scalers_v2.pkl"

    if not weights_path.exists() or not scalers_path.exists():
        raise FileNotFoundError(f"v2 가중치 또는 스케일러 파일 없음: {weights_path}, {scalers_path}")

    # 모델 + 스케일러 로드
    feat_scaler, tgt_scaler = load_scalers(scalers_path)
    input_size = len(feat_scaler.scale_)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model = TCNForecaster(
        input_size=input_size,
        n_channels=128,
        kernel_size=2,
        dilations=[1, 2, 4, 8],
        dropout=0.2,
        output_size=4,
    )
    model.load_weights(weights_path)
    model.to(device)
    model.eval()
    logger.info("TCNForecaster v2 로드 완료 (input_size=%d)", input_size)

    feature_names = list(ALL_FEATURES)
    window_size = 12

    # 학습 데이터 전체 로드 (상관계수 계산 + 유효 조합 추출)
    logger.info("시계열 데이터 로드 중...")
    ts = load_timeseries(db_url=DB_URL, dong_prefix="1144")  # 마포구 전체
    logger.info("데이터 로드 완료: %d 행", len(ts))

    # 상관계수 계산 (전체 데이터 기반)
    correlations = compute_correlations(ts)
    logger.info("상관계수 계산 완료: %s", correlations)

    # 유효 (dong_code, industry_code) 조합 추출 (window_size 이상 데이터 보유)
    valid_combos = []
    for (dong_code, industry_code), group in ts.groupby(["dong_code", "industry_code"]):
        dong_code, industry_code = str(dong_code), str(industry_code)
        if (dong_code, industry_code) in EXCLUDE_COMBOS:
            continue
        if len(group) >= window_size:
            valid_combos.append((dong_code, industry_code))

    logger.info("유효 조합 수: %d", len(valid_combos))

    # quarter_num 인덱스 확인
    quarter_idx_list = get_feature_indices(feature_names, ["quarter_num"])
    quarter_idx = quarter_idx_list[0] if quarter_idx_list else None

    cache: dict = {}
    total = len(valid_combos)

    for idx, (dong_code, industry_code) in enumerate(valid_combos):
        key = f"{dong_code}_{industry_code}"
        logger.info("[%d/%d] 처리 중: %s", idx + 1, total, key)

        group = ts[(ts["dong_code"] == dong_code) & (ts["industry_code"] == industry_code)]
        group = group.sort_values("quarter")
        actual_features = [c for c in feature_names if c in group.columns]

        if len(actual_features) != input_size:
            logger.warning("피처 수 불일치 (%s): skip", key)
            continue

        recent = group[actual_features].values.astype(np.float32)
        if len(recent) < window_size:
            pad_size = window_size - len(recent)
            recent = np.vstack([np.tile(recent[0], (pad_size, 1)), recent])

        seq_scaled = feat_scaler.transform(recent[-window_size:])

        # 기준 예측 (delta=0)
        baseline_raw = perturb_and_predict(seq_scaled, [], 0.0, model, tgt_scaler, device)
        # 4분기 개별 값도 저장 (분기별 차트용)
        with torch.no_grad():
            t = torch.tensor(seq_scaled, dtype=torch.float32).unsqueeze(0).to(device)
            raw = model(t).cpu().numpy().flatten()
        baseline_q = []
        for ps in raw:
            pred_log = float(tgt_scaler.inverse_transform([[float(ps)]])[0][0])
            baseline_q.append(round(max(0.0, float(np.expm1(pred_log))), 0))

        elasticity: dict[str, dict] = {}

        # ±% 슬라이더 (4개)
        for slider_name, target_feats in SLIDER_FEATURES.items():
            feat_indices = get_feature_indices(actual_features, target_feats)
            if not feat_indices:
                continue
            level_results: dict[str, float] = {}
            for delta in PERTURBATION_LEVELS:
                pred = perturb_and_predict(seq_scaled, feat_indices, float(delta), model, tgt_scaler, device)
                if baseline_raw > 0:
                    elast = round((pred - baseline_raw) / baseline_raw * 100.0, 4)
                else:
                    elast = 0.0
                key_str = f"{'+' if delta > 0 else ''}{delta}"
                level_results[key_str] = elast
            elasticity[slider_name] = level_results

        # quarter_num 슬라이더 (categorical)
        if quarter_idx is not None and "quarter_num" in actual_features:
            q_results: dict[str, float] = {}
            for q_label, q_val in QUARTER_VALUES.items():
                pred = perturb_quarter_and_predict(
                    seq_scaled, quarter_idx, q_val, feat_scaler, model, tgt_scaler, device
                )
                if baseline_raw > 0:
                    elast = round((pred - baseline_raw) / baseline_raw * 100.0, 4)
                else:
                    elast = 0.0
                q_results[q_label] = elast
            elasticity["quarter_num"] = q_results

        cache[f"{dong_code}_{industry_code}"] = {
            "baseline": baseline_q,
            "elasticity": elasticity,
        }

    # JSON 저장
    output_cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    logger.info("탄성치 캐시 저장: %s (%d 조합)", output_cache_path, len(cache))

    with open(output_corr_path, "w", encoding="utf-8") as f:
        json.dump(correlations, f, ensure_ascii=False, indent=2)
    logger.info("상관계수 저장: %s", output_corr_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run_batch()
