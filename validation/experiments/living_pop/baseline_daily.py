"""일별 task 의 학술 baseline 측정.

baseline:
- naive_lag1: y[t] = y[t-1] (어제 같은 시간대 같은 동)
- naive_lag7: y[t] = y[t-7] (1주 전 같은 요일) — primary baseline
- naive_lag365: y[t] = y[t-365] (1년 전 같은 날짜)

각 baseline 에 대해 evaluate_all (MAE/RMSE/MAPE/sMAPE/R²/MASE) 산출.
시간순 70/15/15 split (그룹 내).

게이트: naive_lag7 R² < 0.98 → Task 3 (모델 학습) 진입 가치 있음.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from models.living_pop_forecast.data_prep_daily import (
    load_living_pop_daily,
    split_time_order_per_group,
)
from validation.metrics.forecast_metrics import evaluate_all as compute_metrics

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = PROJECT_ROOT / "validation" / "results"
DEFAULT_OUTPUT = RESULTS_DIR / "living_pop_daily_baselines.csv"


def _build_baseline_arrays(
    df_full: pd.DataFrame,
    test_df: pd.DataFrame,
    train_df: pd.DataFrame,
) -> dict:
    """test 구간에 대해 baseline 별 (y_true, y_pred) 와 train_actuals 빌드.

    Baselines
    ---------
    naive_lag1   : y_pred = y[date - 1day, dong, hour]
    naive_lag7   : y_pred = y[date - 7days, dong, hour]
    naive_lag365 : y_pred = y[date - 365days, dong, hour]

    lag 시점이 raw 전체 (train+val+test) 안에 있어야 valid sample 로 인정.
    """
    df_full = df_full.sort_values(["dong_code", "time_zone", "date"]).reset_index(drop=True)

    # group key (dong, hour) 별 date→total_pop dict
    by_group_full: dict[tuple, dict[pd.Timestamp, float]] = {}
    for (dong, hour), g in df_full.groupby(["dong_code", "time_zone"], sort=False):
        by_group_full[(dong, hour)] = dict(
            zip(pd.to_datetime(g["date"]).tolist(), g["total_pop"].astype(float).tolist())
        )

    # train_actuals: 각 그룹의 train 시계열 시간순 1d concat (Hyndman MASE in-sample 분모)
    train_pieces: list[np.ndarray] = []
    for _, g in train_df.sort_values(["dong_code", "time_zone", "date"]).groupby(
        ["dong_code", "time_zone"], sort=False
    ):
        if len(g) >= 2:
            train_pieces.append(g["total_pop"].to_numpy(dtype=np.float32))

    y_true: list[float] = []
    naive_lag1: list[float] = []
    naive_lag7: list[float] = []
    naive_lag365: list[float] = []

    test_sorted = test_df.sort_values(["dong_code", "time_zone", "date"]).reset_index(drop=True)
    test_dates = pd.to_datetime(test_sorted["date"])
    one_day = pd.Timedelta(days=1)
    seven_day = pd.Timedelta(days=7)
    year_day = pd.Timedelta(days=365)

    for i, row in test_sorted.iterrows():
        key = (row["dong_code"], int(row["time_zone"]))
        q_to_pop = by_group_full.get(key)
        if q_to_pop is None:
            continue
        d = test_dates.iloc[i]
        d1 = d - one_day
        d7 = d - seven_day
        d365 = d - year_day
        if d1 not in q_to_pop or d7 not in q_to_pop:
            # lag1 / lag7 결측이면 sample 제외 (모든 baseline 비교 가능하도록)
            continue
        lag1 = q_to_pop[d1]
        lag7 = q_to_pop[d7]
        lag365 = q_to_pop.get(d365, lag7)  # 첫 1년 구간은 lag7 로 fallback

        y_true.append(float(row["total_pop"]))
        naive_lag1.append(float(lag1))
        naive_lag7.append(float(lag7))
        naive_lag365.append(float(lag365))

    return {
        "y_true": np.asarray(y_true, dtype=np.float32),
        "naive_lag1": np.asarray(naive_lag1, dtype=np.float32),
        "naive_lag7": np.asarray(naive_lag7, dtype=np.float32),
        "naive_lag365": np.asarray(naive_lag365, dtype=np.float32),
        "train_actuals": (np.concatenate(train_pieces, axis=0) if train_pieces else np.asarray([], dtype=np.float32)),
    }


def _evaluate_baseline(
    name: str,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_naive: np.ndarray,
    y_train: np.ndarray,
) -> dict:
    metrics = compute_metrics(
        y_true,
        y_pred,
        y_naive=y_naive,
        y_train=y_train if y_train.size > 0 else None,
    )
    return {
        "baseline": name,
        "n_test": int(len(y_true)),
        "MAE": float(metrics["MAE"]),
        "RMSE": float(metrics["RMSE"]),
        "NRMSE_pct": float(metrics["NRMSE_pct"]),
        "MAPE_pct": float(metrics["MAPE_pct"]),
        "sMAPE_pct": float(metrics["sMAPE_pct"]),
        "R2": float(metrics["R2"]),
        "MASE_lag7": float(metrics.get("MASE", float("nan"))),
        "MASE_in_sample": float(metrics.get("MASE_in_sample", float("nan"))),
    }


def run_baselines(
    df: pd.DataFrame,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
) -> tuple[pd.DataFrame, dict]:
    """3 baseline 측정 → DataFrame + meta dict 반환.

    MASE 분모 (y_naive) 는 *naive_lag7* — primary baseline 기준.
    """
    train_df, val_df, test_df = split_time_order_per_group(df, train_ratio, val_ratio)
    if test_df.empty:
        raise ValueError("test split 이 비어 있음 — 그룹별 시계열 길이 부족 의심")

    arrays = _build_baseline_arrays(df, test_df, train_df)
    y_true = arrays["y_true"]
    y_naive = arrays["naive_lag7"]  # primary baseline
    y_train = arrays["train_actuals"]

    rows = []
    for name, key in [
        ("naive_lag1", "naive_lag1"),
        ("naive_lag7", "naive_lag7"),
        ("naive_lag365", "naive_lag365"),
    ]:
        rows.append(_evaluate_baseline(name, y_true, arrays[key], y_naive, y_train))

    out_df = pd.DataFrame(rows)
    meta = {
        "n_dates_total": int(df["date"].nunique()),
        "n_train_rows": int(len(train_df)),
        "n_val_rows": int(len(val_df)),
        "n_test_rows": int(len(test_df)),
        "n_test_pred": int(len(y_true)),
        "n_groups_total": int(df.groupby(["dong_code", "time_zone"]).ngroups),
        "train_date_min": str(pd.to_datetime(train_df["date"]).min().date()) if not train_df.empty else "",
        "train_date_max": str(pd.to_datetime(train_df["date"]).max().date()) if not train_df.empty else "",
        "test_date_min": str(pd.to_datetime(test_df["date"]).min().date()) if not test_df.empty else "",
        "test_date_max": str(pd.to_datetime(test_df["date"]).max().date()) if not test_df.empty else "",
    }
    return out_df, meta


def _format_text(df: pd.DataFrame, meta: dict) -> str:
    lines: list[str] = []
    lines.append("==== 일별 Task — Baseline 비교 (test split) ====\n")
    lines.append(f"  - 총 일수: {meta['n_dates_total']}, 그룹: {meta['n_groups_total']} (16동 x 24시간 = 384 기대)")
    lines.append(
        f"  - split: train={meta['n_train_rows']:,} ({meta['train_date_min']}~{meta['train_date_max']}), "
        f"val={meta['n_val_rows']:,}, test={meta['n_test_rows']:,} ({meta['test_date_min']}~{meta['test_date_max']})"
    )
    lines.append(f"  - test 예측 row: {meta['n_test_pred']:,}")
    lines.append("")
    lines.append("| baseline       | MAE      | RMSE     | NRMSE % | MAPE % | sMAPE % | R²       | MASE_lag7 |")
    lines.append("|----------------|----------|----------|---------|--------|---------|----------|-----------|")
    for _, r in df.iterrows():
        lines.append(
            f"| {r['baseline']:<14} | {r['MAE']:>8.2f} | {r['RMSE']:>8.2f} | "
            f"{r['NRMSE_pct']:>7.3f} | {r['MAPE_pct']:>6.3f} | {r['sMAPE_pct']:>7.3f} | "
            f"{r['R2']:>8.4f} | {r['MASE_lag7']:>9.4f} |"
        )
    lines.append("")
    lines.append("==== 게이트 판단 ====")
    lag7_row = df[df["baseline"] == "naive_lag7"].iloc[0]
    lag7_r2 = float(lag7_row["R2"])
    lines.append(f"- naive_lag7 R²: {lag7_r2:.4f}  (< 0.98 ? {'YES' if lag7_r2 < 0.98 else 'NO'})")
    if lag7_r2 < 0.95:
        verdict = "변동성 매우 풍부 — Task 3 (모델 학습) 강력 권장"
        next_step = "다음 단계 추천: Task 3 (모델 학습) 진입"
    elif lag7_r2 < 0.98:
        verdict = "학습 여지 있음 — Task 3 (모델 학습) 진행 권장"
        next_step = "다음 단계 추천: Task 3 (모델 학습) 진입"
    elif lag7_r2 < 0.99:
        verdict = "학습 여지 작음 — 외부 신호 (공휴일 등) 추가 후 시도 권장"
        next_step = "다음 단계 추천: 외부 신호 보강 후 Task 3"
    else:
        verdict = "stationary — task 변경도 효과 없음, 폐기"
        next_step = "다음 단계 추천: 폐기 (naive_lag7 baseline 채택)"
    lines.append(f"- 학습 모델이 능가할 여지: {verdict}")
    lines.append(f"- {next_step}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, OSError):
        pass
    parser = argparse.ArgumentParser(description="일별 (date × dong × time_zone) baseline 측정")
    parser.add_argument("--rebuild-cache", action="store_true", help="cache 강제 재생성")
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT))
    parser.add_argument("--train-ratio", type=float, default=0.70)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    args = parser.parse_args(argv)

    df = load_living_pop_daily(rebuild=args.rebuild_cache)

    out_df, meta = run_baselines(df, train_ratio=args.train_ratio, val_ratio=args.val_ratio)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False, float_format="%.6f")
    logger.info("결과 csv 저장: %s", out_path)

    print()
    print(_format_text(out_df, meta))
    print()
    return 0


__all__ = ["DEFAULT_OUTPUT", "main", "run_baselines"]


if __name__ == "__main__":
    sys.exit(main())
