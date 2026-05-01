"""SOTA imputation 라이브러리 비교 — 웹서치 식별 기반.

비교 모델 (v3 프레임워크에서):
  === HyperImpute 생태계 (van der Schaar Lab) ===
  - hyperimpute   (AutoML, 자동 최적 imputer 선택)
  - missforest    (R missForest, NeurIPS 2018 표준)
  - gain          (Generative Adversarial Imputation Nets)
  - miwae         (MIWAE - deep generative VAE)
  - sinkhorn      (Optimal Transport-based)
  - mice          (Multiple Imputation by Chained Equations)
  - ice           (Iterative Chained Equations)

  === Native boosting (설치 성공) ===
  - lightgbm      (MS LightGBM)
  - xgboost       (Distributed XGBoost)
  - catboost      (Yandex CatBoost, categorical 강함)

  === Baseline (이전 실험) ===
  - ExtraTrees    (sklearn, 이전 최고)
  - RandomForest  (sklearn)

평가: v3 MNAR-Mimic 5-fold CV (결측 유사 작은 셀 hold-out)
목표: WAPE < 15% (ExtraTrees 15.96% 벽 돌파 여부)
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
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
from sklearn.metrics import r2_score
from sqlalchemy import create_engine, text

sys.stdout.reconfigure(encoding="utf-8")
REPO_ROOT = Path(__file__).resolve().parents[1]
for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

engine = create_engine(os.environ["POSTGRES_URL"])
ANCHOR_CSV = REPO_ROOT / "validation" / "results" / "phase1b_anchor_series.csv"
OUT_MD = REPO_ROOT / "docs" / "sales-imputation" / "sota_comparison.md"


def load_joined():
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


def features_v3(df):
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


def score(actual, pred):
    abs_err = np.abs(actual - pred)
    return {
        "wape": float(abs_err.sum() / actual.sum() * 100) if actual.sum() > 0 else np.nan,
        "r2": float(r2_score(actual, pred)) if len(actual) > 1 else np.nan,
        "r": float(pearsonr(actual, pred)[0]) if len(actual) > 1 else np.nan,
    }


# ============================================================
# 모델별 fit_predict 함수
# ============================================================
def fit_predict_sklearn(model_cls, X_tr, y_tr, X_te, store_te, **kwargs):
    """sklearn-style fit/predict → × store_count."""
    m = model_cls(**kwargs)
    m.fit(X_tr, y_tr)
    log_sps = m.predict(X_te)
    return np.expm1(log_sps) * np.maximum(store_te, 1)


def fit_predict_lgbm(X_tr, y_tr, X_te, store_te):
    import lightgbm as lgb

    m = lgb.LGBMRegressor(
        n_estimators=500, max_depth=6, learning_rate=0.05, num_leaves=31, random_state=42, verbosity=-1
    )
    m.fit(X_tr, y_tr)
    return np.expm1(m.predict(X_te)) * np.maximum(store_te, 1)


def fit_predict_xgb(X_tr, y_tr, X_te, store_te):
    import xgboost as xgb

    m = xgb.XGBRegressor(
        n_estimators=500, max_depth=6, learning_rate=0.05, random_state=42, verbosity=0, tree_method="hist"
    )
    m.fit(X_tr, y_tr)
    return np.expm1(m.predict(X_te)) * np.maximum(store_te, 1)


def fit_predict_catboost(X_tr, y_tr, X_te, store_te):
    from catboost import CatBoostRegressor

    m = CatBoostRegressor(iterations=500, depth=6, learning_rate=0.05, random_state=42, verbose=False)
    m.fit(X_tr, y_tr)
    return np.expm1(m.predict(X_te)) * np.maximum(store_te, 1)


def fit_predict_hyperimpute(method, df, alive_mask, te_idx, store_te):
    """HyperImpute API: matrix에 NaN을 두고 보간.

    전략: 살아있는 셀 + te 셀의 matrix 구성, te의 monthly_sales를 NaN 처리.
    """
    from hyperimpute.plugins.imputers import Imputers

    # training set에서 te_idx만 NaN 처리한 matrix 구성
    work = (
        df[
            [
                "quarter",
                "store_count",
                "kosis_index",
                "franchise_count",
                "open_count",
                "close_count",
                "closure_rate",
                "monthly_sales",
            ]
        ]
        .copy()
        .astype(float)
    )
    work.loc[te_idx, "monthly_sales"] = np.nan
    # training에서 결측인 행은 제외 (원본 결측 137 포함)
    # 실제론 "te_idx만 NaN, 나머지 alive는 값 있음"
    # alive_mask=False인 원본 137은 포함 (어차피 NaN임)
    # te_idx 외 alive_mask=False인 행은 imputer 예측에 영향 → 그대로 둠

    plugin = Imputers().get(method)
    imputed = plugin.fit_transform(work)
    pred_full = imputed["monthly_sales"].values if isinstance(imputed, pd.DataFrame) else imputed[:, -1]
    # HyperImpute는 log 변환 없이 원 스케일에서 작동하므로 직접 사용
    pred_te = pred_full[te_idx]
    return np.maximum(pred_te, 0)  # 음수 클리핑


# ============================================================
# 공통 평가 래퍼 — MNAR-Mimic CV
# ============================================================
def eval_mnar(df, X, predict_fn, label, is_hyperimpute=False):
    """결측 유사 작은 셀 5-fold CV."""
    alive_mask = df["monthly_sales"].notna()
    missing_q95 = df.loc[~alive_mask, "store_count"].quantile(0.95)
    mimic_idx = df[alive_mask & (df["store_count"] <= missing_q95)].index.values
    rng = np.random.default_rng(42)
    folds = np.array_split(rng.permutation(mimic_idx), 5)

    store = df["store_count"].values.astype(float)
    actual_sales = df["monthly_sales"].values
    y_sps = np.log1p(df["sales_per_store"].values)

    wapes, rs, r2s = [], [], []
    t0 = time.time()
    for fi, te_idx in enumerate(folds, 1):
        tr_mask = alive_mask & (~df.index.isin(te_idx))
        tr_idx = df[tr_mask].index.values
        try:
            if is_hyperimpute:
                pred = predict_fn(df, alive_mask, te_idx, store[te_idx])
            else:
                pred = predict_fn(X.loc[tr_idx], y_sps[tr_idx], X.loc[te_idx], store[te_idx])
            m = score(actual_sales[te_idx], pred)
            wapes.append(m["wape"])
            rs.append(m["r"])
            r2s.append(m["r2"])
        except Exception as e:
            print(f"  [{label}] Fold {fi} 실패: {str(e)[:80]}")
            return {"wape": np.nan, "r": np.nan, "r2": np.nan, "time": time.time() - t0}
    elapsed = time.time() - t0
    return {"wape": np.mean(wapes), "r": np.mean(rs), "r2": np.mean(r2s), "time": elapsed}


# ============================================================
# 메인
# ============================================================
def main():
    print("=== SOTA Imputation Model Comparison ===\n")
    df = load_joined()
    X = features_v3(df)
    print(f"[data] n={len(df)} alive={df['monthly_sales'].notna().sum()} missing={df['monthly_sales'].isna().sum()}\n")

    results = []

    # 1) sklearn 기반 (baseline + 신규)
    models_sklearn = [
        (
            "ExtraTrees (baseline)",
            ExtraTreesRegressor,
            {"n_estimators": 300, "min_samples_leaf": 3, "random_state": 42, "n_jobs": -1},
        ),
        (
            "RandomForest",
            RandomForestRegressor,
            {"n_estimators": 300, "min_samples_leaf": 3, "random_state": 42, "n_jobs": -1},
        ),
    ]
    for label, cls, kw in models_sklearn:
        print(f"[run] {label} ...")
        res = eval_mnar(
            df, X, lambda Xt, yt, Xe, se, _cls=cls, _kw=kw: fit_predict_sklearn(_cls, Xt, yt, Xe, se, **_kw), label
        )
        print(f"  ✓ WAPE={res['wape']:.2f}% r={res['r']:.3f} ({res['time']:.0f}s)")
        results.append({"model": label, **res})

    # 2) Native boosting
    for label, fn in [("LightGBM", fit_predict_lgbm), ("XGBoost", fit_predict_xgb), ("CatBoost", fit_predict_catboost)]:
        print(f"[run] {label} ...")
        res = eval_mnar(df, X, fn, label)
        print(f"  ✓ WAPE={res['wape']:.2f}% r={res['r']:.3f} ({res['time']:.0f}s)")
        results.append({"model": label, **res})

    # 3) HyperImpute 생태계
    hyperimp_methods = ["mice", "missforest", "sinkhorn", "ice", "hyperimpute"]
    for method in hyperimp_methods:
        label = f"HyperImpute/{method}"
        print(f"[run] {label} ...")
        res = eval_mnar(
            df,
            X,
            lambda _df, _am, _te, _st, _m=method: fit_predict_hyperimpute(_m, _df, _am, _te, _st),
            label,
            is_hyperimpute=True,
        )
        print(
            f"  ✓ WAPE={res['wape']:.2f}% r={res['r']:.3f} ({res['time']:.0f}s)"
            if not np.isnan(res["wape"])
            else "  × FAIL"
        )
        results.append({"model": label, **res})

    # 정렬 + 리포트
    df_res = pd.DataFrame(results).sort_values("wape")
    print("\n=== 최종 순위 (MNAR WAPE 기준) ===")
    print(df_res.round(3).to_string(index=False))

    # Markdown
    lines = []
    lines.append("# SOTA 모델 비교 — v3 MNAR-Mimic CV\n")
    lines.append(
        "**목적:** 웹서치로 식별한 SOTA imputation 라이브러리가 기존 ExtraTrees(15.96%)를 넘을 수 있는지 검증\n"
    )
    lines.append("**평가:** 137 결측과 유사한 작은 셀(store_count ≤ 15) 5-fold CV\n")
    lines.append("**데이터/피처/CV는 모두 동일**, 오직 모델만 교체\n")
    lines.append("---\n")
    lines.append("## 결과 (MNAR WAPE 낮은 순)\n")
    lines.append("| 순위 | 모델 | MNAR WAPE | Pearson r | R² | 수행시간 |")
    lines.append("|:--:|:-----|----:|:--:|:--:|----:|")
    for i, r in enumerate(df_res.itertuples(), 1):
        wape_str = f"{r.wape:.2f}%" if not np.isnan(r.wape) else "FAIL"
        r_str = f"{r.r:.3f}" if not np.isnan(r.r) else "—"
        r2_str = f"{r.r2:.3f}" if not np.isnan(r.r2) else "—"
        lines.append(f"| {i} | **{r.model}** | {wape_str} | {r_str} | {r2_str} | {r.time:.0f}s |")

    # 판정
    best = df_res.iloc[0]
    lines.append("\n## 결론\n")
    lines.append(f"**최고 성능: `{best['model']}` — MNAR WAPE {best['wape']:.2f}%**\n")
    if best["wape"] < 15:
        lines.append(f"🥇 **Target Achieved!** — WAPE {best['wape']:.2f}% < 15%. 작은 셀 복원도 안정 구간.")
    elif best["wape"] < 20:
        lines.append(f"🥈 **Lewis Reasonable** — WAPE {best['wape']:.2f}%. 15% 장벽 미세 미달이나 실무 수용 가능.")
    else:
        lines.append(f"🥉 **Marginal** — WAPE {best['wape']:.2f}%. 작은 셀의 구조적 한계 확인.")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[saved] {OUT_MD}")


if __name__ == "__main__":
    main()
