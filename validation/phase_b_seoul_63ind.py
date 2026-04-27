"""Phase B: 서울 전체 63업종 매출 역추적.

대상: district_sales_seoul (425동 × 63업종 × 28Q = 749,700 grid, 274,366 결측 36.6%)
store_count: seoul_adstrd_stor (100업종, 매출 63업종 완전 커버)
anchor: KOSIS DT_1KC2023 (음식점은 강력, 비음식점은 약한 신호)
모델: ExtraTrees Optuna-tuned

실행 시간 최적화:
  - Random 5-fold (not 10) + MNAR 5-fold
  - 구(25) dummy 사용, 동(425) dummy 제거
  - dong 통계 feature 로 동 정보 보존
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
    max_depth=30,
    min_samples_leaf=2,
    min_samples_split=2,
    max_features=0.7,
    criterion="squared_error",
    bootstrap=False,
    random_state=42,
    n_jobs=-1,
)


def load_data():
    """store_quarterly (100업종) ← district_sales_seoul (63업종 매출) 조인."""
    sql = text("""
        SELECT q.quarter, q.dong_code, q.dong_name, q.industry_code, q.industry_name,
               s.monthly_sales,
               q.store_count, q.similar_store_count, q.open_count, q.close_count,
               q.close_rate, q.open_rate, q.franchise_count
        FROM seoul_adstrd_stor q
        LEFT JOIN district_sales_seoul s USING (quarter, dong_code, industry_code)
        WHERE q.industry_code IN (
            SELECT DISTINCT industry_code FROM district_sales_seoul
        )
    """)
    with engine.connect() as c:
        df = pd.read_sql(sql, c)
    anchor = pd.read_csv(REPO_ROOT / "validation" / "results" / "phase1b_anchor_series.csv").rename(
        columns={"qkey": "quarter", "수치값": "kosis_index"}
    )
    anchor = anchor.groupby("quarter", as_index=False)["kosis_index"].mean()
    df = df.merge(anchor[["quarter", "kosis_index"]], on="quarter", how="left")
    # kosis_index 결측 (2025분기) → 그 분기의 기존 값 trend 적용: 2024Q4 값 사용
    last_known = (
        df[df["kosis_index"].notna()]["kosis_index"].iloc[-1]
        if not df[df["kosis_index"].notna()].empty
        else df["kosis_index"].mean()
    )
    df["kosis_index"] = df["kosis_index"].fillna(last_known)
    df["sales_per_store"] = df["monthly_sales"] / df["store_count"].clip(lower=1)
    return df


def build_features(df):
    X = pd.DataFrame(index=df.index)
    X["store_count"] = df["store_count"].fillna(df["store_count"].median())
    X["log_store_count"] = np.log1p(X["store_count"])
    X["similar_store_count"] = df["similar_store_count"].fillna(0)
    X["kosis_index"] = df["kosis_index"]
    X["log_kosis"] = np.log(df["kosis_index"])
    X["franchise_ratio"] = df["franchise_count"].fillna(0) / df["store_count"].clip(lower=1)
    X["open_ratio"] = df["open_count"].fillna(0) / df["store_count"].clip(lower=1)
    X["close_rate"] = df["close_rate"].fillna(0).astype(float)
    X["open_rate"] = df["open_rate"].fillna(0).astype(float)
    X["q_of_year"] = df["quarter"] % 10
    X["year"] = df["quarter"] // 10
    # 업종 대분류 (CS1 음식점 / CS2 서비스 / CS3 소매)
    X["ind_major"] = df["industry_code"].str[:3].map({"CS1": 1, "CS2": 2, "CS3": 3}).fillna(0).astype(int)
    # 업종 dummy (63)
    for ind in sorted(df["industry_code"].unique()):
        X[f"ind_{ind}"] = (df["industry_code"] == ind).astype(int)
    # 구 dummy (25)
    df_ = df.copy()
    df_["gu_code"] = df_["dong_code"].str[:5]
    for gu in sorted(df_["gu_code"].unique()):
        X[f"gu_{gu}"] = (df_["gu_code"] == gu).astype(int)
    # 동 통계
    alive = df[df["monthly_sales"].notna()]
    ds = alive.groupby("dong_code")["store_count"].mean()
    X["dong_avg_store"] = df["dong_code"].map(ds).fillna(ds.mean())
    # 동×업종 조합 평균
    co = df.groupby(["dong_code", "industry_code"])["store_count"].mean()
    X["combo_avg_store"] = df.set_index(["dong_code", "industry_code"]).index.map(co.to_dict())
    X["combo_avg_store"] = X["combo_avg_store"].fillna(co.mean())
    # 업종별 전국 평균 매출/점포 (leave-one-cell-out 근사)
    ind_sps = alive.groupby("industry_code")["sales_per_store"].mean()
    X["ind_mean_sps"] = df["industry_code"].map(ind_sps).fillna(ind_sps.mean())
    X["log_ind_mean_sps"] = np.log1p(X["ind_mean_sps"])
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
    print("=== Phase B: 서울 전체 63업종 매출 역추적 ===\n")
    t0 = time.time()
    df = load_data()
    print(
        f"[data] total={len(df):,}  alive={df['monthly_sales'].notna().sum():,}  missing={df['monthly_sales'].isna().sum():,}"
    )
    print(
        f"[dims] 구={df['dong_code'].str[:5].nunique()}, 동={df['dong_code'].nunique()}, 업종={df['industry_code'].nunique()}, 분기={df['quarter'].nunique()}"
    )
    X = build_features(df)
    print(f"[features] {X.shape[1]}개\n")

    alive_mask = df["monthly_sales"].notna()
    alive_idx = df[alive_mask].index.values
    store = df["store_count"].values.astype(float)
    actual_sales = df["monthly_sales"].values
    y_sps = np.log1p(df["sales_per_store"].values)

    print(f"[elapsed] data/feature 준비 {time.time() - t0:.0f}s\n")

    # === Random 5-fold CV ===
    print("--- Random 5-fold CV ---")
    t1 = time.time()
    kf = KFold(5, shuffle=True, random_state=42)
    r_wapes, r_rs, r_r2s = [], [], []
    for fi, (tr, te) in enumerate(kf.split(alive_idx), 1):
        tr_idx = alive_idx[tr]
        te_idx = alive_idx[te]
        tfit = time.time()
        m = ExtraTreesRegressor(**TUNED_PARAMS)
        m.fit(X.iloc[tr_idx], y_sps[tr_idx])
        pred = np.expm1(m.predict(X.iloc[te_idx])) * np.maximum(store[te_idx], 1)
        s = score(actual_sales[te_idx], pred)
        r_wapes.append(s["wape"])
        r_rs.append(s["r"])
        r_r2s.append(s["r2"])
        print(
            f"  Fold {fi}/5 (n={s['n']}): WAPE={s['wape']:.2f}% r={s['r']:.3f} R²={s['r2']:.3f}  [{time.time() - tfit:.0f}s]",
            flush=True,
        )
    print(f"  → 평균 WAPE: {np.mean(r_wapes):.2f}% ± {np.std(r_wapes):.2f}  (총 {time.time() - t1:.0f}s)")

    # === MNAR-Mimic CV ===
    print("\n--- MNAR-Mimic 5-fold CV ---")
    t2 = time.time()
    miss_q95 = df.loc[~alive_mask, "store_count"].quantile(0.95)
    mimic_idx = df[alive_mask & (df["store_count"] <= miss_q95)].index.values
    print(f"  결측 유사 alive 셀: {len(mimic_idx):,}  (store_count <= {miss_q95:.0f})")
    rng = np.random.default_rng(42)
    folds = np.array_split(rng.permutation(mimic_idx), 5)
    m_wapes, m_rs, m_r2s = [], [], []
    for fi, te_idx in enumerate(folds, 1):
        tr_mask = alive_mask & (~df.index.isin(te_idx))
        tr_idx = df[tr_mask].index.values
        tfit = time.time()
        m = ExtraTreesRegressor(**TUNED_PARAMS)
        m.fit(X.iloc[tr_idx], y_sps[tr_idx])
        pred = np.expm1(m.predict(X.iloc[te_idx])) * np.maximum(store[te_idx], 1)
        s = score(actual_sales[te_idx], pred)
        m_wapes.append(s["wape"])
        m_rs.append(s["r"])
        m_r2s.append(s["r2"])
        print(
            f"  Fold {fi}/5 (n={s['n']}): WAPE={s['wape']:.2f}% r={s['r']:.3f}  [{time.time() - tfit:.0f}s]", flush=True
        )
    print(f"  → MNAR WAPE: {np.mean(m_wapes):.2f}% ± {np.std(m_wapes):.2f}  (총 {time.time() - t2:.0f}s)")

    # === 최종 학습 + 복원 ===
    print("\n--- 전체 학습 → 결측 복원 ---")
    t3 = time.time()
    m = ExtraTreesRegressor(**TUNED_PARAMS)
    m.fit(X[alive_mask], y_sps[alive_mask.values])
    pred_all = np.expm1(m.predict(X)) * np.maximum(store, 1)
    print(f"  예측 완료 [{time.time() - t3:.0f}s]")

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
    out["source"] = np.where(alive_mask, "original", "reverse_engineered_63ind")
    mnar_wape = float(np.mean(m_wapes))
    out["confidence"] = np.where(alive_mask, 1.0, max(0.50, 1.0 - mnar_wape / 100))

    out_csv = REPO_ROOT / "validation" / "results" / "imputed_seoul_sales_63ind.csv"
    out.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"  복원 셀: {(~alive_mask).sum():,}  confidence={max(0.50, 1.0 - mnar_wape / 100):.2f}")
    print(f"  [saved] {out_csv}")

    # === 업종 대분류별 분석 ===
    print("\n--- 업종 대분류별 커버리지 & 예측력 ---")
    df_ = df.copy()
    df_["ind_major"] = df_["industry_code"].str[:3].map({"CS1": "음식점", "CS2": "서비스", "CS3": "소매"})
    by_major = df_.groupby("ind_major").agg(
        total=("dong_code", "count"),
        missing=("monthly_sales", lambda x: x.isna().sum()),
    )
    by_major["miss_rate"] = by_major["missing"] / by_major["total"] * 100
    print(by_major.round(2).to_string())

    total_time = time.time() - t0
    print(f"\n=== 완료: {total_time:.0f}s ({total_time / 60:.1f}min) ===")
    print(f"  Random 5-fold WAPE: {np.mean(r_wapes):.2f}%")
    print(f"  MNAR WAPE         : {mnar_wape:.2f}%")
    print(f"  복원 cells        : {(~alive_mask).sum():,}")

    # Markdown 리포트
    md = []
    md.append("# Phase B: 서울 전체 63업종 매출 역추적\n")
    md.append("**대상:** `district_sales_seoul` (425동 × 63업종 × 28Q)")
    md.append(f"**결측:** {(~alive_mask).sum():,} ({(~alive_mask).sum() / len(df) * 100:.1f}%)")
    md.append(f"**피처:** {X.shape[1]}개 (store_count + KOSIS + industry 63 + gu 25 + 통계)")
    md.append("")
    md.append("## 결과")
    md.append(f"- **Random 5-fold WAPE**: {np.mean(r_wapes):.2f}% ± {np.std(r_wapes):.2f}")
    md.append(f"- **MNAR WAPE** (주 지표): **{mnar_wape:.2f}%**")
    md.append(f"- Pearson r: {np.mean(r_rs):.4f}")
    md.append(f"- R²: {np.mean(r_r2s):.4f}")
    md.append(f"- confidence: {max(0.50, 1.0 - mnar_wape / 100):.2f}")
    md.append("")
    md.append("## Phase A vs B 비교")
    md.append("| Phase | 범위 | 셀 수 | 결측 | MNAR WAPE |")
    md.append("|:----|:----|:--:|:--:|:--:|")
    md.append("| A | 서울 10업종 | 100,587 | 12,649 | 18.56% |")
    md.append(f"| **B** | **서울 63업종** | **{len(df):,}** | **{(~alive_mask).sum():,}** | **{mnar_wape:.2f}%** |")
    md.append("")
    md.append("## 업종 대분류별 결측")
    md.append("| 대분류 | total | missing | miss_rate |")
    md.append("|:----|:--:|:--:|:--:|")
    for idx, row in by_major.iterrows():
        md.append(f"| {idx} | {row['total']} | {row['missing']} | {row['miss_rate']:.1f}% |")
    (REPO_ROOT / "docs" / "sales-imputation" / "phase_b_seoul_report.md").write_text("\n".join(md), encoding="utf-8")
    print("  [saved] docs/sales-imputation/phase_b_seoul_report.md")


if __name__ == "__main__":
    main()
