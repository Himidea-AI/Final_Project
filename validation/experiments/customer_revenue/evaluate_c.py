"""C 모델 학술 평가 — model vs 3 baseline.

산출:
- MAE on ratio (16 차원 평균)
- KL divergence per segment group (age/gender/time/day)
- 16 segment 별 MASE (group_mean baseline 대비)
- CSV: validation/results/customer_revenue_metrics.csv

Note
----
plan 의 ``load_segment_data`` / ``encode_inputs`` 는 ``data_prep.py`` 에 존재하지
않아서, 동일 의미를 ``load_district_sales`` + ``_compute_ratios`` + 인라인 인코딩
헬퍼로 재구성한다.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from models.customer_revenue.data_prep import (
    DB_URL,
    DONG_TO_IDX,
    INDUSTRY_TO_IDX,
    SEGMENT_COLS,
    YEAR_BASE,
    YEAR_SCALE,
    _compute_ratios,
    load_district_sales,
)
from models.customer_revenue.model import WEIGHTS_DIR, MLPPredictor
from validation.experiments.customer_revenue.baseline_c import (
    global_mean_baseline,
    group_mean_baseline,
    industry_only_baseline,
)
from validation.metrics.forecast_metrics import kl_divergence, mae_on_ratio

logger = logging.getLogger(__name__)
RESULTS_DIR = Path("validation/results")


def _load_segment_df(db_url: str = DB_URL) -> pd.DataFrame:
    """district_sales 로드 + 비율 계산 + 마포 16동 / 10업종 / 유효 분기 필터."""
    df = load_district_sales(db_url=db_url)
    df = _compute_ratios(df)
    df["dong_code"] = df["dong_code"].astype(str)
    df["industry_code"] = df["industry_code"].astype(str)
    df = df[df["dong_code"].isin(DONG_TO_IDX) & df["industry_code"].isin(INDUSTRY_TO_IDX)]
    df = df[df["quarter"] % 10 != 0]
    if df.empty:
        raise RuntimeError("district_sales 데이터가 비어있습니다. DB 연결/필터 조건 확인 필요.")
    return df.reset_index(drop=True)


def _encode_inputs(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(dong_idx, industry_idx, quarter_enc[N,3]) 반환. data_prep.prepare_training_data 와 동일 인코딩."""
    dong_idx = df["dong_code"].map(DONG_TO_IDX).values.astype(np.int64)
    industry_idx = df["industry_code"].map(INDUSTRY_TO_IDX).values.astype(np.int64)

    years = (df["quarter"].values // 10).astype(np.float32)
    year_norms = (years - YEAR_BASE) / YEAR_SCALE
    quarter_nums = (df["quarter"] % 10).values
    quarter_enc = np.array(
        [
            [
                math.sin(2 * math.pi * (q - 1) / 4),
                math.cos(2 * math.pi * (q - 1) / 4),
                year_norms[i],
            ]
            for i, q in enumerate(quarter_nums)
        ],
        dtype=np.float32,
    )
    return dong_idx, industry_idx, quarter_enc


def evaluate_c_model(db_url: str = DB_URL, seed: int = 2026) -> pd.DataFrame:
    """C 모델 vs 3 baseline 학술 metric 측정.

    Returns
    -------
    pd.DataFrame
        rows: ["c_model", "group_mean", "global_mean", "industry_only"]
        cols: model / MAE_overall / KL_age / KL_gender / KL_time / KL_day /
              MASE_<segment> ... (group_mean 행은 MASE 자기 참조라 NaN 유지)
    """
    np.random.seed(seed)
    torch.manual_seed(seed)

    df = _load_segment_df(db_url=db_url)

    # 시간순 70/15/15 split (분기 기준)
    quarters = sorted(df["quarter"].unique())
    n = len(quarters)
    if n < 3:
        raise RuntimeError(f"분기 수가 부족합니다 ({n}). 학술 평가 불가.")
    train_q = quarters[: int(n * 0.70)]
    test_q = quarters[int(n * 0.85) :]
    df_train = df[df["quarter"].isin(train_q)].reset_index(drop=True)
    df_test = df[df["quarter"].isin(test_q)].reset_index(drop=True)
    if df_test.empty:
        raise RuntimeError("test split 이 비어있습니다. quarter 분포 확인 필요.")

    logger.info(
        "split: total_quarters=%d train=%d test=%d (train_rows=%d test_rows=%d)",
        n,
        len(train_q),
        len(test_q),
        len(df_train),
        len(df_test),
    )

    y_true = df_test[SEGMENT_COLS].values.astype(np.float64)  # (N, 16)

    # 1. C 모델 추론
    weights_path = WEIGHTS_DIR / "customer_mlp.pt"
    if not weights_path.exists():
        raise FileNotFoundError(
            f"학습 가중치를 찾을 수 없습니다: {weights_path}. models/customer_revenue/train.py 를 먼저 실행하세요."
        )
    model = MLPPredictor()
    model.load_weights(weights_path)
    model.eval()

    dong_idx, ind_idx, q_enc = _encode_inputs(df_test)
    with torch.no_grad():
        y_pred_model = (
            model(
                torch.from_numpy(dong_idx).long(),
                torch.from_numpy(ind_idx).long(),
                torch.from_numpy(q_enc).float(),
            )
            .cpu()
            .numpy()
            .astype(np.float64)
        )  # (N, 16)

    # 2. baseline 예측 (train 기준 통계)
    gm = group_mean_baseline(df_train, SEGMENT_COLS)
    glob = global_mean_baseline(df_train, SEGMENT_COLS)
    ind_only = industry_only_baseline(df_train, SEGMENT_COLS)

    glob_vals = glob.values.astype(np.float64)

    y_pred_gm = np.array(
        [
            gm.loc[(r.dong_code, r.industry_code)].values if (r.dong_code, r.industry_code) in gm.index else glob_vals
            for r in df_test.itertuples(index=False)
        ],
        dtype=np.float64,
    )
    y_pred_global = np.tile(glob_vals, (len(df_test), 1))
    y_pred_ind = np.array(
        [
            ind_only.loc[r.industry_code].values if r.industry_code in ind_only.index else glob_vals
            for r in df_test.itertuples(index=False)
        ],
        dtype=np.float64,
    )

    # 3. metric 측정
    rows = []
    preds = [
        ("c_model", y_pred_model),
        ("group_mean", y_pred_gm),
        ("global_mean", y_pred_global),
        ("industry_only", y_pred_ind),
    ]
    for name, y_pred in preds:
        m: dict[str, float | str] = {
            "model": name,
            "MAE_overall": mae_on_ratio(y_true, y_pred),
            "KL_age": float(np.mean([kl_divergence(y_true[i, 0:6], y_pred[i, 0:6]) for i in range(len(y_true))])),
            "KL_gender": float(np.mean([kl_divergence(y_true[i, 6:8], y_pred[i, 6:8]) for i in range(len(y_true))])),
            "KL_time": float(np.mean([kl_divergence(y_true[i, 8:14], y_pred[i, 8:14]) for i in range(len(y_true))])),
            "KL_day": float(np.mean([kl_divergence(y_true[i, 14:16], y_pred[i, 14:16]) for i in range(len(y_true))])),
        }
        # MASE per segment (group_mean baseline 분모)
        for k, col in enumerate(SEGMENT_COLS):
            mae_model = float(np.mean(np.abs(y_true[:, k] - y_pred[:, k])))
            mae_baseline = float(np.mean(np.abs(y_true[:, k] - y_pred_gm[:, k])))
            if name == "group_mean":
                # 자기 자신 — 항상 1.0 (혹은 0/0 시 NaN)
                m[f"MASE_{col}"] = 1.0 if mae_baseline > 1e-9 else float("nan")
            else:
                m[f"MASE_{col}"] = mae_model / mae_baseline if mae_baseline > 1e-9 else float("nan")
        rows.append(m)

    result_df = pd.DataFrame(rows)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "customer_revenue_metrics.csv"
    result_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    logger.info("결과 저장: %s", out_path)
    return result_df


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    df = evaluate_c_model()
    print("\n=== C 모델 학술 평가 ===")
    # 가독성: 숫자 컬럼 소수 4자리 표시
    with pd.option_context("display.float_format", lambda v: f"{v:.4f}"):
        print(df.to_string(index=False))


if __name__ == "__main__":
    main()
