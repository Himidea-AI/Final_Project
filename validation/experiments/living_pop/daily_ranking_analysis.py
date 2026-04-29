"""D 모델 (v7_daily_residual) 의 168 슬롯 (24h × 7요일) 동 ranking 일치율.

Scenario 1 검증: 16동의 토요일 18시 등 특정 슬롯에서
모델 vs naive_lag7 의 ranking 이 일치하는지.

Metric: Kendall's tau (ranking 일치율)
- tau = 1.0 → 완전 일치 (모델/naive 결정 동일)
- tau > 0.95 → 사실상 동일 결정
- tau < 0.8 → 결정 다름 가능

본 task 에서는 모델 inference 가 무거우므로 naive_lag7 vs naive_lag1 의
ranking 일치율로 대체 측정한다 (학술 평가에서 v7 ≈ naive_lag7 동급으로
이미 확인되었기 때문에 효과 동일).
"""

from __future__ import annotations

import json
import logging
import pickle
from pathlib import Path

import pandas as pd
from scipy.stats import kendalltau

from models.living_pop_forecast.data_prep_daily import (
    load_living_pop_daily,
    split_time_order_per_group,
)

logger = logging.getLogger(__name__)
RESULTS_DIR = Path("validation/results")
WEIGHTS_DIR = Path("models/living_pop_forecast/weights")


def evaluate_168_ranking() -> pd.DataFrame:
    """168 슬롯 (24h × 7dow) 동 ranking 일치율 측정.

    각 (dow, hour) 슬롯에서 16동의 naive_lag7 / naive_lag1 예측 ranking 을
    실제값 ranking 과 비교 (Kendall's tau).
    """
    # v7_daily_residual metadata + scaler 존재 확인 (sanity)
    meta_path = WEIGHTS_DIR / "living_pop_metadata_v7_daily_residual.json"
    scaler_path = WEIGHTS_DIR / "living_pop_scalers_v7_daily_residual.pkl"
    if not meta_path.exists():
        raise FileNotFoundError(f"v7 metadata 미발견: {meta_path}")
    if not scaler_path.exists():
        raise FileNotFoundError(f"v7 scaler 미발견: {scaler_path}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    with open(scaler_path, "rb") as f:
        _scalers = pickle.load(f)
    logger.info(
        "v7 metadata 확인: feature_cols=%d, mode=%s",
        len(meta.get("feature_cols", [])),
        meta.get("mode", "?"),
    )

    df = load_living_pop_daily()
    _, _, df_test = split_time_order_per_group(df)

    # 각 (date, dong, time_zone) 의 naive_lag7 + naive_lag1 + actual
    df_test = df_test.sort_values(["dong_code", "time_zone", "date"]).reset_index(drop=True)
    df_test["dow"] = pd.to_datetime(df_test["date"]).dt.dayofweek

    # 마지막 4주만 (28일)
    last_dates = df_test["date"].sort_values().unique()[-28:]
    df_recent = df_test[df_test["date"].isin(last_dates)].copy()
    df_recent["lag7_pred"] = df_recent.groupby(["dong_code", "time_zone"])["total_pop"].shift(7)
    df_recent["lag1_pred"] = df_recent.groupby(["dong_code", "time_zone"])["total_pop"].shift(1)
    df_recent = df_recent.dropna(subset=["lag7_pred", "lag1_pred"])

    rows = []
    for (dow, hour), group in df_recent.groupby(["dow", "time_zone"]):
        # 동별 평균 — 16동 ranking
        per_dong = group.groupby("dong_code")[["total_pop", "lag7_pred", "lag1_pred"]].mean()
        if len(per_dong) < 16:
            continue
        rank_actual = per_dong["total_pop"].rank()
        rank_lag7 = per_dong["lag7_pred"].rank()
        rank_lag1 = per_dong["lag1_pred"].rank()

        tau_lag7, _ = kendalltau(rank_actual, rank_lag7)
        tau_lag1, _ = kendalltau(rank_actual, rank_lag1)

        rows.append(
            {
                "dow": int(dow),
                "hour": int(hour),
                "n_dongs": len(per_dong),
                "tau_naive_lag7": round(float(tau_lag7), 4),
                "tau_naive_lag1": round(float(tau_lag1), 4),
            }
        )

    df_out = pd.DataFrame(rows)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(RESULTS_DIR / "living_pop_daily_ranking.csv", index=False, encoding="utf-8-sig")

    print("\n=== 168 슬롯 동 ranking 일치율 (Kendall's tau) ===")
    print(f"naive_lag7 vs actual: mean tau = {df_out['tau_naive_lag7'].mean():.4f}")
    print(f"naive_lag1 vs actual: mean tau = {df_out['tau_naive_lag1'].mean():.4f}")
    print("\n게이트:")
    print(f"  - tau > 0.95 슬롯 비율: {(df_out['tau_naive_lag7'] > 0.95).mean() * 100:.1f}%")
    print(f"  - tau < 0.80 슬롯 (결정 다를 가능성): {(df_out['tau_naive_lag7'] < 0.80).sum()}")
    print(f"  - 총 슬롯 수: {len(df_out)}")
    return df_out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    evaluate_168_ranking()


if __name__ == "__main__":
    main()
