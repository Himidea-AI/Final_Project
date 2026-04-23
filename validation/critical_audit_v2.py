"""v2 검증의 엄격 비판: 데이터 누수·MNAR·셀 크기 편향 재검사.

네 가지 추가 검증:
  A. Time-Series CV (rolling window) — 시계열 누수 차단
  B. MNAR CV — 결측 셀과 유사한 small-store 셀만 hold-out
  C. Leave-One-Dong-Out — dong fixed effect 의존도 확인
  D. 셀 크기 별 WAPE 층화 분석

출력: docs/sales-imputation/v2_critical_audit.md
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from sklearn.ensemble import GradientBoostingRegressor
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
OUT_MD = REPO_ROOT / "docs" / "sales-imputation" / "v2_critical_audit.md"


def load_joined() -> pd.DataFrame:
    sql = text("""
        SELECT q.quarter, q.dong_code, q.dong_name,
               q.industry_code, q.industry_name,
               s.monthly_sales,
               q.store_count, q.open_count, q.close_count, q.closure_rate, q.franchise_count
        FROM store_quarterly q
        LEFT JOIN seoul_district_sales s
          ON q.quarter=s.quarter AND q.dong_code=s.dong_code AND q.industry_code=s.industry_code
        WHERE q.dong_code LIKE '11440%'
        ORDER BY q.quarter, q.dong_code, q.industry_code
    """)
    with engine.connect() as c:
        df = pd.read_sql(sql, c)
    anchor = pd.read_csv(ANCHOR_CSV).rename(columns={"qkey": "quarter", "수치값": "kosis_index"})
    anchor = anchor.groupby("quarter", as_index=False)["kosis_index"].mean()
    return df.merge(anchor[["quarter", "kosis_index"]], on="quarter", how="left")


def build_features(df: pd.DataFrame) -> pd.DataFrame:
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


def score(actual: np.ndarray, pred: np.ndarray) -> dict:
    abs_err = np.abs(actual - pred)
    wape = float(abs_err.sum() / actual.sum() * 100) if actual.sum() > 0 else np.nan
    mape = float(np.mean(abs_err / actual) * 100) if (actual > 0).all() else np.nan
    r2 = float(r2_score(actual, pred)) if len(actual) > 1 else np.nan
    try:
        r, _ = pearsonr(actual, pred)
    except Exception:
        r = np.nan
    return {"wape": wape, "mape": mape, "r2": r2, "r": float(r) if not np.isnan(r) else np.nan, "n": int(len(actual))}


def fit_gbm(X_tr, y_tr) -> GradientBoostingRegressor:
    return GradientBoostingRegressor(n_estimators=400, max_depth=4, learning_rate=0.05, random_state=42).fit(X_tr, y_tr)


# ─────────────────────────────────────────────────────────
# Audit A: Time-Series CV (forward chaining)
# ─────────────────────────────────────────────────────────
def audit_A_timeseries(df_alive: pd.DataFrame, X: pd.DataFrame) -> list[dict]:
    """분기 순서대로 한 분기씩 미래 예측 → 시계열 누수 차단."""
    print("\n=== Audit A: Time-Series CV (rolling) ===")
    results = []
    quarters = sorted(df_alive["quarter"].unique())
    # 초기 학습 최소 8분기 (2년) 확보 후 한 분기씩 전진
    for i in range(8, len(quarters)):
        train_q = quarters[:i]
        test_q = quarters[i]
        tr_mask = df_alive["quarter"].isin(train_q)
        te_mask = df_alive["quarter"] == test_q
        if te_mask.sum() == 0:
            continue
        y_tr = np.log1p(df_alive.loc[tr_mask, "monthly_sales"].values)
        gbm = fit_gbm(X[tr_mask], y_tr)
        pred = np.expm1(gbm.predict(X[te_mask]))
        actual = df_alive.loc[te_mask, "monthly_sales"].values
        m = score(actual, pred) | {"test_q": int(test_q)}
        print(f"  Train≤Q{train_q[-1]} → Test Q{test_q}: WAPE={m['wape']:5.1f}% r={m['r']:.3f} n={m['n']}")
        results.append(m)
    return results


# ─────────────────────────────────────────────────────────
# Audit B: MNAR CV — 결측 프로파일과 유사한 셀만 hold-out
# ─────────────────────────────────────────────────────────
def audit_B_mnar(df: pd.DataFrame, df_alive: pd.DataFrame, X_full: pd.DataFrame) -> dict:
    """결측 137개 셀의 store_count 분포를 따라가는 survivor를 hold-out."""
    print("\n=== Audit B: MNAR-mimicking CV (small store bias) ===")
    missing_df = df[df["monthly_sales"].isna()].copy()
    alive_df = df[df["monthly_sales"].notna()].copy()

    miss_q = missing_df["store_count"].quantile([0.25, 0.5, 0.75, 0.95]).to_dict()
    print(f"  결측 셀 store_count 분위: {miss_q}")
    print(f"  살아있는 셀 store_count 분위: {alive_df['store_count'].quantile([0.25, 0.5, 0.75, 0.95]).to_dict()}")

    # 결측의 store_count 범위(전체의 하위 ~25%)와 유사한 survivor를 hold-out
    miss_max = float(missing_df["store_count"].quantile(0.95))
    mimic_mask = (df["monthly_sales"].notna()) & (df["store_count"] <= miss_max)
    mimic_idx = df[mimic_mask].index

    # 5-fold CV on mimic subset (나머지 살아있는 셀 + 그 중 80%로 학습)
    rng = np.random.default_rng(42)
    shuffled = rng.permutation(mimic_idx)
    folds = np.array_split(shuffled, 5)

    fold_results = []
    for fi, te_idx in enumerate(folds, 1):
        tr_mask = df["monthly_sales"].notna() & (~df.index.isin(te_idx))
        te_mask = df.index.isin(te_idx)
        y_tr = np.log1p(df.loc[tr_mask, "monthly_sales"].values)
        gbm = fit_gbm(X_full[tr_mask], y_tr)
        pred = np.expm1(gbm.predict(X_full[te_mask]))
        actual = df.loc[te_mask, "monthly_sales"].values
        m = score(actual, pred)
        fold_results.append(m)
        print(f"  Fold {fi}/5 (small cells n={m['n']}): WAPE={m['wape']:5.1f}% r={m['r']:.3f}")

    return {
        "miss_store_max_q95": miss_max,
        "n_mimic_alive": int(mimic_mask.sum()),
        "fold_results": fold_results,
        "mean_wape": float(np.mean([f["wape"] for f in fold_results])),
        "mean_r": float(np.nanmean([f["r"] for f in fold_results])),
    }


# ─────────────────────────────────────────────────────────
# Audit C: Leave-One-Dong-Out (dong_fe 의존도 검사)
# ─────────────────────────────────────────────────────────
def audit_C_lodo(df: pd.DataFrame, df_alive: pd.DataFrame, X_full: pd.DataFrame) -> list[dict]:
    """각 동 전체를 제거하고 그 동을 예측 → fixed effect 학습 여부 확인."""
    print("\n=== Audit C: Leave-One-Dong-Out CV ===")
    results = []
    for dong in sorted(df["dong_code"].unique()):
        tr_mask = (df["dong_code"] != dong) & df["monthly_sales"].notna()
        te_mask = (df["dong_code"] == dong) & df["monthly_sales"].notna()
        if te_mask.sum() == 0:
            continue
        y_tr = np.log1p(df.loc[tr_mask, "monthly_sales"].values)
        gbm = fit_gbm(X_full[tr_mask], y_tr)
        pred = np.expm1(gbm.predict(X_full[te_mask]))
        actual = df.loc[te_mask, "monthly_sales"].values
        m = score(actual, pred) | {"dong": dong, "dong_name": str(df.loc[te_mask, "dong_name"].iloc[0])}
        print(f"  Leave-out {m['dong_name']:8s}: WAPE={m['wape']:5.1f}% r={m['r']:.3f} n={m['n']}")
        results.append(m)
    return results


# ─────────────────────────────────────────────────────────
# Audit D: 셀 크기별 WAPE 층화
# ─────────────────────────────────────────────────────────
def audit_D_size_strata(df: pd.DataFrame, X_full: pd.DataFrame) -> dict:
    """store_count 4분위 별 WAPE (GBM, 10-fold random CV)."""
    print("\n=== Audit D: 셀 크기 층화 WAPE ===")
    from sklearn.model_selection import KFold

    alive_idx = df[df["monthly_sales"].notna()].index
    kf = KFold(n_splits=10, shuffle=True, random_state=42)
    preds = np.zeros(len(df))
    actuals = df["monthly_sales"].values.astype(float)
    alive_arr = np.array(alive_idx)

    for tr_pos, te_pos in kf.split(alive_arr):
        tr_idx = alive_arr[tr_pos]
        te_idx = alive_arr[te_pos]
        y_tr = np.log1p(actuals[tr_idx])
        gbm = fit_gbm(X_full.loc[tr_idx], y_tr)
        preds[te_idx] = np.expm1(gbm.predict(X_full.loc[te_idx]))

    out = df.loc[alive_idx, ["store_count"]].copy()
    out["actual"] = actuals[alive_idx]
    out["pred"] = preds[alive_idx]
    out["abs_err"] = np.abs(out["actual"] - out["pred"])

    q = out["store_count"].quantile([0.25, 0.5, 0.75]).tolist()

    def bucket(x):
        if x <= q[0]:
            return "Q1 (작음)"
        if x <= q[1]:
            return "Q2"
        if x <= q[2]:
            return "Q3"
        return "Q4 (큼)"

    out["bucket"] = out["store_count"].apply(bucket)

    agg = (
        out.groupby("bucket")
        .apply(
            lambda g: pd.Series(
                {
                    "n": len(g),
                    "wape": g["abs_err"].sum() / g["actual"].sum() * 100 if g["actual"].sum() > 0 else np.nan,
                    "mean_store": g["store_count"].mean(),
                    "mean_actual": g["actual"].mean(),
                }
            )
        )
        .reset_index()
    )
    for _, r in agg.iterrows():
        print(
            f"  {r['bucket']:10s} n={int(r['n']):4d}  mean_store={r['mean_store']:6.1f}  mean_actual={r['mean_actual'] / 1e8:5.2f}억  WAPE={r['wape']:5.1f}%"
        )
    return {"q": q, "agg": agg.to_dict("records")}


# ─────────────────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────────────────
def write_report(a, b, c, d, default_wape: float = 14.30) -> None:
    lines = []
    lines.append("# v2 검증의 엄격 비판 · 재검사 리포트\n")
    lines.append("**기존 v2 결과:** WAPE 14.30% (random 10-fold CV) — 멘토 조언 반영 후 리버스 엔지니어링으로 달성.\n")
    lines.append("**본 문서 목적:** 그 검증이 **과대평가**가 아닌지 4가지 관점에서 비판적으로 재실험.\n")
    lines.append("---\n")

    # A
    lines.append("## A. Time-Series CV (시계열 누수 차단)\n")
    lines.append(
        '**문제의식:** random K-fold은 같은 연도의 Q1이 train, Q2가 test에 갈 수 있음 → 모델이 "그 해의 평균"을 학습해 미래를 예측한 척할 수 있음.\n'
    )
    lines.append("**방법:** 첫 8분기(2019Q1~2020Q4) 학습 → 한 분기씩 rolling-forward 예측.\n")
    if a:
        lines.append(f"**결과 ({len(a)}개 fold):**")
        lines.append("| Test Quarter | WAPE | Pearson r | n |")
        lines.append("|:-----------:|----:|---:|--:|")
        for f in a:
            lines.append(f"| {f['test_q']} | {f['wape']:.1f}% | {f['r']:.3f} | {f['n']} |")
        mean_w = np.mean([f["wape"] for f in a])
        lines.append(f"\n**평균 WAPE: {mean_w:.2f}%** (vs 랜덤 CV {default_wape}%)")
        delta = mean_w - default_wape
        if abs(delta) < 2:
            lines.append(f"→ **차이 {delta:+.1f}%p — 시계열 누수 없음 확인** ✅\n")
        elif delta > 5:
            lines.append(f"→ **차이 {delta:+.1f}%p — 랜덤 CV가 누수로 과소평가되고 있었음** ⚠️\n")
        else:
            lines.append(f"→ 차이 {delta:+.1f}%p — 약한 누수 존재, 실무적으론 수용 가능\n")

    # B
    lines.append("## B. MNAR-Mimicking CV (결측 프로파일 층화)\n")
    lines.append(
        '**문제의식:** 137개 결측은 "품질 게이트"로 필터링된 **작은 셀**에 집중. random CV는 모든 크기에서 뽑으니 결측 복원 정확도를 **과대평가**할 수 있음.\n'
    )
    lines.append(
        f"**방법:** 결측 셀의 store_count 95%ile = {b['miss_store_max_q95']:.0f} 이하의 survivor만 hold-out 대상으로 5-fold CV.\n"
    )
    lines.append(f"- 결측과 유사한 survivor 수: {b['n_mimic_alive']:,}")
    lines.append("| Fold | WAPE | Pearson r | n |")
    lines.append("|:--:|----:|---:|--:|")
    for i, f in enumerate(b["fold_results"], 1):
        lines.append(f"| {i} | {f['wape']:.1f}% | {f['r']:.3f} | {f['n']} |")
    lines.append(f"\n**평균 WAPE (결측 유사 셀): {b['mean_wape']:.2f}%** (vs 전체 랜덤 {default_wape}%)")
    delta_b = b["mean_wape"] - default_wape
    if delta_b > 10:
        lines.append(
            f"→ **+{delta_b:.1f}%p — 결측 셀은 예측이 훨씬 어려움**. 실제 137개 복원 정확도는 전체 평균보다 나쁠 가능성 큼 ⚠️\n"
        )
    elif delta_b > 3:
        lines.append(f"→ **+{delta_b:.1f}%p — 일부 저하 있음**, 복원값은 이 수준 신뢰도로 해석 필요 ⚠️\n")
    else:
        lines.append(f"→ {delta_b:+.1f}%p — 크기 편향 미미, 복원 신뢰도 유지 ✅\n")

    # C
    lines.append("## C. Leave-One-Dong-Out (동 고정효과 의존도)\n")
    lines.append(
        '**문제의식:** 16개 동 dummy 변수로 GBM이 "각 동의 평균 매출"을 외울 수 있음. 한 동 전체를 제거하면 예측 능력이 급락할 수 있음.\n'
    )
    lines.append("**결과 (16개 동):**")
    lines.append("| 동 | WAPE | Pearson r | n |")
    lines.append("|:----|----:|---:|--:|")
    if c:
        for f in sorted(c, key=lambda x: x["wape"]):
            lines.append(f"| {f['dong_name']} | {f['wape']:.1f}% | {f['r']:.3f} | {f['n']} |")
        mean_c = np.mean([f["wape"] for f in c])
        lines.append(f"\n**평균 WAPE: {mean_c:.2f}%** (vs 랜덤 CV {default_wape}%)")
        delta_c = mean_c - default_wape
        if delta_c > 15:
            lines.append(
                f"→ **+{delta_c:.1f}%p — dong fixed effect에 과도 의존**. 사업체수·KOSIS 지수의 일반화 능력 부족 ⚠️\n"
            )
        elif delta_c > 5:
            lines.append(f"→ **+{delta_c:.1f}%p — 일부 의존 있음**, 하지만 anchor가 큰 역할 ✅\n")
        else:
            lines.append(f"→ {delta_c:+.1f}%p — 동 의존 거의 없음, 일반화 우수 ✅\n")

    # D
    lines.append("## D. 셀 크기별 WAPE 층화\n")
    lines.append("**문제의식:** 평균 WAPE 14.3%가 작은 셀에도 성립하는가? 큰 셀이 평균을 끌어내릴 수 있음.\n")
    lines.append(
        f"**분위 경계 (store_count):** Q1≤{d['q'][0]:.0f}, Q2≤{d['q'][1]:.0f}, Q3≤{d['q'][2]:.0f}, Q4>{d['q'][2]:.0f}\n"
    )
    lines.append("| 크기 분위 | n | 평균 사업체수 | 평균 매출(억) | WAPE |")
    lines.append("|:---------|--:|------------:|-----------:|----:|")
    for r in d["agg"]:
        lines.append(
            f"| {r['bucket']} | {int(r['n'])} | {r['mean_store']:.1f} | {r['mean_actual'] / 1e8:.2f} | {r['wape']:.1f}% |"
        )
    wapes = [r["wape"] for r in d["agg"]]
    q1_wape = wapes[0] if len(wapes) > 0 else np.nan
    lines.append(
        f"\n→ **가장 작은 셀(Q1) WAPE: {q1_wape:.1f}%** ({'target 미달' if q1_wape > 15 else 'target 달성'})\n"
    )

    # 종합 판정
    lines.append("---\n## 종합 판정\n")
    a_wape = np.mean([f["wape"] for f in a]) if a else np.nan
    lines.append("| 검증 | WAPE | vs 원본 14.3% | 판정 |")
    lines.append("|:----|----:|----:|:----|")
    lines.append("| 원본 (random 10-fold) | 14.30% | — | 🥇 |")
    lines.append(
        f"| A. Time-Series CV | {a_wape:.2f}% | {a_wape - default_wape:+.2f}%p | {'✅' if abs(a_wape - default_wape) < 3 else '⚠️'} |"
    )
    lines.append(
        f"| B. MNAR-Mimic | {b['mean_wape']:.2f}% | {b['mean_wape'] - default_wape:+.2f}%p | {'✅' if b['mean_wape'] < 20 else '⚠️'} |"
    )
    c_wape = np.mean([f["wape"] for f in c]) if c else np.nan
    lines.append(
        f"| C. Leave-One-Dong-Out | {c_wape:.2f}% | {c_wape - default_wape:+.2f}%p | {'✅' if c_wape < 20 else '⚠️'} |"
    )
    lines.append(
        f"| D. 작은 셀 (Q1) | {q1_wape:.2f}% | {q1_wape - default_wape:+.2f}%p | {'✅' if q1_wape < 20 else '⚠️'} |"
    )

    lines.append("\n### 결론 해석")
    lines.append("- **A가 +3%p 이내**면: 시계열 누수 없음. 원본 14.3% 신뢰 가능.")
    lines.append("- **B가 원본보다 크게 높음**: 결측 복원 실제 정확도는 CV 평균보다 낮음 → confidence 하향 조정 필요.")
    lines.append("- **C가 원본보다 크게 높음**: dong fixed effect memoization 존재 → SEMAS 등 외부 피처 필요.")
    lines.append("- **D Q1이 20% 초과**: 작은 셀 예측 한계. 결측 (작은 셀 위주)의 복원값은 ±20%로 해석.")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[saved] {OUT_MD}")


if __name__ == "__main__":
    print("=== v2 Critical Audit ===")
    df = load_joined()
    X = build_features(df)
    alive = df[df["monthly_sales"].notna()].reset_index(drop=True)
    X_alive = X.loc[df["monthly_sales"].notna()].reset_index(drop=True)
    print(f"[data] total={len(df)} alive={len(alive)} missing={df['monthly_sales'].isna().sum()}")

    a = audit_A_timeseries(alive, X_alive)
    b = audit_B_mnar(df, alive, X)
    c = audit_C_lodo(df, alive, X)
    d = audit_D_size_strata(df, X)
    write_report(a, b, c, d)
