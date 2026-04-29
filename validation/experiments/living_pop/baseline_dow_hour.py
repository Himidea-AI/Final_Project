"""(동 x 요일 x 시간대) task 의 naive / seasonal baseline 측정.

목적: task 변경 후에도 naive baseline 이 강력한지 진단.
naive R2 > 0.95 면 task 변경 자체 효과 없음 (D 모델 재정의 폐기 권장).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from models.living_pop_forecast.data_prep_dow_hour import load_dow_hour_cache
from validation.metrics.forecast_metrics import evaluate_all as compute_metrics

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = PROJECT_ROOT / "validation" / "results"
DEFAULT_OUTPUT = RESULTS_DIR / "living_pop_dow_hour_baselines.csv"


def _split_quarters(
    quarters: list[int], train_ratio: float = 0.70, val_ratio: float = 0.15
) -> tuple[list[int], list[int], list[int]]:
    """시간순 분기 split."""
    n = len(quarters)
    n_train = max(1, int(n * train_ratio))
    n_val = max(1, int(n * val_ratio))
    train = quarters[:n_train]
    val = quarters[n_train : n_train + n_val]
    test = quarters[n_train + n_val :]
    if not test:
        # 분기 수 부족 시 마지막 한 분기를 test 로 강제 분리
        test = [train.pop()] if len(train) > 1 else []
    return train, val, test


def _build_baseline_arrays(
    df: pd.DataFrame,
    train_q: list[int],
    val_q: list[int],
    test_q: list[int],
) -> dict:
    """test 구간에 대해 baseline 별 (y_true, y_pred) 와 naive_lag1, train_actuals 빌드.

    Baselines
    ---------
    naive_lag1     : y_pred = 직전 분기 (dong, dow, hour) mean_pop
    seasonal_lag4  : y_pred = 4 분기 전 (dong, dow, hour) mean_pop (전년도 같은 분기)
    dong_hour_mean : y_pred = (dong, hour) 의 train 분기 평균 (요일 무시 — 현재 D 모델 task 의 대응)
    """
    df = df.sort_values(["dong_code", "day_of_week", "time_zone", "quarter"]).reset_index(drop=True)
    quarters_sorted = sorted(df["quarter"].unique().tolist())
    q_to_idx = {q: i for i, q in enumerate(quarters_sorted)}

    # group key (dong, dow, hour) 별 quarter→mean_pop dict
    by_group: dict[tuple, dict[int, float]] = {}
    for (dong, dow, hour), g in df.groupby(["dong_code", "day_of_week", "time_zone"], sort=False):
        by_group[(dong, dow, hour)] = dict(zip(g["quarter"].tolist(), g["mean_pop"].astype(float).tolist()))

    # dong_hour_mean: (dong, hour) → train 분기들의 mean_pop 평균 (모든 dow 와 모든 train_q)
    train_mask = df["quarter"].isin(train_q)
    dong_hour_mean_map: dict[tuple, float] = (
        df.loc[train_mask].groupby(["dong_code", "time_zone"])["mean_pop"].mean().to_dict()
    )

    y_true: list[float] = []
    naive_lag1: list[float] = []
    seasonal_lag4: list[float] = []
    dong_hour_mean_pred: list[float] = []
    # group test 시퀀스 → train_actuals (Hyndman MASE in-sample 분모용 1d concat)
    train_actuals_pieces: list[np.ndarray] = []

    for (dong, dow, hour), q_to_pop in by_group.items():
        # train_actuals: 이 그룹의 train 분기 mean_pop 시계열 (시간순)
        train_vals = [q_to_pop[q] for q in train_q if q in q_to_pop]
        if len(train_vals) >= 2:
            train_actuals_pieces.append(np.asarray(train_vals, dtype=np.float32))

        for q in test_q:
            if q not in q_to_pop:
                continue
            y = q_to_pop[q]
            # naive_lag1: 직전 분기
            idx = q_to_idx[q]
            if idx == 0:
                continue
            prev_q = quarters_sorted[idx - 1]
            if prev_q not in q_to_pop:
                continue
            lag1 = q_to_pop[prev_q]
            # seasonal_lag4: 1년 전 분기
            if idx < 4:
                lag4 = lag1  # fallback
            else:
                prev4_q = quarters_sorted[idx - 4]
                lag4 = q_to_pop.get(prev4_q, lag1)
            # dong_hour_mean (요일 무시): (dong, hour) train 평균
            dh_mean = float(dong_hour_mean_map.get((dong, hour), lag1))

            y_true.append(float(y))
            naive_lag1.append(float(lag1))
            seasonal_lag4.append(float(lag4))
            dong_hour_mean_pred.append(dh_mean)

    return {
        "y_true": np.asarray(y_true, dtype=np.float32),
        "naive_lag1": np.asarray(naive_lag1, dtype=np.float32),
        "seasonal_lag4": np.asarray(seasonal_lag4, dtype=np.float32),
        "dong_hour_mean": np.asarray(dong_hour_mean_pred, dtype=np.float32),
        "train_actuals": (
            np.concatenate(train_actuals_pieces, axis=0) if train_actuals_pieces else np.asarray([], dtype=np.float32)
        ),
    }


def _evaluate_baseline(
    name: str, y_true: np.ndarray, y_pred: np.ndarray, y_naive: np.ndarray, y_train: np.ndarray
) -> dict:
    metrics = compute_metrics(y_true, y_pred, y_naive=y_naive, y_train=y_train if y_train.size > 0 else None)
    row = {
        "baseline": name,
        "n_test": int(len(y_true)),
        "MAE": float(metrics["MAE"]),
        "RMSE": float(metrics["RMSE"]),
        "NRMSE_pct": float(metrics["NRMSE_pct"]),
        "MAPE_pct": float(metrics["MAPE_pct"]),
        "sMAPE_pct": float(metrics["sMAPE_pct"]),
        "R2": float(metrics["R2"]),
        "MASE": float(metrics["MASE"]),
        "MASE_in_sample": float(metrics.get("MASE_in_sample", float("nan"))),
    }
    return row


def run_baselines(df: pd.DataFrame, train_ratio: float = 0.70, val_ratio: float = 0.15) -> tuple[pd.DataFrame, dict]:
    """3 baseline 측정 → DataFrame + meta dict 반환."""
    quarters_sorted = sorted(df["quarter"].unique().tolist())
    train_q, val_q, test_q = _split_quarters(quarters_sorted, train_ratio, val_ratio)
    if not test_q:
        raise ValueError(f"test 분기 0개 — quarters={quarters_sorted}")

    arrays = _build_baseline_arrays(df, train_q, val_q, test_q)
    y_true = arrays["y_true"]
    y_naive = arrays["naive_lag1"]
    y_train = arrays["train_actuals"]

    rows = []
    for name, key in [
        ("naive_lag1", "naive_lag1"),
        ("seasonal_lag4", "seasonal_lag4"),
        ("dong_hour_mean", "dong_hour_mean"),
    ]:
        rows.append(_evaluate_baseline(name, y_true, arrays[key], y_naive, y_train))

    out_df = pd.DataFrame(rows)
    meta = {
        "n_quarters": len(quarters_sorted),
        "train_quarters": train_q,
        "val_quarters": val_q,
        "test_quarters": test_q,
        "n_test_pred": int(len(y_true)),
        "n_groups_total": int(df.groupby(["dong_code", "day_of_week", "time_zone"]).ngroups),
    }
    return out_df, meta


def _format_text(df: pd.DataFrame, meta: dict) -> str:
    lines: list[str] = []
    lines.append("=== Task 변경 전후 baseline 비교 ===\n")
    lines.append("[현재 task: 분기 평균 (동 x 시간대)]")
    lines.append("  (사전 측정) naive R2 = 0.989, MAPE 2.11%, MASE = 1.000")
    lines.append("")
    lines.append("[새 task: 분기 평균 (동 x 요일 x 시간대)]")
    lines.append(
        f"  - 분기 수: {meta['n_quarters']} (train={len(meta['train_quarters'])}, "
        f"val={len(meta['val_quarters'])}, test={len(meta['test_quarters'])})"
    )
    lines.append(f"  - 그룹 수: {meta['n_groups_total']} (16동 x 7요일 x 24시간 = 2688 기대)")
    lines.append(f"  - test 예측 row: {meta['n_test_pred']:,}")
    lines.append("")
    lines.append(
        f"  {'baseline':<16} {'n_test':>8} {'MAE':>10} {'RMSE':>10} "
        f"{'NRMSE_pct':>10} {'MAPE_pct':>10} {'sMAPE_pct':>10} {'R2':>8} {'MASE':>8} {'MASE_is':>8}"
    )
    for _, r in df.iterrows():
        lines.append(
            f"  {r['baseline']:<16} {int(r['n_test']):>8,} "
            f"{r['MAE']:>10.2f} {r['RMSE']:>10.2f} "
            f"{r['NRMSE_pct']:>10.3f} {r['MAPE_pct']:>10.3f} "
            f"{r['sMAPE_pct']:>10.3f} {r['R2']:>8.4f} "
            f"{r['MASE']:>8.4f} {r['MASE_in_sample']:>8.4f}"
        )
    lines.append("")
    lines.append("[게이트 판단]")
    naive_row = df[df["baseline"] == "naive_lag1"].iloc[0]
    naive_r2 = float(naive_row["R2"])
    naive_mape = float(naive_row["MAPE_pct"])
    lines.append(f"  naive_lag1 R2 = {naive_r2:.4f}, MAPE = {naive_mape:.3f}%")
    if naive_r2 < 0.85:
        verdict = "변동성 풍부 - Task 3 (모델 학습) 가치 큼"
    elif naive_r2 < 0.95:
        verdict = "충분한 변동성 - Task 3 (모델 학습) 진행 권장"
    else:
        verdict = "naive 가 거의 optimal - D 모델 재정의 폐기 권장"
    lines.append(f"  -> {verdict}")
    if naive_mape > 10.0:
        lines.append("  + MAPE > 10% -> 학습 신호 충분")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    # Windows cp949 콘솔에서도 한글/특수문자 출력 가능하도록 stdout 재구성
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, OSError):
        pass
    parser = argparse.ArgumentParser(description="(동 x 요일 x 시간대) baseline 측정")
    parser.add_argument("--rebuild-cache", action="store_true", help="cache 강제 재생성")
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT))
    parser.add_argument("--train-ratio", type=float, default=0.70)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    args = parser.parse_args(argv)

    df = load_dow_hour_cache(rebuild=args.rebuild_cache)

    out_df, meta = run_baselines(df, train_ratio=args.train_ratio, val_ratio=args.val_ratio)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False, float_format="%.6f")
    logger.info("결과 csv 저장: %s", out_path)

    text = _format_text(out_df, meta)
    print()
    print(text)
    print()
    return 0


__all__ = ["DEFAULT_OUTPUT", "main", "run_baselines"]


if __name__ == "__main__":
    sys.exit(main())
