"""v1/v2/v3 파이프라인을 다양한 모델로 교체·비교.

sklearn 모델군 5개 × 3개 버전 = 15 조합 매트릭스.

평가:
  v1 — IPF(0.4) + Model(0.6) 앙상블, target=log(sales)
  v2 — Model 단독, target=log(sales), dong one-hot
  v3 — Model 단독, target=log(sales_per_store), dong stats + MNAR CV

모델:
  1. GradientBoostingRegressor (sklearn, baseline)
  2. HistGradientBoostingRegressor (sklearn fast)
  3. RandomForestRegressor
  4. ExtraTreesRegressor
  5. Ridge (linear baseline)

출력: docs/sales-imputation/model_comparison.md
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from sklearn.ensemble import (
    ExtraTreesRegressor,
    GradientBoostingRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.linear_model import Ridge
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
ANCHOR_CSV = REPO_ROOT / "validation" / "results" / "phase1b_anchor_series.csv"
OUT_MD = REPO_ROOT / "docs" / "sales-imputation" / "model_comparison.md"


# ─────────────────────────────────────────────
# 모델 팩토리
# ─────────────────────────────────────────────
def make_models():
    """각 모델은 fresh instance를 반환하는 팩토리 함수."""
    return {
        "GBM": lambda: GradientBoostingRegressor(n_estimators=400, max_depth=4, learning_rate=0.05, random_state=42),
        "HistGBM": lambda: HistGradientBoostingRegressor(
            max_iter=400, max_depth=6, learning_rate=0.05, random_state=42
        ),
        "RF": lambda: RandomForestRegressor(
            n_estimators=300, max_depth=None, min_samples_leaf=3, random_state=42, n_jobs=-1
        ),
        "ExtraTrees": lambda: ExtraTreesRegressor(
            n_estimators=300, max_depth=None, min_samples_leaf=3, random_state=42, n_jobs=-1
        ),
        "Ridge": lambda: Ridge(alpha=1.0),
    }


# ─────────────────────────────────────────────
# 데이터 로드
# ─────────────────────────────────────────────
def load_joined() -> pd.DataFrame:
    sql = text("""
        SELECT q.quarter, q.dong_code, q.dong_name, q.industry_code, q.industry_name,
               s.monthly_sales,
               q.store_count, q.open_count, q.close_count, q.closure_rate, q.franchise_count
        FROM store_quarterly q
        LEFT JOIN seoul_district_sales s USING (quarter, dong_code, industry_code)
        WHERE q.dong_code LIKE '11440%'
        ORDER BY q.quarter, q.dong_code, q.industry_code
    """)
    with engine.connect() as c:
        df = pd.read_sql(sql, c)
    anchor = pd.read_csv(ANCHOR_CSV).rename(columns={"qkey": "quarter", "수치값": "kosis_index"})
    anchor = anchor.groupby("quarter", as_index=False)["kosis_index"].mean()
    df = df.merge(anchor[["quarter", "kosis_index"]], on="quarter", how="left")
    df["sales_per_store"] = df["monthly_sales"] / df["store_count"].clip(lower=1)
    return df


# ─────────────────────────────────────────────
# 피처 구성
# ─────────────────────────────────────────────
def features_v1_v2(df):
    """v1·v2 — 원본 feature set (dong one-hot 포함)."""
    X = pd.DataFrame(index=df.index)
    X["store_count"] = df["store_count"].fillna(df["store_count"].median())
    X["log_store_count"] = np.log1p(X["store_count"])
    X["kosis_index"] = df["kosis_index"]
    X["log_kosis"] = np.log(df["kosis_index"])
    X["store_x_index"] = X["store_count"] * df["kosis_index"] / 100.0
    X["franchise_ratio"] = df["franchise_count"].fillna(0) / df["store_count"].clip(lower=1)
    X["open_ratio"] = df["open_count"].fillna(0) / df["store_count"].clip(lower=1)
    X["closure_rate"] = df["closure_rate"].fillna(0)
    X["q_of_year"] = df["quarter"] % 10
    X["year"] = df["quarter"] // 10
    for ind in df["industry_code"].unique():
        X[f"ind_{ind}"] = (df["industry_code"] == ind).astype(int)
    for dong in df["dong_code"].unique():
        X[f"dong_{dong}"] = (df["dong_code"] == dong).astype(int)
    return X


def features_v3(df):
    """v3 — dong one-hot 제거 + 통계 feature."""
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
    dong_size = df_alive.groupby("dong_code")["store_count"].mean()
    dong_density = df_alive.groupby("dong_code")["store_count"].sum()
    X["dong_avg_store"] = df["dong_code"].map(dong_size).fillna(dong_size.mean())
    X["dong_total_store"] = df["dong_code"].map(dong_density).fillna(dong_density.mean())
    combo = df.groupby(["dong_code", "industry_code"])["store_count"].mean()
    X["combo_avg_store"] = df.set_index(["dong_code", "industry_code"]).index.map(combo.to_dict())
    X["combo_avg_store"] = X["combo_avg_store"].fillna(combo.mean())
    return X


# ─────────────────────────────────────────────
# 평가 지표
# ─────────────────────────────────────────────
def score(actual, pred):
    abs_err = np.abs(actual - pred)
    wape = float(abs_err.sum() / actual.sum() * 100) if actual.sum() > 0 else np.nan
    r2 = float(r2_score(actual, pred)) if len(actual) > 1 else np.nan
    try:
        r, _ = pearsonr(actual, pred)
        r = float(r)
    except Exception:
        r = np.nan
    return {"wape": wape, "r2": r2, "r": r}


# ─────────────────────────────────────────────
# IPF (간단 구현) — v1용
# ─────────────────────────────────────────────
def ipf_predict(df, alive_mask, max_iter=30, tol=1e-4):
    """3차원 IPF: dong × industry × quarter matrix 반복 보정."""
    dongs = sorted(df["dong_code"].unique())
    inds = sorted(df["industry_code"].unique())
    qtrs = sorted(df["quarter"].unique())
    D, I, Q = len(dongs), len(inds), len(qtrs)
    d_idx = {d: i for i, d in enumerate(dongs)}
    i_idx = {x: i for i, x in enumerate(inds)}
    q_idx = {q: i for i, q in enumerate(qtrs)}

    # 관측 matrix
    obs = np.full((D, I, Q), np.nan)
    for _, r in df[alive_mask].iterrows():
        obs[d_idx[r["dong_code"]], i_idx[r["industry_code"]], q_idx[r["quarter"]]] = r["monthly_sales"]

    # 초기값 = 관측 평균 (결측 위치에 대해)
    T = np.nan_to_num(obs, nan=np.nanmean(obs))
    for _ in range(max_iter):
        prev = T.copy()
        # dong axis rescale
        row_sum = T.sum(axis=(1, 2))
        obs_row_sum = np.nansum(np.where(np.isnan(obs), 0, obs), axis=(1, 2))
        ratio = np.where(row_sum > 0, obs_row_sum / row_sum, 1.0)
        T = T * ratio[:, None, None]
        # industry axis
        col_sum = T.sum(axis=(0, 2))
        obs_col_sum = np.nansum(np.where(np.isnan(obs), 0, obs), axis=(0, 2))
        ratio = np.where(col_sum > 0, obs_col_sum / col_sum, 1.0)
        T = T * ratio[None, :, None]
        # quarter axis
        t_sum = T.sum(axis=(0, 1))
        obs_t_sum = np.nansum(np.where(np.isnan(obs), 0, obs), axis=(0, 1))
        ratio = np.where(t_sum > 0, obs_t_sum / t_sum, 1.0)
        T = T * ratio[None, None, :]
        if np.nanmax(np.abs(T - prev)) < tol:
            break

    # 각 셀별 예측값 반환
    pred = np.zeros(len(df))
    for idx, r in df.reset_index(drop=True).iterrows():
        pred[idx] = T[d_idx[r["dong_code"]], i_idx[r["industry_code"]], q_idx[r["quarter"]]]
    return pred


# ─────────────────────────────────────────────
# v1: IPF + Model 앙상블
# ─────────────────────────────────────────────
def run_v1(df, model_factory, n_folds=10):
    X = features_v1_v2(df)
    y_log = np.log1p(df["monthly_sales"].values)
    alive_mask = df["monthly_sales"].notna()
    alive_idx = df[alive_mask].index.values

    wapes, rs, r2s = [], [], []
    kf = KFold(n_folds, shuffle=True, random_state=42)
    for tr_pos, te_pos in kf.split(alive_idx):
        tr_idx = alive_idx[tr_pos]
        te_idx = alive_idx[te_pos]
        # 훈련 데이터만으로 IPF
        tr_mask = pd.Series(False, index=df.index)
        tr_mask.iloc[tr_idx] = True
        pred_ipf = ipf_predict(df, tr_mask)
        # Model
        model = model_factory()
        model.fit(X.iloc[tr_idx], y_log[tr_idx])
        pred_model = np.expm1(model.predict(X.iloc[te_idx]))
        # 앙상블 0.4 IPF + 0.6 Model
        pred_ens = 0.4 * pred_ipf[te_idx] + 0.6 * pred_model
        m = score(df["monthly_sales"].iloc[te_idx].values, pred_ens)
        wapes.append(m["wape"])
        rs.append(m["r"])
        r2s.append(m["r2"])
    return {"wape": np.mean(wapes), "r": np.mean(rs), "r2": np.mean(r2s)}


# ─────────────────────────────────────────────
# v2: Model 단독 (dong one-hot)
# ─────────────────────────────────────────────
def run_v2(df, model_factory, n_folds=10):
    X = features_v1_v2(df)
    y_log = np.log1p(df["monthly_sales"].values)
    alive_mask = df["monthly_sales"].notna()
    alive_idx = df[alive_mask].index.values

    wapes, rs, r2s = [], [], []
    kf = KFold(n_folds, shuffle=True, random_state=42)
    for tr_pos, te_pos in kf.split(alive_idx):
        tr_idx = alive_idx[tr_pos]
        te_idx = alive_idx[te_pos]
        model = model_factory()
        model.fit(X.iloc[tr_idx], y_log[tr_idx])
        pred = np.expm1(model.predict(X.iloc[te_idx]))
        m = score(df["monthly_sales"].iloc[te_idx].values, pred)
        wapes.append(m["wape"])
        rs.append(m["r"])
        r2s.append(m["r2"])
    return {"wape": np.mean(wapes), "r": np.mean(rs), "r2": np.mean(r2s)}


# ─────────────────────────────────────────────
# v3: Model + sales_per_store target (MNAR 포함)
# ─────────────────────────────────────────────
def run_v3(df, model_factory):
    X = features_v3(df)
    y_sps = np.log1p(df["sales_per_store"].values)
    alive_mask = df["monthly_sales"].notna()
    alive_idx = df[alive_mask].index.values
    store = df["store_count"].values.astype(float)
    actual_sales = df["monthly_sales"].values

    # Random 10-fold
    kf = KFold(10, shuffle=True, random_state=42)
    wapes_r, rs_r, r2s_r = [], [], []
    for tr_pos, te_pos in kf.split(alive_idx):
        tr_idx = alive_idx[tr_pos]
        te_idx = alive_idx[te_pos]
        model = model_factory()
        model.fit(X.iloc[tr_idx], y_sps[tr_idx])
        pred = np.expm1(model.predict(X.iloc[te_idx])) * np.maximum(store[te_idx], 1)
        m = score(actual_sales[te_idx], pred)
        wapes_r.append(m["wape"])
        rs_r.append(m["r"])
        r2s_r.append(m["r2"])

    # MNAR-Mimic: 결측 유사 작은 셀만 hold-out
    missing_q95 = df.loc[~alive_mask, "store_count"].quantile(0.95)
    mimic_idx = df[alive_mask & (df["store_count"] <= missing_q95)].index.values
    rng = np.random.default_rng(42)
    shuffled = rng.permutation(mimic_idx)
    folds = np.array_split(shuffled, 5)
    wapes_m, rs_m = [], []
    for te_idx in folds:
        tr_mask = alive_mask & (~df.index.isin(te_idx))
        tr_idx = df[tr_mask].index.values
        model = model_factory()
        model.fit(X.loc[tr_idx], y_sps[tr_idx])
        pred = np.expm1(model.predict(X.loc[te_idx])) * np.maximum(store[te_idx], 1)
        m = score(actual_sales[te_idx], pred)
        wapes_m.append(m["wape"])
        rs_m.append(m["r"])

    return {
        "wape_random": np.mean(wapes_r),
        "r_random": np.mean(rs_r),
        "r2_random": np.mean(r2s_r),
        "wape_mnar": np.mean(wapes_m),
        "r_mnar": np.mean(rs_m),
    }


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────
def main():
    print("=== 모델 비교: v1/v2/v3 × 5 models ===\n")
    df = load_joined()
    print(
        f"[data] total={len(df)} alive={df['monthly_sales'].notna().sum()} missing={df['monthly_sales'].isna().sum()}\n"
    )

    models = make_models()
    results = []

    for name, factory in models.items():
        print(f"\n--- {name} ---")
        # v1
        try:
            r1 = run_v1(df, factory)
            print(f"  v1 IPF+{name:11s} WAPE={r1['wape']:5.2f}%  r={r1['r']:.3f}  R²={r1['r2']:.3f}")
        except Exception as e:
            r1 = {"wape": np.nan, "r": np.nan, "r2": np.nan}
            print(f"  v1 FAIL: {e}")
        # v2
        try:
            r2_ = run_v2(df, factory)
            print(f"  v2 {name:11s}     WAPE={r2_['wape']:5.2f}%  r={r2_['r']:.3f}  R²={r2_['r2']:.3f}")
        except Exception as e:
            r2_ = {"wape": np.nan, "r": np.nan, "r2": np.nan}
            print(f"  v2 FAIL: {e}")
        # v3
        try:
            r3 = run_v3(df, factory)
            print(f"  v3 {name:11s}     Random WAPE={r3['wape_random']:5.2f}%  MNAR={r3['wape_mnar']:5.2f}%")
        except Exception as e:
            r3 = {"wape_random": np.nan, "wape_mnar": np.nan, "r_random": np.nan, "r2_random": np.nan, "r_mnar": np.nan}
            print(f"  v3 FAIL: {e}")
        results.append(
            {
                "model": name,
                "v1_wape": r1["wape"],
                "v1_r": r1["r"],
                "v1_r2": r1["r2"],
                "v2_wape": r2_["wape"],
                "v2_r": r2_["r"],
                "v2_r2": r2_["r2"],
                "v3_rand_wape": r3["wape_random"],
                "v3_rand_r": r3["r_random"],
                "v3_rand_r2": r3["r2_random"],
                "v3_mnar_wape": r3["wape_mnar"],
                "v3_mnar_r": r3["r_mnar"],
            }
        )

    df_res = pd.DataFrame(results)
    print("\n=== 최종 비교 표 ===")
    print(df_res.round(2).to_string(index=False))

    # Markdown 저장
    lines = []
    lines.append("# 모델 교체 실험: v1/v2/v3 × 5 모델\n")
    lines.append("**목적:** GBM 외 모델들이 같은 파이프라인에서 어떤 성능을 내는지 체계적 비교\n")
    lines.append("**데이터·피처·CV 분할은 모두 동일**, 오직 **회귀 모델만 교체**.\n")
    lines.append("---\n")
    lines.append("## 결과 매트릭스 (Random 10-fold CV WAPE 기준)\n")
    lines.append("| 모델 | v1 (IPF+Model) | v2 (Model 단독) | v3 Random | **v3 MNAR (정직)** |")
    lines.append("|:----|------:|------:|------:|------:|")
    for r in results:
        lines.append(
            f"| **{r['model']}** | {r['v1_wape']:.2f}% | {r['v2_wape']:.2f}% | {r['v3_rand_wape']:.2f}% | **{r['v3_mnar_wape']:.2f}%** |"
        )

    lines.append("\n## Pearson r 비교\n")
    lines.append("| 모델 | v1 r | v2 r | v3 Random r | v3 MNAR r |")
    lines.append("|:----|:--:|:--:|:--:|:--:|")
    for r in results:
        lines.append(
            f"| **{r['model']}** | {r['v1_r']:.3f} | {r['v2_r']:.3f} | {r['v3_rand_r']:.3f} | {r['v3_mnar_r']:.3f} |"
        )

    # 최고 모델 식별
    best_mnar = min(results, key=lambda x: x["v3_mnar_wape"] if not np.isnan(x["v3_mnar_wape"]) else 999)
    lines.append("\n## 결론\n")
    lines.append(f"**MNAR 기준 최고 모델: `{best_mnar['model']}` (v3 MNAR WAPE {best_mnar['v3_mnar_wape']:.2f}%)**\n")
    lines.append(
        "MNAR-Mimic WAPE가 실제 137 결측 복원 상황을 반영하므로 이 기준으로 모델을 선택하는 것이 정직합니다.\n"
    )

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[saved] {OUT_MD}")


if __name__ == "__main__":
    main()
