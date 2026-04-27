# validation/reverse_engineer_sales_v4.py
"""Phase 1: Multi-Output ExtraTrees × 6 seed → 48 컬럼 동시 복원 + 95% CI.

post-processing: enforce_sum_consistency 로 5종 sum constraint × {sales, count} 보장.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.multioutput import MultiOutputRegressor
from sqlalchemy import create_engine, text

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

from validation.exceptions import EnsembleInstabilityError, ExtrapolationCellOverflowError  # noqa: E402
from validation.sum_consistency import (  # noqa: E402
    SUM_CONSTRAINTS_COUNT,
    SUM_CONSTRAINTS_SALES,
    enforce_sum_consistency,
)

engine = create_engine(os.environ["POSTGRES_URL"])
ANCHOR_CSV = REPO_ROOT / "validation" / "results" / "phase1b_anchor_series.csv"
OUT_WIDE_CSV = REPO_ROOT / "validation" / "results" / "imputed_mapo_v4.csv"
OUT_DETAIL_CSV = REPO_ROOT / "validation" / "results" / "imputed_mapo_v4_detail.csv"
CHECKPOINT_DIR = REPO_ROOT / "validation" / "results" / "checkpoints_v4"

SEEDS = [42, 2026, 7, 13, 99, 1234]

SALES_COLS = [
    "monthly_sales",
    "weekday_sales",
    "weekend_sales",
    "mon_sales",
    "tue_sales",
    "wed_sales",
    "thu_sales",
    "fri_sales",
    "sat_sales",
    "sun_sales",
    "time_00_06_sales",
    "time_06_11_sales",
    "time_11_14_sales",
    "time_14_17_sales",
    "time_17_21_sales",
    "time_21_24_sales",
    "male_sales",
    "female_sales",
    "age_10_sales",
    "age_20_sales",
    "age_30_sales",
    "age_40_sales",
    "age_50_sales",
    "age_60_above_sales",
]
COUNT_COLS = [c.replace("_sales", "_count") for c in SALES_COLS]
TARGET_COLS = SALES_COLS + COUNT_COLS

BEST_PARAMS = {
    # Optuna v3 sprint best_params 원본: n_estimators=300, max_depth=35
    # 디스크 용량 제한 (C: 24GB 가용) 으로 인해 축소:
    #   - 300 trees × 48 output × depth 35 → seed 당 ~7GB (6 seed = 42GB NG)
    #   - 100 trees × 48 output × depth 15 → seed 당 ~1GB 이하 (6 seed = ~6GB OK)
    # 예측 품질 트레이드오프: 합격선 1-1~1-4 통과 여부는 실행 후 확인.
    "n_estimators": 100,
    "max_depth": 15,
    "min_samples_leaf": 1,
    "min_samples_split": 2,
    "max_features": 0.8,
    "criterion": "squared_error",
    "bootstrap": False,
    # n_jobs=1 per estimator: MultiOutputRegressor 가 outputs 를 병렬화하므로
    # 중첩 병렬 (tree × output) 로 인한 WinError 1450 방지.
    "n_jobs": 1,
}


def load_joined_with_all_cols() -> pd.DataFrame:
    """48 numeric 컬럼을 모두 로드 (seoul_district_sales 조인)."""
    cols = ", ".join([f"s.{c}" for c in TARGET_COLS])
    sql = text(f"""
        SELECT q.quarter, q.dong_code, q.dong_name, q.industry_code, q.industry_name,
               q.store_count, q.open_count, q.close_count, q.closure_rate, q.franchise_count,
               {cols}
        FROM store_quarterly q
        LEFT JOIN seoul_district_sales s
          ON q.quarter = s.quarter AND q.dong_code = s.dong_code
         AND q.industry_code = s.industry_code
        WHERE q.dong_code LIKE '11440%'
        ORDER BY q.quarter, q.dong_code, q.industry_code
    """)
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn)
    anchor = pd.read_csv(ANCHOR_CSV).rename(columns={"qkey": "quarter", "수치값": "kosis_index"})
    anchor = anchor.groupby("quarter", as_index=False)["kosis_index"].mean()
    return df.merge(anchor[["quarter", "kosis_index"]], on="quarter", how="left")


def build_features_v4(df: pd.DataFrame) -> pd.DataFrame:
    """v3 와 동일한 피처 (LOO 는 본 학습에선 적용 X — 모든 alive 활용)."""
    X = pd.DataFrame(index=df.index)
    X["store_count"] = df["store_count"].fillna(df["store_count"].median())
    X["log_store_count"] = np.log1p(X["store_count"])
    X["kosis_index"] = df["kosis_index"]
    X["log_kosis"] = np.log(df["kosis_index"])
    X["franchise_ratio"] = df["franchise_count"].fillna(0) / df["store_count"].clip(lower=1)
    X["open_ratio"] = df["open_count"].fillna(0) / df["store_count"].clip(lower=1)
    X["closure_rate"] = df["closure_rate"].fillna(0)
    X["q_of_year"] = df["quarter"] % 10
    X["year"] = df["quarter"] // 10
    for ind in df["industry_code"].unique():
        X[f"ind_{ind}"] = (df["industry_code"] == ind).astype(int)
    df_alive = df[df["monthly_sales"].notna()]
    X["dong_avg_store"] = df["dong_code"].map(df_alive.groupby("dong_code")["store_count"].mean())
    X["dong_avg_store"] = X["dong_avg_store"].fillna(df_alive["store_count"].mean())
    combo = df_alive.groupby(["dong_code", "industry_code"])["store_count"].mean()
    X["combo_avg_store"] = df.set_index(["dong_code", "industry_code"]).index.map(combo.to_dict())
    X["combo_avg_store"] = X["combo_avg_store"].fillna(combo.mean())
    return X


def fit_seed_ensemble_multi(
    X: pd.DataFrame,
    Y: pd.DataFrame,
    seeds: list[int],
    best_params: dict,
    ckpt_dir: Path | None = None,
) -> list[MultiOutputRegressor]:
    """6 seed × MultiOutputRegressor(ExtraTrees) — 48 컬럼 동시 학습.

    checkpoint: 각 seed 완료 시 디스크 저장 → 중단 시 재개.
    ckpt_dir: None 이면 CHECKPOINT_DIR 사용 (본 학습 기본값).
    """
    _ckpt_dir = Path(ckpt_dir) if ckpt_dir is not None else CHECKPOINT_DIR
    _ckpt_dir.mkdir(parents=True, exist_ok=True)
    models = []
    for seed in seeds:
        ckpt = _ckpt_dir / f"model_seed_{seed}.pkl"
        if ckpt.exists():
            print(f"  [seed {seed}] checkpoint 로드")
            models.append(joblib.load(ckpt))
            continue
        print(f"  [seed {seed}] 학습 중...")
        m = MultiOutputRegressor(
            ExtraTreesRegressor(**best_params, random_state=seed),
            n_jobs=4,
        ).fit(X, Y)
        joblib.dump(m, ckpt)
        models.append(m)
    return models


def predict_with_ci_multi(
    models: list[MultiOutputRegressor],
    X_missing: pd.DataFrame,
    store_count: np.ndarray,
) -> dict[str, pd.DataFrame]:
    """6 seed × 48 컬럼 → mean / std / lower_95 / upper_95 / ci_width_ratio."""
    preds_log = np.array([m.predict(X_missing) for m in models])  # (6, N, 48)
    sc_b = np.maximum(store_count, 1)[None, :, None]  # (1, N, 1)
    preds = np.expm1(preds_log) * sc_b
    mean = preds.mean(axis=0)
    std = preds.std(axis=0, ddof=1)
    lower_95 = np.maximum(0, mean - 1.96 * std)
    upper_95 = mean + 1.96 * std
    ci_width_ratio = (upper_95 - lower_95) / np.maximum(mean, 1)
    return {
        "mean": pd.DataFrame(mean, columns=TARGET_COLS),
        "std": pd.DataFrame(std, columns=TARGET_COLS),
        "lower_95": pd.DataFrame(lower_95, columns=TARGET_COLS),
        "upper_95": pd.DataFrame(upper_95, columns=TARGET_COLS),
        "ci_width_ratio": pd.DataFrame(ci_width_ratio, columns=TARGET_COLS),
    }


def detect_extrapolation_cells(
    df_missing: pd.DataFrame,
    pred_dict: dict[str, pd.DataFrame],
    threshold_ratio: float = 1.8,
) -> np.ndarray:
    """외삽 셀 = (24Q 전체 결측) OR (monthly_sales std / median_std ≥ 1.8)."""
    n = len(df_missing)
    mask = np.zeros(n, dtype=bool)

    # 1) 24Q 전체 결측 — 같은 (dong_code, industry_code) 가 24개 이상이면 전 기간 결측
    if "dong_code" in df_missing.columns and "industry_code" in df_missing.columns:
        full_missing_combos = df_missing.groupby(["dong_code", "industry_code"]).size().pipe(lambda s: s[s >= 24]).index
        for d, i in full_missing_combos:
            sel = (df_missing["dong_code"] == d) & (df_missing["industry_code"] == i)
            mask |= sel.values

    # 2) high variance — monthly_sales std 기준
    monthly_std = pred_dict["std"]["monthly_sales"].values
    median_std = float(np.median(monthly_std)) if len(monthly_std) > 0 else 0.0
    if median_std > 0:
        high_var = monthly_std >= threshold_ratio * median_std
        mask |= high_var

    return mask


def calculate_confidence(
    pred_dict: dict[str, pd.DataFrame],
    extrap_mask: np.ndarray,
    audit_metrics: dict,
) -> np.ndarray:
    """confidence = base × ci_penalty × extrapolation_penalty (monthly 기준 1개)."""
    base = max(0.60, 1.0 - audit_metrics.get("mnar_wape", 25.0) / 100.0)
    ci = pred_dict["ci_width_ratio"]["monthly_sales"].values
    ci_penalty = np.where(ci > 0.5, 1.0 - np.minimum(0.3, ci - 0.5), 1.0)
    extrap_penalty = np.where(extrap_mask, 0.4 / max(base, 0.001), 1.0)
    conf = base * ci_penalty * extrap_penalty
    return np.clip(conf, 0.10, 1.0)


def main():
    print("=== Phase 1: Multi-Output v4 본 학습 ===")
    df = load_joined_with_all_cols()
    print(f"[data] total={len(df)} alive={df['monthly_sales'].notna().sum()}")

    X = build_features_v4(df)
    alive_mask = df["monthly_sales"].notna()
    missing_mask = ~alive_mask
    df_alive = df[alive_mask].copy()
    df_missing = df[missing_mask].copy()

    # Y: 48 컬럼 log1p 변환
    # NaN guard: TARGET_COLS 전체가 NaN 인 행 제거 (fillna 전에 먼저 체크)
    valid_rows = ~df_alive[TARGET_COLS].isna().all(axis=1)
    n_dropped = (~valid_rows).sum()
    if n_dropped > 0:
        print(f"[warn] dropped {n_dropped} rows with all-NaN target cols")
    df_alive_clean = df_alive[valid_rows].copy()
    Y_raw = df_alive_clean[TARGET_COLS].fillna(0).astype(float)
    Y_alive = Y_raw.apply(np.log1p)
    X_alive = X.loc[df_alive_clean.index]

    print(f"[fit] 6 seed × ExtraTrees Multi-Output ({len(TARGET_COLS)} 컬럼)...")
    print(f"      학습 샘플: {len(X_alive)}, 결측 셀: {len(df_missing)}")
    models = fit_seed_ensemble_multi(X_alive, Y_alive, SEEDS, BEST_PARAMS)

    print(f"[predict] {len(df_missing)} 결측 셀 × 48 컬럼 ...")
    # store_count 곱셈은 predict_with_ci_multi 내부에서 수행 (log1p 역변환 × store_count)
    # count 컬럼은 store_count 곱셈 X → ones 전달 후 sales 만 별도 스케일
    preds = predict_with_ci_multi(models, X.loc[missing_mask], np.ones(len(df_missing)))

    # SALES 컬럼만 store_count 곱셈 (count 컬럼은 이미 개수 단위)
    sc_missing = df_missing["store_count"].fillna(1).astype(float).values
    for col in SALES_COLS:
        for k in ["mean", "std", "lower_95", "upper_95"]:
            preds[k][col] = preds[k][col] * sc_missing
    # ci_width_ratio 재계산
    preds["ci_width_ratio"] = pd.DataFrame(
        (preds["upper_95"].values - preds["lower_95"].values) / np.maximum(preds["mean"].values, 1),
        columns=TARGET_COLS,
    )

    # 합격선 1-1: std/mean ≤ 0.10
    monthly_mean = preds["mean"]["monthly_sales"].values
    monthly_std = preds["std"]["monthly_sales"].values
    valid_mean = np.maximum(monthly_mean, 1)
    cv = monthly_std / valid_mean
    cv_mean = float(cv.mean())
    print(f"[합격선 1-1] std/mean (monthly_sales) = {cv_mean:.4f}  (기준: ≤ 0.10)")
    if cv_mean > 0.10:
        raise EnsembleInstabilityError(f"6 seed std/mean = {cv_mean:.4f} > 0.10 합격선 미달 — 앙상블 불안정")

    # 합격선 1-2: CI 폭 ≤ 0.50
    ci_mean = float(preds["ci_width_ratio"]["monthly_sales"].mean())
    print(f"[합격선 1-2] CI 폭 (monthly_sales ci_width_ratio) = {ci_mean:.4f}  (기준: ≤ 0.50)")

    # raking — sales + count
    print("[raking] sum constraint × 5 종 × {sales, count}")
    mean_pre_raking = preds["mean"].copy()
    preds["mean"] = enforce_sum_consistency(preds["mean"], SUM_CONSTRAINTS_SALES)
    preds["mean"] = enforce_sum_consistency(preds["mean"], SUM_CONSTRAINTS_COUNT)

    # CI 동기화: raking scale 을 std / lower_95 / upper_95 에도 반영
    scale = preds["mean"] / mean_pre_raking.replace(0, 1)
    preds["std"] = preds["std"] * scale
    preds["lower_95"] = (preds["mean"] - 1.96 * preds["std"]).clip(lower=0)
    preds["upper_95"] = preds["mean"] + 1.96 * preds["std"]
    preds["ci_width_ratio"] = (preds["upper_95"] - preds["lower_95"]) / preds["mean"].clip(lower=1)

    # extrapolation
    extrap_mask = detect_extrapolation_cells(df_missing.reset_index(drop=True), preds, 1.8)
    extrap_count = int(extrap_mask.sum())
    total_count = len(extrap_mask)
    extrap_ratio = extrap_count / total_count
    print(f"[합격선 1-3] 외삽 셀: {extrap_count} / {total_count} ({extrap_ratio * 100:.1f}%)  (기준: std ≥ 1.8×median)")
    if extrap_ratio > 0.50:
        raise ExtrapolationCellOverflowError(
            f"외삽 셀 {extrap_count}/{total_count} ({extrap_ratio * 100:.1f}%) > 50% — 모델 신뢰 불가"
        )

    # confidence (Phase 2 audit 결과 들어오기 전: 임시 13.5%)
    audit_temp = {"mnar_wape": 13.5}
    conf = calculate_confidence(preds, extrap_mask, audit_temp)
    conf_mean = float(conf.mean())
    print(f"[합격선 1-4] confidence 평균 = {conf_mean:.3f}  (기준: ≥ 0.75)")
    print(f"             min={conf.min():.3f}, max={conf.max():.3f}")

    # wide CSV
    wide = df_missing.reset_index(drop=True)[
        ["quarter", "dong_code", "dong_name", "industry_code", "industry_name", "store_count"]
    ].copy()
    for col in TARGET_COLS:
        wide[col] = preds["mean"][col].values.astype("int64")
    wide["extrapolation_flag"] = extrap_mask
    wide["confidence"] = conf
    wide["source"] = np.where(extrap_mask, "extrapolated_v4", "imputed_v4")
    OUT_WIDE_CSV.parent.mkdir(parents=True, exist_ok=True)
    wide.to_csv(OUT_WIDE_CSV, index=False, encoding="utf-8-sig")
    print(f"[saved] {OUT_WIDE_CSV}  ({len(wide)} 셀)")

    # detail CSV (long, 137 × 47 = 6,439 row — monthly_sales 제외)
    rows = []
    detail_cols = [c for c in TARGET_COLS if c != "monthly_sales"]
    for i, missing_row in df_missing.reset_index(drop=True).iterrows():
        for col in detail_cols:
            rows.append(
                {
                    "quarter": missing_row["quarter"],
                    "dong_code": missing_row["dong_code"],
                    "industry_code": missing_row["industry_code"],
                    "column_name": col,
                    "imputed_value": int(preds["mean"][col].iloc[i]),
                    "lower_95": int(preds["lower_95"][col].iloc[i]),
                    "upper_95": int(preds["upper_95"][col].iloc[i]),
                    "std": float(preds["std"][col].iloc[i]),
                    "ci_width_ratio": float(preds["ci_width_ratio"][col].iloc[i]),
                    "confidence": float(conf[i]),
                }
            )
    detail = pd.DataFrame(rows)
    detail.to_csv(OUT_DETAIL_CSV, index=False, encoding="utf-8-sig")
    print(f"[saved] {OUT_DETAIL_CSV}  ({len(detail)} row)")

    # 합격선 최종 요약
    print("\n=== 합격선 최종 요약 ===")
    print(f"  1-1 std/mean        : {cv_mean:.4f}  {'✓' if cv_mean <= 0.10 else '✗'} (≤ 0.10)")
    print(f"  1-2 CI 폭           : {ci_mean:.4f}  {'✓' if ci_mean <= 0.50 else '✗'} (≤ 0.50)")
    print(f"  1-3 외삽 셀         : {extrap_count}/{total_count}  ✓ (std ≥ 1.8×median 기준)")
    print(f"  1-4 confidence 평균 : {conf_mean:.3f}  {'✓' if conf_mean >= 0.75 else '✗'} (≥ 0.75)")


if __name__ == "__main__":
    main()
