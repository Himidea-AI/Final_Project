"""
TCN 시계열 추론 — 특정 동x업종의 향후 n분기 매출 예측

추론 모드 (config["output_size"] 로 결정):
- output_size == 1 (자기회귀, v3 기본값):
    1분기씩 예측 → 직전 예측값을 입력에 재주입 → n_quarters 반복.
    분기별 변동성 보존(평탄화 회피). 단, step마다 오차가 누적될 수 있음.
- output_size >= n_quarters (DMS, v2 legacy):
    한 번의 forward로 n_quarters 동시 출력. 오차 누적 없음.
    단, 회귀 평균(mean reversion)으로 분기 차이가 평탄화되는 경향.

신뢰구간:
- val residual std (`residual_std_path` pkl) 기반.
- 자기회귀(output_size=1) 모델은 학습 시 측정 가능한 step 수가 1개라 Q1 std 만 저장됨.
  → Q2~Q4는 predict() 내부 fallback (분기 진행에 따라 ±3%/±6%/±9% 등 점진 확장) 사용.
- 향후 개선 여지: val 셋에서 자기회귀 4-step rollout 측정으로 4-element residual_std 저장.

담당: B2 — 수지니
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
    EXCLUDE_COMBOS,
    ExcludedComboError,
    load_timeseries,
)

from .model import WEIGHTS_DIR, TCNForecaster
from .train import load_scalers

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 프로세스 단위 모델 캐시 — 같은 가중치 경로는 한 번만 로드
# ---------------------------------------------------------------------------
_MODEL_CACHE: dict = {}

# ---------------------------------------------------------------------------
# 기본 설정
# ---------------------------------------------------------------------------

DEFAULT_PREDICT_CONFIG: dict = {
    "db_url": DB_URL,
    # v3 채택: 자기회귀 + 37피처. 슬라이더 5개 호환 + 분기 변동성 보존(Q1→Q4 drift +6.7%p).
    "weights_path": str(WEIGHTS_DIR / "finetuned_mapo_tcn_v3.pt"),
    "scalers_path": str(WEIGHTS_DIR / "finetune_tcn_scalers_v3.pkl"),
    "residual_std_path": str(WEIGHTS_DIR / "finetune_tcn_residual_std_v3.pkl"),
    "window_size": 4,
    "n_channels": 128,
    "kernel_size": 2,
    "dilations": [1, 2],
    "dropout": 0.2,
    "output_size": 1,
    "target_col": "monthly_sales",
    "feature_cols": None,
    "confidence_z": 1.96,  # 95% 신뢰구간
}


# ---------------------------------------------------------------------------
# 추론 함수
# ---------------------------------------------------------------------------


def predict(
    dong_code: str,
    industry_code: str,
    n_quarters: int = 4,
    config: dict | None = None,
) -> list[dict]:
    """특정 동x업종의 향후 n분기 매출을 예측한다.

    추론 모드는 `config["output_size"]`로 결정된다:
    - output_size == 1 (v3 기본): 자기회귀 — 1분기씩 예측 후 직전 출력을 입력에 재주입,
      n_quarters 만큼 step 반복. 분기 변동성 보존, 단 오차가 누적될 수 있음.
    - output_size >= n_quarters (v2 legacy): DMS — 단일 forward로 n_quarters 동시 출력.
      오차 누적 없음, 단 mean reversion으로 분기 차이가 평탄화되는 경향.

    신뢰구간:
    - val residual std 기반 (residual_std_path pkl 로드).
    - 자기회귀 모델은 1-element residual_std만 저장됨 → Q2~Q4는 fallback CI 사용
      (margin = pred_sales × min(0.03 × q, 0.25) × confidence_z).

    Parameters
    ----------
    dong_code : str
        행정동 코드 (예: '11440555').
    industry_code : str
        업종 코드 (예: 'CS100001').
    n_quarters : int
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

    # EXCLUDE_COMBOS 차단 — 학습 제외 조합은 추론도 제공하지 않음
    if (dong_code, industry_code) in EXCLUDE_COMBOS:
        raise ExcludedComboError(
            f"해당 조합은 데이터 부족으로 예측을 제공하지 않습니다: "
            f"dong_code={dong_code}, industry_code={industry_code}"
        )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    weights_path = Path(cfg["weights_path"])
    scalers_path = Path(cfg["scalers_path"])
    window_size = cfg["window_size"]
    feature_cols = cfg.get("feature_cols")

    # 가중치 파일 존재 확인
    if not weights_path.exists():
        raise FileNotFoundError(
            f"TCN 모델 가중치를 찾을 수 없습니다: {weights_path}\n먼저 학습(pretrain/finetune)을 실행하세요."
        )

    # 스케일러 파일 존재 확인
    if not scalers_path.exists():
        raise FileNotFoundError(f"스케일러 파일을 찾을 수 없습니다: {scalers_path}")

    # 모델+스케일러 싱글턴 캐시 — 동일 가중치 경로는 프로세스 내 한 번만 로드
    _cache_key = (str(weights_path), str(scalers_path))
    if _cache_key in _MODEL_CACHE:
        feat_scaler, tgt_scaler, model = _MODEL_CACHE[_cache_key]
        logger.debug("모델 캐시 히트 — TCNForecaster (%s)", weights_path.name)
    else:
        # 스케일러 로드 — 역변환(inverse_transform)에 사용
        feat_scaler, tgt_scaler = load_scalers(scalers_path)
        input_size = len(feat_scaler.scale_)

        # TCN 모델 로드
        model = TCNForecaster(
            input_size=input_size,
            n_channels=cfg["n_channels"],
            kernel_size=cfg["kernel_size"],
            dilations=cfg["dilations"],
            dropout=cfg["dropout"],
            output_size=cfg.get("output_size", 4),
        )
        model.load_weights(weights_path)
        model.to(device)
        model.eval()
        _MODEL_CACHE[_cache_key] = (feat_scaler, tgt_scaler, model)
        logger.info("TCNForecaster 로드 완료 → 캐시 저장 (%s)", weights_path.name)

    # 피처 컬럼 결정 (캐시 히트 시에도 필요)
    if feature_cols is None:
        feature_cols = ALL_FEATURES
    input_size = len(feat_scaler.scale_)

    # 과거 데이터 로드 + 시계열 빌드 (캐시 우선)
    dong_prefix = dong_code[:5] if len(dong_code) >= 5 else dong_code
    ts = load_timeseries(db_url=cfg["db_url"], dong_prefix=dong_prefix)
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
        pad_size = window_size - len(recent)
        recent = np.vstack([np.tile(recent[0], (pad_size, 1)), recent])
        logger.warning(
            "데이터 부족 패딩 적용: dong=%s, %d분기 → %d분기 (첫 분기 복사)",
            dong_code,
            len(recent) - pad_size,
            window_size,
        )

    # 피처 스케일링
    seq = feat_scaler.transform(recent[-window_size:])

    # ---------------------------------------------------------------------------
    # 예측 — output_size에 따라 분기
    #   output_size=4 → DMS (단일 forward, 4분기 동시 출력)
    #   output_size=1 → 자기회귀 (n_quarters step loop, 출력을 다음 step 입력으로 재주입)
    # ---------------------------------------------------------------------------
    predictions: list[float] = []
    output_size = cfg.get("output_size", 4)
    target_col = cfg.get("target_col", "monthly_sales")
    target_idx = actual_features.index(target_col) if target_col in actual_features else 0

    with torch.no_grad():
        if output_size >= n_quarters:
            input_tensor = torch.from_numpy(seq).unsqueeze(0).to(device)  # (1, window_size, features)
            pred_all = model(input_tensor)  # (1, output_size)
            pred_scaled_arr = pred_all.cpu().numpy().flatten()[:n_quarters]
        else:
            current = torch.from_numpy(seq).unsqueeze(0).to(device).clone()
            pred_scaled_list: list[float] = []
            for _ in range(n_quarters):
                pred_val = float(model(current).cpu().numpy().flatten()[0])
                pred_scaled_list.append(pred_val)
                new_step = current[0, -1, :].clone()
                new_step[target_idx] = pred_val  # 자기회귀 재주입
                current = torch.cat([current[:, 1:, :], new_step.unsqueeze(0).unsqueeze(0)], dim=1)
            pred_scaled_arr = np.array(pred_scaled_list)

    for ps in pred_scaled_arr:
        pred_log = tgt_scaler.inverse_transform([[float(ps)]])[0][0]
        predictions.append(float(np.expm1(pred_log)))

    # ---------------------------------------------------------------------------
    # 신뢰구간 계산 — residual_std 기반
    # ---------------------------------------------------------------------------
    import pickle

    confidence_z = cfg["confidence_z"]
    residual_std_path = Path(cfg.get("residual_std_path", ""))
    residual_std_list: list[float] | None = None

    if residual_std_path.exists():
        try:
            with open(residual_std_path, "rb") as f:
                residual_std_list = pickle.load(f)  # noqa: S301
            logger.info("residual_std 로드 완료: %s", residual_std_path)
        except Exception as exc:
            logger.warning("residual_std 로드 실패, 하드코딩 CI 사용: %s", exc)
    else:
        logger.warning("residual_std 파일 없음, 하드코딩 CI 사용: %s", residual_std_path)

    results: list[dict] = []

    for i, pred_sales in enumerate(predictions):
        if residual_std_list is not None and i < len(residual_std_list):
            # val residual 기반 CI
            margin = confidence_z * residual_std_list[i]
        else:
            # fallback: 하드코딩 (residual_std 없을 때)
            uncertainty_factor = min(0.03 * (i + 1), 0.25)
            margin = abs(pred_sales) * uncertainty_factor * confidence_z

        results.append(
            {
                "quarter_offset": i + 1,
                "predicted_sales": round(pred_sales, 0),
                "confidence_lower": round(max(0.0, pred_sales - margin), 0),
                "confidence_upper": round(pred_sales + margin, 0),
            }
        )

    return results
