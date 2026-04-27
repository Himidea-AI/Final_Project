"""Phase A: 서울 전체 10업종 매출 역추적 (마포 → 424동 확장).

대상: seoul_district_sales (424동 × 10업종 × 24Q = 101,760 grid, 13,822 결측)
모델: ExtraTrees (Optuna-tuned params)
anchor: KOSIS DT_1KC2023 서울 숙박·음식점업 지수
store_count: seoul_district_stores (서울 전체 완결)

출력:
  validation/results/imputed_seoul_sales_10ind.csv
  docs/sales-imputation/phase_a_seoul_report.md
"""

from __future__ import annotations

import os
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.metrics import r2_score
from sklearn.model_selection import KFold
from sqlalchemy import create_engine, text

sys.stdout.reconfigure(encoding="utf-8")
REPO_ROOT = Path(__file__).resolve().parents[1]
for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())
engine = create_engine(os.environ["POSTGRES_URL"])

TUNED_PARAMS = dict(
    n_estimators=300,
    max_depth=35,
    min_samples_leaf=1,
    min_samples_split=2,
    max_features=1.0,
    criterion="squared_error",
    bootstrap=False,
    random_state=42,
    n_jobs=-1,
)


def load_data():
    sql = text("""
        SELECT q.quarter, q.dong_code, q.dong_name, q.industry_code, q.industry_name,
               s.monthly_sales,
               q.store_count, q.open_count, q.close_count, q.closure_rate, q.franchise_count
        FROM seoul_district_stores q
        LEFT JOIN seoul_district_sales s USING (quarter, dong_code, industry_code)
    """)
    with engine.connect() as c:
        df = pd.read_sql(sql, c)
    anchor = pd.read_csv(REPO_ROOT / "validation" / "results" / "phase1b_anchor_series.csv").rename(
        columns={"qkey": "quarter", "수치값": "kosis_index"}
    )
    anchor = anchor.groupby("quarter", as_index=False)["kosis_index"].mean()
    df = df.merge(anchor[["quarter", "kosis_index"]], on="quarter", how="left")
    df["sales_per_store"] = df["monthly_sales"] / df["store_count"].clip(lower=1)
    # kosis_index NaN (anchor 없는 분기) → 전체 평균
    df["kosis_index"] = df["kosis_index"].fillna(df["kosis_index"].mean())
    return df


def build_features(df):
    X = pd.DataFrame(index=df.index)
    X["store_count"] = df["store_count"].fillna(df["store_count"].median())
    X["log_store_count"] = np.log1p(X["store_count"])
    X["kosis_index"] = df["kosis_index"]
    X["log_kosis"] = np.log(df["kosis_index"])
    X["franchise_ratio"] = df["franchise_count"].fillna(0) / df["store_count"].clip(lower=1)
    X["open_ratio"] = df["open_count"].fillna(0) / df["store_count"].clip(lower=1)
    X["closure_rate"] = df["closure_rate"].fillna(0).astype(float)
    X["q_of_year"] = df["quarter"] % 10
    X["year"] = df["quarter"] // 10
    # 업종 dummy (10)
    for ind in sorted(df["industry_code"].unique()):
        X[f"ind_{ind}"] = (df["industry_code"] == ind).astype(int)
    # 구 dummy (25개) — 서울은 25개 구라 feasible
    df_ = df.copy()
    df_["gu_code"] = df_["dong_code"].str[:5]
    for gu in sorted(df_["gu_code"].unique()):
        X[f"gu_{gu}"] = (df_["gu_code"] == gu).astype(int)
    # 동 레벨 통계 (leave-one-out 없이 전체)
    alive = df[df["monthly_sales"].notna()]
    ds = alive.groupby("dong_code")["store_count"].mean()
    dt = alive.groupby("dong_code")["store_count"].sum()
    X["dong_avg_store"] = df["dong_code"].map(ds).fillna(ds.mean())
    X["dong_total_store"] = df["dong_code"].map(dt).fillna(dt.mean())
    # 동×업종 평균
    co = df.groupby(["dong_code", "industry_code"])["store_count"].mean()
    X["combo_avg_store"] = df.set_index(["dong_code", "industry_code"]).index.map(co.to_dict())
    X["combo_avg_store"] = X["combo_avg_store"].fillna(co.mean())
    return X


def score(actual, pred):
    abs_err = np.abs(actual - pred)
    wape = float(abs_err.sum() / actual.sum() * 100) if actual.sum() > 0 else np.nan
    r2 = float(r2_score(actual, pred)) if len(actual) > 1 else np.nan
    try:
        r = float(pearsonr(actual, pred)[0])
    except Exception:
        r = np.nan
    return {"wape": wape, "r2": r2, "r": r, "n": len(actual)}


def main():
    print("=== Phase A: 서울 전체 10업종 매출 역추적 ===\n")
    t0 = time.time()
    df = load_data()
    X = build_features(df)
    print(
        f"[data] total={len(df):,}  alive={df['monthly_sales'].notna().sum():,}  missing={df['monthly_sales'].isna().sum():,}"
    )
    print(
        f"[dims] 구={df['dong_code'].str[:5].nunique()}, 동={df['dong_code'].nunique()}, 업종={df['industry_code'].nunique()}, 분기={df['quarter'].nunique()}"
    )
    print(f"[features] {X.shape[1]}개\n")

    alive_mask = df["monthly_sales"].notna()
    alive_idx = df[alive_mask].index.values
    store = df["store_count"].values.astype(float)
    actual_sales = df["monthly_sales"].values
    y_sps = np.log1p(df["sales_per_store"].values)

    # === 10-fold Random CV ===
    print("--- Random 10-fold CV ---")
    kf = KFold(10, shuffle=True, random_state=42)
    r_wapes, r_rs = [], []
    for fi, (tr, te) in enumerate(kf.split(alive_idx), 1):
        tr_idx = alive_idx[tr]
        te_idx = alive_idx[te]
        m = ExtraTreesRegressor(**TUNED_PARAMS)
        m.fit(X.iloc[tr_idx], y_sps[tr_idx])
        pred = np.expm1(m.predict(X.iloc[te_idx])) * np.maximum(store[te_idx], 1)
        s = score(actual_sales[te_idx], pred)
        r_wapes.append(s["wape"])
        r_rs.append(s["r"])
        if fi <= 3 or fi == 10:
            print(f"  Fold {fi:2d}/10 (n={s['n']}): WAPE={s['wape']:.2f}% r={s['r']:.3f}")
    print(f"  → 평균 WAPE: {np.mean(r_wapes):.2f}% ± {np.std(r_wapes):.2f}")
    print(f"  → 평균 r   : {np.mean(r_rs):.4f}")

    # === MNAR-Mimic CV ===
    print("\n--- MNAR-Mimic CV (작은 셀 hold-out) ---")
    miss_q95 = df.loc[~alive_mask, "store_count"].quantile(0.95)
    mimic_idx = df[alive_mask & (df["store_count"] <= miss_q95)].index.values
    print(f"  결측 유사 alive 셀 수: {len(mimic_idx):,}  (store_count <= {miss_q95:.0f})")
    rng = np.random.default_rng(42)
    folds = np.array_split(rng.permutation(mimic_idx), 5)
    m_wapes, m_rs = [], []
    for fi, te_idx in enumerate(folds, 1):
        tr_mask = alive_mask & (~df.index.isin(te_idx))
        tr_idx = df[tr_mask].index.values
        m = ExtraTreesRegressor(**TUNED_PARAMS)
        m.fit(X.iloc[tr_idx], y_sps[tr_idx])
        pred = np.expm1(m.predict(X.iloc[te_idx])) * np.maximum(store[te_idx], 1)
        s = score(actual_sales[te_idx], pred)
        m_wapes.append(s["wape"])
        m_rs.append(s["r"])
        print(f"  Fold {fi}/5 (n={s['n']}): WAPE={s['wape']:.2f}% r={s['r']:.3f}")
    print(f"  → MNAR WAPE: {np.mean(m_wapes):.2f}% ± {np.std(m_wapes):.2f}")

    # === 최종 학습 + 복원 ===
    print("\n--- 전체 alive 학습 → 결측 복원 ---")
    m = ExtraTreesRegressor(**TUNED_PARAMS)
    m.fit(X[alive_mask], y_sps[alive_mask.values])
    pred_all = np.expm1(m.predict(X)) * np.maximum(store, 1)

    out = df[
        [
            "quarter",
            "dong_code",
            "dong_name",
            "industry_code",
            "industry_name",
            "store_count",
            "kosis_index",
            "monthly_sales",
        ]
    ].copy()
    out["imputed_sales"] = np.where(alive_mask, df["monthly_sales"], pred_all)
    out["is_missing"] = ~alive_mask
    out["source"] = np.where(alive_mask, "original", "reverse_engineered_et_tuned")
    mnar_wape = float(np.mean(m_wapes))
    out["confidence"] = np.where(alive_mask, 1.0, max(0.60, 1.0 - mnar_wape / 100))

    out_csv = REPO_ROOT / "validation" / "results" / "imputed_seoul_sales_10ind.csv"
    out.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"  복원 셀: {(~alive_mask).sum():,}  confidence={max(0.60, 1.0 - mnar_wape / 100):.2f}")
    print(f"  [saved] {out_csv}")

    # === 구별 WAPE 분석 ===
    print("\n--- 구별 결측 분포 및 복원 커버리지 ---")
    df_ = df.copy()
    df_["gu_code"] = df_["dong_code"].str[:5]
    by_gu = (
        df_.assign(missing=~alive_mask)
        .groupby("gu_code")
        .agg(
            total=("dong_code", "count"),
            missing=("missing", "sum"),
        )
    )
    by_gu["miss_rate"] = by_gu["missing"] / by_gu["total"] * 100
    print(by_gu.sort_values("miss_rate", ascending=False).head(10).round(2).to_string())

    print(f"\n=== 완료: {time.time() - t0:.0f}s ===")
    print(f"  최종 MNAR WAPE: {mnar_wape:.2f}%")
    print(f"  Random 10-fold WAPE: {np.mean(r_wapes):.2f}%")
    print(f"  복원 cells: {(~alive_mask).sum():,} / full {len(df):,}")

    # Markdown 저장
    md = []
    md.append("# Phase A: 서울 전체 10업종 매출 역추적 결과\n")
    md.append("**대상:** `seoul_district_sales` (424동 × 10업종 × 24Q)")
    md.append(f"**결측:** 13,822 ({len(df) - alive_mask.sum():,}개) = {(1 - alive_mask.sum() / len(df)) * 100:.1f}%")
    md.append("**모델:** ExtraTrees Optuna-tuned (n_estimators=300, max_depth=35)")
    md.append("")
    md.append("## 결과")
    md.append(f"- **Random 10-fold WAPE**: {np.mean(r_wapes):.2f}% ± {np.std(r_wapes):.2f}")
    md.append(f"- **MNAR-Mimic WAPE** (주 지표): **{mnar_wape:.2f}%**")
    md.append(f"- Pearson r (random CV): {np.mean(r_rs):.4f}")
    md.append(f"- confidence: {max(0.60, 1.0 - mnar_wape / 100):.2f}")
    md.append("")
    md.append("## 마포 1개 구 결과와 비교")
    md.append("| Scope | 셀 수 | MNAR WAPE |")
    md.append("|:----|:--:|:--:|")
    md.append("| 마포 (기존) | 3,840 | 13.35% |")
    md.append(f"| **서울 전체 (Phase A)** | **{len(df):,}** | **{mnar_wape:.2f}%** |")
    md.append("")
    md.append("## 구별 결측률 상위 10")
    md.append("| gu_code | total | missing | rate(%) |")
    md.append("|:----|:--:|:--:|:--:|")
    for idx, row in by_gu.sort_values("miss_rate", ascending=False).head(10).iterrows():
        md.append(f"| {idx} | {row['total']} | {row['missing']} | {row['miss_rate']:.1f} |")
    (REPO_ROOT / "docs" / "sales-imputation" / "phase_a_seoul_report.md").write_text("\n".join(md), encoding="utf-8")
    print("  [saved] docs/sales-imputation/phase_a_seoul_report.md")


if __name__ == "__main__":
    main()
