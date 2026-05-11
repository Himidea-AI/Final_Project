"""
TCN 시나리오 시뮬레이터 — 사전 배치 섭동 분석

슬라이더 5개(공실률/물가/상권 활성도/트렌드/계절)에 대해
156개 (동×업종) 조합의 분기별 탄성치 테이블을 사전 계산하여 JSON으로 저장한다.

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

# 슬라이더명 → 실제 TCN 피처 목록
SLIDER_FEATURES: dict[str, list[str]] = {
    "vacancy_rate": ["vacancy_rate"],
    "trend_score": ["trend_score"],
    "cpi_index": ["cpi_index"],
    "opr_sale_mt_avg": ["opr_sale_mt_avg"],
}

# ±% 섭동 레벨 (quarter_num 제외)
PERTURBATION_LEVELS: list[int] = [-30, -20, -10, 0, 10, 20, 30]

# quarter_num 슬라이더용 분기 값 (categorical)
QUARTER_VALUES: dict[str, int] = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}

# Pearson 상관계수 계산 대상 피처 쌍
CORRELATION_PAIRS: list[tuple[str, str]] = [
    ("vacancy_rate", "cpi_index"),
    ("vacancy_rate", "opr_sale_mt_avg"),
    ("cpi_index", "opr_sale_mt_avg"),
    ("trend_score", "opr_sale_mt_avg"),
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
        {"vacancy_rate→cpi_index": 0.43, ...} 형태의 상관계수 딕셔너리.
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


def _predict_quarters(
    seq_scaled: np.ndarray,
    model: torch.nn.Module,
    device: torch.device,
    target_idx: int = 0,
    n_quarters: int = 4,
) -> np.ndarray:
    """모델 output_size에 따라 분기 예측.

    output_size>=n_quarters → 단일 forward (DMS)
    output_size<n_quarters  → 자기회귀 n_quarters-step loop (출력 재주입)

    Returns shape (n_quarters,) of scaled predictions.
    """
    import torch

    with torch.no_grad():
        t = torch.tensor(seq_scaled, dtype=torch.float32).unsqueeze(0).to(device)
        first = model(t).cpu().numpy().flatten()
        if len(first) >= n_quarters:
            return first[:n_quarters]
        # 자기회귀 — 추가 step 진행 (첫 step은 first[0] 사용)
        current = t.clone()
        outs: list[float] = [float(first[0])]
        # 첫 step 결과를 입력에 재주입
        new_step = current[0, -1, :].clone()
        new_step[target_idx] = float(first[0])
        current = torch.cat([current[:, 1:, :], new_step.unsqueeze(0).unsqueeze(0)], dim=1)
        for _ in range(n_quarters - 1):
            pred_val = float(model(current).cpu().numpy().flatten()[0])
            outs.append(pred_val)
            new_step = current[0, -1, :].clone()
            new_step[target_idx] = pred_val
            current = torch.cat([current[:, 1:, :], new_step.unsqueeze(0).unsqueeze(0)], dim=1)
        return np.array(outs)


def perturb_and_predict(
    seq_scaled: np.ndarray,
    feature_indices: list[int],
    delta_pct: float,
    model: torch.nn.Module,
    tgt_scaler: sklearn.preprocessing.StandardScaler | sklearn.preprocessing.MinMaxScaler,
    device: torch.device,
    target_idx: int = 0,
) -> list[float]:
    """특정 피처를 delta_pct% 변화시킨 후 TCN으로 예측하여 분기별 매출(원) list를 반환한다.

    Parameters
    ----------
    seq_scaled : np.ndarray
        shape (window_size, n_features). feat_scaler로 스케일링된 입력 시퀀스.
    feature_indices : list[int]
        섭동할 피처 인덱스 목록 (유동인구는 3개 동시 섭동).
    delta_pct : float
        변화율 (%). 예: 10.0 → +10%, -20.0 → -20%.
    model : TCNForecaster
        eval 모드의 TCN 모델 인스턴스 (v2 DMS 또는 v3 자기회귀).
    tgt_scaler : StandardScaler | MinMaxScaler
        타겟 역변환용 스케일러 (inverse_transform만 호출하므로 두 종류 모두 호환).
    device : torch.device
        추론 디바이스 (CPU/CUDA).
    target_idx : int
        자기회귀 모드에서 예측 출력을 재주입할 monthly_sales 컬럼 인덱스.

    Returns
    -------
    list[float]
        길이 4의 분기별 매출 예측치 (Q1, Q2, Q3, Q4 순). 각 값은 원 단위, 음수 클립.
    """
    seq_perturbed = seq_scaled.copy()
    for idx in feature_indices:
        seq_perturbed[:, idx] *= 1.0 + delta_pct / 100.0

    raw = _predict_quarters(seq_perturbed, model, device, target_idx=target_idx, n_quarters=4)

    quarters: list[float] = []
    for v in raw:
        pred_log = float(tgt_scaler.inverse_transform([[float(v)]])[0][0])
        quarters.append(max(0.0, float(np.expm1(pred_log))))
    return quarters


def _scale_quarter_value(
    feat_scaler: sklearn.preprocessing.StandardScaler | sklearn.preprocessing.MinMaxScaler,
    quarter_idx: int,
    quarter_value: int,
) -> float:
    """quarter_value(1~4)를 feat_scaler가 정의한 스케일 공간 값으로 변환한다.

    MinMaxScaler / StandardScaler 양쪽을 지원하며, 변환식은 sklearn 내부와 동일:
    - MinMaxScaler  : scaled = x * scale_ + min_
    - StandardScaler: scaled = (x - mean_) / scale_

    Parameters
    ----------
    feat_scaler : StandardScaler | MinMaxScaler
        학습 시 fit된 피처 스케일러.
    quarter_idx : int
        feat_scaler가 fit된 피처 배열 내 quarter_num의 인덱스.
    quarter_value : int
        1~4 중 하나. 스케일 공간 값으로 변환된다.

    Returns
    -------
    float
        스케일 공간의 quarter 값.
    """
    if hasattr(feat_scaler, "data_min_"):
        # MinMaxScaler
        scale_val = float(feat_scaler.scale_[quarter_idx])
        min_val = float(feat_scaler.min_[quarter_idx])
        return quarter_value * scale_val + min_val
    # StandardScaler
    mean_val = float(feat_scaler.mean_[quarter_idx])
    std_val = float(feat_scaler.scale_[quarter_idx])
    return (quarter_value - mean_val) / std_val if std_val > 1e-10 else 0.0


def perturb_quarter_and_predict(
    seq_scaled: np.ndarray,
    quarter_idx: int,
    quarter_value: int,
    feat_scaler: sklearn.preprocessing.StandardScaler | sklearn.preprocessing.MinMaxScaler,
    model: torch.nn.Module,
    tgt_scaler: sklearn.preprocessing.StandardScaler | sklearn.preprocessing.MinMaxScaler,
    device: torch.device,
    target_idx: int = 0,
) -> list[float]:
    """quarter_num을 특정 분기값으로 설정 후 예측하여 분기별 매출(원) list를 반환한다."""
    seq_perturbed = seq_scaled.copy()
    seq_perturbed[:, quarter_idx] = _scale_quarter_value(feat_scaler, quarter_idx, quarter_value)

    raw = _predict_quarters(seq_perturbed, model, device, target_idx=target_idx, n_quarters=4)

    quarters: list[float] = []
    for v in raw:
        pred_log = float(tgt_scaler.inverse_transform([[float(v)]])[0][0])
        quarters.append(max(0.0, float(np.expm1(pred_log))))
    return quarters


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

    # v3 채택: 자기회귀 + 37피처. predict.py DEFAULT_PREDICT_CONFIG와 동기화.
    weights_path = WEIGHTS_DIR / "finetuned_mapo_tcn_v3.pt"
    scalers_path = WEIGHTS_DIR / "finetune_tcn_scalers_v3.pkl"

    if not weights_path.exists() or not scalers_path.exists():
        raise FileNotFoundError(f"v3 가중치 또는 스케일러 파일 없음: {weights_path}, {scalers_path}")

    # 모델 + 스케일러 로드
    feat_scaler, tgt_scaler = load_scalers(scalers_path)
    input_size = len(feat_scaler.scale_)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model = TCNForecaster(
        input_size=input_size,
        n_channels=128,
        kernel_size=2,
        dilations=[1, 2],
        dropout=0.2,
        output_size=1,
    )
    model.load_weights(weights_path)
    model.to(device)
    model.eval()
    logger.info("TCNForecaster v3 로드 완료 (input_size=%d, autoregressive)", input_size)

    feature_names = list(ALL_FEATURES)
    window_size = 4

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

        # v3 자기회귀 재주입용 monthly_sales 인덱스
        target_idx = actual_features.index("monthly_sales") if "monthly_sales" in actual_features else 0

        # 기준 예측 (delta=0) — 4분기 list 반환
        baseline_q_raw = perturb_and_predict(seq_scaled, [], 0.0, model, tgt_scaler, device, target_idx=target_idx)
        baseline_q = [round(v, 0) for v in baseline_q_raw]

        # 점포당 baseline (프론트 표시 단위 일관성)
        from models.interface import _get_latest_store_count

        store_count = _get_latest_store_count(dong_code, industry_code)
        baseline_per_store = [round(v / store_count, 0) for v in baseline_q_raw]

        elasticity: dict[str, dict] = {}

        # ±% 슬라이더 (4개) — 분기별 % 변화율 list 저장
        for slider_name, target_feats in SLIDER_FEATURES.items():
            feat_indices = get_feature_indices(actual_features, target_feats)
            if not feat_indices:
                continue
            level_results: dict[str, list[float]] = {}
            for delta in PERTURBATION_LEVELS:
                pred_q = perturb_and_predict(
                    seq_scaled, feat_indices, float(delta), model, tgt_scaler, device, target_idx=target_idx
                )
                per_quarter: list[float] = []
                for q_idx, p in enumerate(pred_q):
                    base = baseline_q_raw[q_idx]
                    if base > 0:
                        per_quarter.append(round((p - base) / base * 100.0, 4))
                    else:
                        per_quarter.append(0.0)
                key_str = f"{'+' if delta > 0 else ''}{delta}"
                level_results[key_str] = per_quarter
            elasticity[slider_name] = level_results

        # quarter_num 슬라이더 (categorical) — 분기별 % 변화율 list 저장
        if quarter_idx is not None and "quarter_num" in actual_features:
            q_results: dict[str, list[float]] = {}
            for q_label, q_val in QUARTER_VALUES.items():
                pred_q = perturb_quarter_and_predict(
                    seq_scaled, quarter_idx, q_val, feat_scaler, model, tgt_scaler, device, target_idx=target_idx
                )
                per_quarter = []
                for q_idx, p in enumerate(pred_q):
                    base = baseline_q_raw[q_idx]
                    if base > 0:
                        per_quarter.append(round((p - base) / base * 100.0, 4))
                    else:
                        per_quarter.append(0.0)
                q_results[q_label] = per_quarter
            elasticity["quarter_num"] = q_results

        cache[f"{dong_code}_{industry_code}"] = {
            "baseline": baseline_q,
            "baseline_per_store": baseline_per_store,
            "store_count": store_count,
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
