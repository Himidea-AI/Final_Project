# validation/compare_learning_paths.py
"""Phase 0-3: 3 학습 path × 6 seed × MNAR-mimic CV 비교.

(A) mapo_only:     마포 alive 만 학습 → 마포 137 예측
(B) seoul_to_mapo: 서울 10 업종 alive 학습 → 마포 137 예측
(C) hybrid:        서울 alive 학습 + 마포 sample_weight=5 → 마포 137 예측

합격: 최저 WAPE − 마포 단독 WAPE ≥ −1.5%p 시 그 path 채택.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor
from sqlalchemy import create_engine, text

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
ANCHOR_CSV = REPO_ROOT / "validation" / "results" / "phase1b_anchor_series.csv"
OUT_CSV = REPO_ROOT / "validation" / "results" / "learning_paths_comparison.csv"


def _get_engine():
    return create_engine(os.environ["POSTGRES_URL"])


SEEDS = [42, 2026, 7, 13, 99, 1234]
THRESHOLD_IMPROVEMENT_PP = 1.5  # 합격선 0-3
N_FOLDS = 5

INDUSTRIES_10 = [
    "CS100001",
    "CS100002",
    "CS100003",
    "CS100004",
    "CS100005",
    "CS100006",
    "CS100007",
    "CS100008",
    "CS100009",
    "CS100010",
]


def load_data(scope: str) -> pd.DataFrame:
    """scope = 'mapo' or 'seoul_10ind'.

    마포(store_quarterly): 16동, 3840행
    서울25구(seoul_district_stores): 425동, 100,587행 — seoul_district_sales LEFT JOIN 시 87,938 alive
    """
    engine = _get_engine()
    if scope == "mapo":
        # 마포구 전용: store_quarterly (마포만 적재)
        store_table = "store_quarterly"
        where = "q.dong_code LIKE '11440%'"
    else:
        # 서울 25구: seoul_district_stores (store_quarterly 의 서울 전체 버전)
        store_table = "seoul_district_stores"
        ind_list = "', '".join(INDUSTRIES_10)
        where = f"q.industry_code IN ('{ind_list}')"

    sql = text(f"""
        SELECT q.quarter, q.dong_code, q.industry_code,
               s.monthly_sales, q.store_count, q.open_count, q.close_count,
               q.closure_rate, q.franchise_count
        FROM {store_table} q
        LEFT JOIN seoul_district_sales s
          ON q.quarter = s.quarter AND q.dong_code = s.dong_code
         AND q.industry_code = s.industry_code
        WHERE {where}
        ORDER BY q.quarter, q.dong_code, q.industry_code
    """)
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn)
    anchor = pd.read_csv(ANCHOR_CSV).rename(columns={"qkey": "quarter", "수치값": "kosis_index"})
    anchor = anchor.groupby("quarter", as_index=False)["kosis_index"].mean()
    df = df.merge(anchor[["quarter", "kosis_index"]], on="quarter", how="left")
    df["sales_per_store"] = df["monthly_sales"] / df["store_count"].clip(lower=1)
    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """LOO 미적용 (path 비교 용도, leak 제어는 Task 3 결과로 별도 적용)."""
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
    for ind in INDUSTRIES_10:
        X[f"ind_{ind}"] = (df["industry_code"] == ind).astype(int)
    return X


def mnar_mimic_cv_path(
    df_train: pd.DataFrame,
    df_target: pd.DataFrame,
    sample_weight: np.ndarray | None,
    seeds: list[int],
) -> dict:
    """target (마포) 의 결측 store_count 분포 유사 셀로 hold-out + train 으로 학습."""
    X_train = build_features(df_train)
    X_target = build_features(df_target)
    alive_target = df_target[df_target["monthly_sales"].notna()].copy()
    missing_q95 = df_target.loc[~df_target["monthly_sales"].notna(), "store_count"].quantile(0.95)
    mimic_idx = alive_target[alive_target["store_count"] <= missing_q95].index.values

    wapes = []
    for seed in seeds:
        rng = np.random.default_rng(seed)
        folds = np.array_split(rng.permutation(mimic_idx), N_FOLDS)
        fold_wapes = []
        for te_idx in folds:
            # train: train df 의 alive + target df 의 alive (te_idx 제외)
            tr_mask_train = df_train["monthly_sales"].notna()
            tr_mask_target = df_target["monthly_sales"].notna() & (~df_target.index.isin(te_idx))
            X_tr = pd.concat([X_train[tr_mask_train], X_target[tr_mask_target]], ignore_index=True)
            y_tr = np.concatenate(
                [
                    np.log1p(df_train.loc[tr_mask_train, "sales_per_store"].values),
                    np.log1p(df_target.loc[tr_mask_target, "sales_per_store"].values),
                ]
            )
            sw_tr = None
            if sample_weight is not None:
                sw_train_part = np.ones(int(tr_mask_train.sum()))
                sw_target_part = np.full(int(tr_mask_target.sum()), 5.0)
                sw_tr = np.concatenate([sw_train_part, sw_target_part])

            m = ExtraTreesRegressor(
                n_estimators=300,
                max_depth=35,
                min_samples_leaf=1,
                bootstrap=False,
                random_state=seed,
                n_jobs=-1,
            )
            m.fit(X_tr, y_tr, sample_weight=sw_tr)

            log_pred = m.predict(X_target.loc[te_idx])
            sales_pred = np.expm1(log_pred) * np.maximum(df_target.loc[te_idx, "store_count"].values, 1)
            sales_pred = np.clip(sales_pred, 0, None)
            actual = df_target.loc[te_idx, "monthly_sales"].values
            fold_wapes.append(np.abs(actual - sales_pred).sum() / actual.sum() * 100)
        wapes.append(np.mean(fold_wapes))

    return {"mean_wape": float(np.mean(wapes)), "std_wape": float(np.std(wapes))}


if __name__ == "__main__":
    for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

    print("=== Phase 0-3: Learning Path Comparison ===")
    print("[1/2] Loading mapo + seoul_10ind...")
    df_mapo = load_data("mapo")
    df_seoul = load_data("seoul_10ind")
    df_seoul_only = df_seoul[~df_seoul["dong_code"].str.startswith("11440")].copy().reset_index(drop=True)
    print(f"  mapo:  {len(df_mapo)} (alive {df_mapo['monthly_sales'].notna().sum()})")
    print(f"  seoul (마포 제외): {len(df_seoul_only)} (alive {df_seoul_only['monthly_sales'].notna().sum()})")

    print("\n[2/2] Running 3 paths × 6 seeds...")
    empty_df = df_mapo.iloc[0:0].copy()

    print("  [A] mapo_only ...")
    res_a = mnar_mimic_cv_path(empty_df, df_mapo, sample_weight=None, seeds=SEEDS)
    print(f"      WAPE = {res_a['mean_wape']:.2f}% ± {res_a['std_wape']:.2f}")

    print("  [B] seoul_to_mapo ...")
    res_b = mnar_mimic_cv_path(df_seoul_only, df_mapo, sample_weight=None, seeds=SEEDS)
    print(f"      WAPE = {res_b['mean_wape']:.2f}% ± {res_b['std_wape']:.2f}")

    print("  [C] hybrid (마포 sample_weight=5) ...")
    res_c = mnar_mimic_cv_path(df_seoul_only, df_mapo, sample_weight=np.ones(1), seeds=SEEDS)
    print(f"      WAPE = {res_c['mean_wape']:.2f}% ± {res_c['std_wape']:.2f}")

    results = [
        {"path": "mapo_only", **res_a},
        {"path": "seoul_to_mapo", **res_b},
        {"path": "hybrid", **res_c},
    ]
    out_df = pd.DataFrame(results)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    best = min(results, key=lambda x: x["mean_wape"])
    improvement = res_a["mean_wape"] - best["mean_wape"]
    print(f"\n[합격선 0-3] best ({best['path']}) − mapo_only = −{improvement:.2f}%p")
    if improvement >= THRESHOLD_IMPROVEMENT_PP:
        print(f"✅ ≥ {THRESHOLD_IMPROVEMENT_PP}%p — '{best['path']}' 채택")
    else:
        print(f"⚠️  < {THRESHOLD_IMPROVEMENT_PP}%p — 'mapo_only' 채택")

    print(f"[saved] {OUT_CSV}")
