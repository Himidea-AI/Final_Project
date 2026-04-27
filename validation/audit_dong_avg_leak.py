# validation/audit_dong_avg_leak.py
"""Phase 0-2: MNAR/LODO CV 에서 dong_avg_store/combo_avg_store LOO 적용.

기존 v3 는 dong_avg_store 를 전체 데이터로 계산 → fold 분리해도 leak.
LOO (Leave-One-Out) 적용 시 진짜 일반화 성능 측정.
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
OUT_CSV = REPO_ROOT / "validation" / "results" / "dong_avg_leak_audit.csv"


def _get_engine():
    return create_engine(os.environ["POSTGRES_URL"])


THRESHOLD_DELTA_WAPE_PP = 3.0  # 합격선 0-2: ≤ 3%p


def load_joined() -> pd.DataFrame:
    engine = _get_engine()
    sql = text("""
        SELECT q.quarter, q.dong_code, q.dong_name, q.industry_code, q.industry_name,
               s.monthly_sales, q.store_count, q.open_count, q.close_count,
               q.closure_rate, q.franchise_count
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
    df = df.merge(anchor[["quarter", "kosis_index"]], on="quarter", how="left")
    df["sales_per_store"] = df["monthly_sales"] / df["store_count"].clip(lower=1)
    return df


def build_features_with_leak(df: pd.DataFrame, exclude_idx: pd.Index | None = None) -> pd.DataFrame:
    """v3 의 leak 있는 피처 생성 (전체 데이터로 dong_avg 계산). exclude_idx 는 무시."""
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
    # ⚠️ leak: 전체 alive 로 계산
    df_alive = df[df["monthly_sales"].notna()]
    dong_size = df_alive.groupby("dong_code")["store_count"].mean()
    X["dong_avg_store"] = df["dong_code"].map(dong_size).fillna(dong_size.mean())
    combo = df_alive.groupby(["dong_code", "industry_code"])["store_count"].mean()
    X["combo_avg_store"] = df.set_index(["dong_code", "industry_code"]).index.map(combo.to_dict())
    X["combo_avg_store"] = X["combo_avg_store"].fillna(combo.mean())
    return X


def build_features_loo(df: pd.DataFrame, exclude_idx: pd.Index) -> pd.DataFrame:
    """LOO 적용: dong_avg / combo_avg 계산 시 exclude_idx 제외."""
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
    # LOO: exclude 제외하고 alive 만 사용
    df_alive_loo = df.drop(exclude_idx).query("monthly_sales == monthly_sales")
    dong_size = df_alive_loo.groupby("dong_code")["store_count"].mean()
    X["dong_avg_store"] = df["dong_code"].map(dong_size).fillna(dong_size.mean())
    combo = df_alive_loo.groupby(["dong_code", "industry_code"])["store_count"].mean()
    X["combo_avg_store"] = df.set_index(["dong_code", "industry_code"]).index.map(combo.to_dict())
    X["combo_avg_store"] = X["combo_avg_store"].fillna(combo.mean())
    return X


def mnar_mimic_cv(df: pd.DataFrame, build_X_fn, n_folds: int = 5, seed: int = 42) -> float:
    """MNAR-mimic CV: 결측 셀 store_count 분포 유사 alive 만 hold-out."""
    alive_mask = df["monthly_sales"].notna()
    missing_q95 = df.loc[~alive_mask, "store_count"].quantile(0.95)
    mimic_idx = df[alive_mask & (df["store_count"] <= missing_q95)].index.values

    rng = np.random.default_rng(seed)
    folds = np.array_split(rng.permutation(mimic_idx), n_folds)

    wapes = []
    actual_sales = df["monthly_sales"].values
    store = df["store_count"].values.astype(float)
    y_sps = np.log1p(df["sales_per_store"].values)

    for te_idx in folds:
        tr_mask = alive_mask & (~df.index.isin(te_idx))
        tr_idx = df[tr_mask].index.values
        # 통일 시그니처: (df, exclude_idx) — leak 버전은 exclude_idx 무시
        X = build_X_fn(df, pd.Index(te_idx))

        gbm = ExtraTreesRegressor(
            n_estimators=300, max_depth=35, min_samples_leaf=1, bootstrap=False, random_state=42, n_jobs=-1
        )
        gbm.fit(X.loc[tr_idx], y_sps[tr_idx])
        log_pred = gbm.predict(X.loc[te_idx])
        sales_pred = np.expm1(log_pred) * np.maximum(store[te_idx], 1)
        sales_pred = np.clip(sales_pred, 0, None)
        actual = actual_sales[te_idx]
        wape = np.abs(actual - sales_pred).sum() / actual.sum() * 100
        wapes.append(wape)
    return float(np.mean(wapes))


if __name__ == "__main__":
    for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

    print("=== Phase 0-2: dong_avg LOO Leak Audit ===")
    df = load_joined()
    print(f"[data] total={len(df)} alive={df['monthly_sales'].notna().sum()}")

    print("\n[1/2] WITH leak (v3 방식)...")
    wape_leak = mnar_mimic_cv(df, build_features_with_leak)
    print(f"  MNAR WAPE = {wape_leak:.2f}%")

    print("\n[2/2] WITHOUT leak (LOO 적용)...")
    wape_loo = mnar_mimic_cv(df, build_features_loo)
    print(f"  MNAR WAPE = {wape_loo:.2f}%")

    delta = wape_loo - wape_leak
    print(f"\n[합격선 0-2] |delta| = |{delta:+.2f}%p|")
    if abs(delta) <= THRESHOLD_DELTA_WAPE_PP:
        print(f"✅ ≤ {THRESHOLD_DELTA_WAPE_PP}%p — v3 결과 신뢰")
    else:
        print(f"⚠️  > {THRESHOLD_DELTA_WAPE_PP}%p — v3 leak로 과소평가, 진짜 MNAR ≈ {wape_loo:.1f}%")

    out_df = pd.DataFrame(
        [
            {"variant": "v3_with_leak", "mnar_wape_pct": round(wape_leak, 2)},
            {"variant": "v4_loo", "mnar_wape_pct": round(wape_loo, 2)},
            {"variant": "delta_pp", "mnar_wape_pct": round(delta, 2)},
        ]
    )
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"[saved] {OUT_CSV}")
