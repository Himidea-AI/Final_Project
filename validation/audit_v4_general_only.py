"""Sprint 4: 일반 87셀 (extrapolation_flag=False) 만으로 별도 MNAR 측정.

전체 audit (Sprint 1 Task 7) 의 MNAR 21.23% 는 외삽 50셀이 포함된 결과.
일반 셀만의 MNAR 은 더 낮을 가능성 → confidence base 정직 산출.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

sys.stdout.reconfigure(encoding="utf-8")

from validation.reverse_engineer_sales_v4 import (  # noqa: E402
    BEST_PARAMS,
    SEEDS,
    load_joined_with_all_cols,
)
from validation.reverse_engineer_sales_v4 import build_features_v5_loo as build_features_v4  # noqa: E402

SEEDS_USED = SEEDS  # 6 seeds


def main() -> float:
    print("=== Sprint 4: 일반 셀 전용 MNAR ===")
    df = load_joined_with_all_cols()
    X = build_features_v4(df)

    # 외삽 (full_missing) 식별 — 24Q 전체 결측 (dong, industry) 조합
    missing = df[df["monthly_sales"].isna()]
    n_per_combo = missing.groupby(["dong_code", "industry_code"]).size()
    full_missing_combos = set(n_per_combo[n_per_combo >= 24].index)

    df["is_full_missing_combo"] = df.apply(
        lambda r: (r["dong_code"], r["industry_code"]) in full_missing_combos, axis=1
    )
    print(f"[full_missing combos] {len(full_missing_combos)} combo (= {len(full_missing_combos) * 24} cells)")

    # 일반 셀: alive OR (missing AND NOT full_missing_combo)
    alive_mask = df["monthly_sales"].notna()
    actual_sales = df["monthly_sales"].values
    store = df["store_count"].fillna(1).values.astype(float)
    sales_per_store = actual_sales / np.maximum(store, 1)

    # MNAR-mimic CV — 일반 셀 한정
    # missing_q95 는 일반 missing 셀의 store_count 95% (외삽 제외)
    general_missing = df[~alive_mask & ~df["is_full_missing_combo"]]
    if len(general_missing) == 0:
        print("일반 missing 셀 없음 (모든 missing 이 full_missing) — fallback 사용")
        missing_q95 = df.loc[~alive_mask, "store_count"].quantile(0.95)
    else:
        missing_q95 = general_missing["store_count"].quantile(0.95)

    print(f"[missing_q95 (일반 셀 기준)] {missing_q95:.0f}")

    # 일반 alive 셀 mimic 으로 5-fold CV (외삽 combo 제외)
    mimic_mask = alive_mask & (~df["is_full_missing_combo"]) & (df["store_count"] <= missing_q95)
    mimic_idx = df[mimic_mask].index.values
    print(f"[mimic 일반 셀] {len(mimic_idx)} 개")

    wapes = []
    for seed in SEEDS_USED:
        rng = np.random.default_rng(seed)
        folds = np.array_split(rng.permutation(mimic_idx), 5)
        fw = []
        for te_idx in folds:
            tr_mask = alive_mask & (~df.index.isin(te_idx))
            tr_idx = df[tr_mask].index.values
            y_tr = np.log1p(sales_per_store[tr_idx])
            m = ExtraTreesRegressor(**BEST_PARAMS, random_state=seed).fit(X.loc[tr_idx], y_tr)
            log_pred = m.predict(X.loc[te_idx])
            sales_pred = np.expm1(log_pred) * np.maximum(store[te_idx], 1)
            sales_pred = np.clip(sales_pred, 0, None)
            actual = actual_sales[te_idx]
            fw.append(np.abs(actual - sales_pred).sum() / max(actual.sum(), 1) * 100)
        wapes.append(np.mean(fw))
        print(f"  seed {seed}: WAPE = {wapes[-1]:.2f}%")

    mean_wape = float(np.mean(wapes))
    std_wape = float(np.std(wapes))
    print(f"\n[일반 셀 MNAR WAPE] {mean_wape:.2f}% ± {std_wape:.2f}")
    print(f"[합격선 2-3 (≤15%)] {'PASS' if mean_wape <= 15 else 'FAIL'}")

    # 결과 저장
    out_path = REPO_ROOT / "validation" / "results" / "audit_v4_general_only.csv"
    pd.DataFrame(
        [
            {
                "variant": "general_only_mnar_wape_pct",
                "mean": round(mean_wape, 2),
                "std": round(std_wape, 2),
            }
        ]
    ).to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"[saved] {out_path}")
    return mean_wape


if __name__ == "__main__":
    main()
