# validation/audit_v4.py
"""Phase 2: 4종 CV (Random/TS/MNAR/LODO/Q1) + 6 추가 지표 감사 + 합격선 판정."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
from scipy.stats import pearsonr
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.metrics import f1_score
from sklearn.model_selection import KFold

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

from validation.reverse_engineer_sales_v4 import (  # noqa: E402
    BEST_PARAMS,
    SEEDS,
    build_features_v4,
    load_joined_with_all_cols,
)

OUT_MD = REPO_ROOT / "docs" / "sales-imputation" / "audit_v4_report.md"

THRESHOLDS = {
    "random_wape": 0.12,
    "ts_wape": 0.15,
    "mnar_wape": 0.15,
    "lodo_wape": 0.30,
    "q1_wape": 0.18,
    "pearson_r": 0.97,
    "rmsle": 0.35,
    "oom_accuracy": 0.97,
    "f1_4tier": 0.85,
    "mase": 0.20,
}


def wape(actual, pred):
    return float(np.abs(actual - pred).sum() / np.maximum(actual.sum(), 1))


def rmsle(actual, pred):
    return float(np.sqrt(np.mean((np.log1p(np.maximum(pred, 0)) - np.log1p(actual)) ** 2)))


def oom_accuracy(actual, pred):
    ratio = pred / np.maximum(actual, 1)
    return float(np.mean((ratio >= 0.5) & (ratio <= 2.0)))


def f1_4tier(actual, pred):
    q = np.quantile(actual, [0.25, 0.5, 0.75])
    actual_tier = np.digitize(actual, q)
    pred_tier = np.digitize(pred, q)
    return float(f1_score(actual_tier, pred_tier, average="macro"))


def mase(actual, pred):
    naive_err = np.mean(np.abs(np.diff(actual)))
    return float(np.mean(np.abs(actual - pred)) / max(naive_err, 1))


def fit_simple(X_tr, y_tr, seed):
    return ExtraTreesRegressor(**BEST_PARAMS, random_state=seed).fit(X_tr, y_tr)


def random_kfold_wape(df, X, seeds, n_splits=10):
    alive = df["monthly_sales"].notna()
    alive_idx = df[alive].index.values
    actual_sales = df["monthly_sales"].values
    store = df["store_count"].fillna(1).values.astype(float)
    y = np.log1p((actual_sales / np.maximum(store, 1))[alive])

    wapes = []
    for seed in seeds:
        kf = KFold(n_splits=n_splits, shuffle=True, random_state=seed)
        fold_wapes = []
        for tr, te in kf.split(alive_idx):
            tr_idx = alive_idx[tr]
            te_idx = alive_idx[te]
            m = fit_simple(X.loc[tr_idx], y[tr], seed)
            log_pred = m.predict(X.loc[te_idx])
            sales_pred = np.expm1(log_pred) * np.maximum(store[te_idx], 1)
            sales_pred = np.clip(sales_pred, 0, None)
            fold_wapes.append(wape(actual_sales[te_idx], sales_pred))
        wapes.append(np.mean(fold_wapes))
    return {"mean": float(np.mean(wapes)), "std": float(np.std(wapes))}


def time_series_wape(df, X, seeds):
    alive = df["monthly_sales"].notna()
    actual_sales = df["monthly_sales"].values
    store = df["store_count"].fillna(1).values.astype(float)
    sales_per_store = actual_sales / np.maximum(store, 1)
    quarters = sorted(df.loc[alive, "quarter"].unique())

    wapes = []
    for seed in seeds:
        ts_wapes = []
        for i in range(8, len(quarters)):
            tr_q = quarters[:i]
            te_q = quarters[i]
            tr_mask = alive & df["quarter"].isin(tr_q)
            te_mask = alive & (df["quarter"] == te_q)
            if te_mask.sum() == 0:
                continue
            y_tr = np.log1p(sales_per_store[tr_mask])
            m = fit_simple(X[tr_mask], y_tr, seed)
            log_pred = m.predict(X[te_mask])
            sales_pred = np.expm1(log_pred) * np.maximum(store[te_mask], 1)
            sales_pred = np.clip(sales_pred, 0, None)
            ts_wapes.append(wape(actual_sales[te_mask], sales_pred))
        wapes.append(np.mean(ts_wapes))
    return {"mean": float(np.mean(wapes)), "std": float(np.std(wapes))}


def mnar_mimic_wape(df, X, seeds, n_folds=5):
    alive = df["monthly_sales"].notna()
    actual_sales = df["monthly_sales"].values
    store = df["store_count"].fillna(1).values.astype(float)
    sales_per_store = actual_sales / np.maximum(store, 1)
    missing_q95 = df.loc[~alive, "store_count"].quantile(0.95)
    mimic_idx = df[alive & (df["store_count"] <= missing_q95)].index.values

    wapes = []
    for seed in seeds:
        rng = np.random.default_rng(seed)
        folds = np.array_split(rng.permutation(mimic_idx), n_folds)
        fw = []
        for te_idx in folds:
            tr_mask = alive & (~df.index.isin(te_idx))
            tr_idx = df[tr_mask].index.values
            y_tr = np.log1p(sales_per_store[tr_idx])
            m = fit_simple(X.loc[tr_idx], y_tr, seed)
            log_pred = m.predict(X.loc[te_idx])
            sales_pred = np.expm1(log_pred) * np.maximum(store[te_idx], 1)
            sales_pred = np.clip(sales_pred, 0, None)
            fw.append(wape(actual_sales[te_idx], sales_pred))
        wapes.append(np.mean(fw))
    return {"mean": float(np.mean(wapes)), "std": float(np.std(wapes))}


def lodo_wape(df, X, seeds):
    alive = df["monthly_sales"].notna()
    actual_sales = df["monthly_sales"].values
    store = df["store_count"].fillna(1).values.astype(float)
    sales_per_store = actual_sales / np.maximum(store, 1)

    wapes = []
    for seed in seeds:
        lodo_wapes = []
        for dong in sorted(df["dong_code"].unique()):
            tr_mask = alive & (df["dong_code"] != dong)
            te_mask = alive & (df["dong_code"] == dong)
            if te_mask.sum() == 0:
                continue
            y_tr = np.log1p(sales_per_store[tr_mask])
            m = fit_simple(X[tr_mask], y_tr, seed)
            log_pred = m.predict(X[te_mask])
            sales_pred = np.expm1(log_pred) * np.maximum(store[te_mask], 1)
            sales_pred = np.clip(sales_pred, 0, None)
            lodo_wapes.append(wape(actual_sales[te_mask], sales_pred))
        wapes.append(np.mean(lodo_wapes))
    return {"mean": float(np.mean(wapes)), "std": float(np.std(wapes))}


def q1_wape(df, X, seeds):
    """Q1 (작은 셀) — store_count 분위 1만."""
    alive = df["monthly_sales"].notna()
    q25 = df.loc[alive, "store_count"].quantile(0.25)
    q1_mask = alive & (df["store_count"] <= q25)
    actual_sales = df["monthly_sales"].values
    store = df["store_count"].fillna(1).values.astype(float)
    sales_per_store = actual_sales / np.maximum(store, 1)

    wapes = []
    for seed in seeds:
        kf = KFold(5, shuffle=True, random_state=seed)
        q1_idx = df[q1_mask].index.values
        fw = []
        for _tr, te in kf.split(q1_idx):
            te_idx = q1_idx[te]
            tr_mask_full = alive & (~df.index.isin(te_idx))
            tr_idx_full = df[tr_mask_full].index.values
            y_tr = np.log1p(sales_per_store[tr_idx_full])
            m = fit_simple(X.loc[tr_idx_full], y_tr, seed)
            log_pred = m.predict(X.loc[te_idx])
            sales_pred = np.expm1(log_pred) * np.maximum(store[te_idx], 1)
            sales_pred = np.clip(sales_pred, 0, None)
            fw.append(wape(actual_sales[te_idx], sales_pred))
        wapes.append(np.mean(fw))
    return {"mean": float(np.mean(wapes)), "std": float(np.std(wapes))}


def diagnose_failure(audit):
    diags = []
    if not audit.get("mnar_wape", {}).get("pass", True):
        v = audit["mnar_wape"]["mean"] * 100
        diags.append(f"MNAR WAPE {v:.1f}% > 15%: 결측 복원 신뢰성 부족. → confidence 일괄 0.10 하향")
    if not audit.get("lodo_wape", {}).get("pass", True):
        v = audit["lodo_wape"]["mean"] * 100
        diags.append(f"LODO WAPE {v:.1f}% > 30%: dong fixed effect 의존 잔존. → dong_avg LOO 재적용")
    if not audit.get("pearson_r", {}).get("pass", True):
        v = audit["pearson_r"]["value"]
        diags.append(f"Pearson r {v:.3f} < 0.97: 순위 보존 부족. → 외삽 셀 confidence 강화")
    return diags


def main():
    print("=== Phase 2: Audit v4 ===")
    df = load_joined_with_all_cols()
    X = build_features_v4(df)
    print(f"[data] alive={df['monthly_sales'].notna().sum()} features={X.shape[1]}")

    audits = {}

    print("[1/5] Random 10-fold ...")
    audits["random_wape"] = random_kfold_wape(df, X, SEEDS)
    audits["random_wape"]["pass"] = audits["random_wape"]["mean"] <= THRESHOLDS["random_wape"]

    print("[2/5] Time-Series CV ...")
    audits["ts_wape"] = time_series_wape(df, X, SEEDS)
    audits["ts_wape"]["pass"] = audits["ts_wape"]["mean"] <= THRESHOLDS["ts_wape"]

    print("[3/5] MNAR-Mimic ...")
    audits["mnar_wape"] = mnar_mimic_wape(df, X, SEEDS)
    audits["mnar_wape"]["pass"] = audits["mnar_wape"]["mean"] <= THRESHOLDS["mnar_wape"]

    print("[4/5] LODO ...")
    audits["lodo_wape"] = lodo_wape(df, X, SEEDS)
    audits["lodo_wape"]["pass"] = audits["lodo_wape"]["mean"] <= THRESHOLDS["lodo_wape"]

    print("[5/5] Q1 (작은 셀) ...")
    audits["q1_wape"] = q1_wape(df, X, SEEDS)
    audits["q1_wape"]["pass"] = audits["q1_wape"]["mean"] <= THRESHOLDS["q1_wape"]

    # 추가 지표 (random fold 의 OOF 예측으로)
    alive = df["monthly_sales"].notna()
    alive_idx = df[alive].index.values
    actual_sales = df["monthly_sales"].values
    store = df["store_count"].fillna(1).values.astype(float)
    sales_per_store = actual_sales / np.maximum(store, 1)
    preds_full = np.zeros(len(df))
    kf = KFold(10, shuffle=True, random_state=42)
    for tr, te in kf.split(alive_idx):
        tr_idx = alive_idx[tr]
        te_idx = alive_idx[te]
        y_tr = np.log1p(sales_per_store[tr_idx])
        m = fit_simple(X.loc[tr_idx], y_tr, 42)
        log_pred = m.predict(X.loc[te_idx])
        preds_full[te_idx] = np.expm1(log_pred) * np.maximum(store[te_idx], 1)
    preds_full = np.clip(preds_full, 0, None)
    actual_alive = actual_sales[alive]
    pred_alive = preds_full[alive]

    audits["pearson_r"] = {"value": float(pearsonr(actual_alive, pred_alive)[0])}
    audits["pearson_r"]["pass"] = audits["pearson_r"]["value"] >= THRESHOLDS["pearson_r"]
    audits["rmsle"] = {"value": rmsle(actual_alive, pred_alive)}
    audits["rmsle"]["pass"] = audits["rmsle"]["value"] <= THRESHOLDS["rmsle"]
    audits["oom_accuracy"] = {"value": oom_accuracy(actual_alive, pred_alive)}
    audits["oom_accuracy"]["pass"] = audits["oom_accuracy"]["value"] >= THRESHOLDS["oom_accuracy"]
    audits["f1_4tier"] = {"value": f1_4tier(actual_alive, pred_alive)}
    audits["f1_4tier"]["pass"] = audits["f1_4tier"]["value"] >= THRESHOLDS["f1_4tier"]
    audits["mase"] = {"value": mase(actual_alive, pred_alive)}
    audits["mase"]["pass"] = audits["mase"]["value"] <= THRESHOLDS["mase"]

    audits["all_pass"] = all(a.get("pass", False) for k, a in audits.items() if k != "all_pass")
    audits["diagnoses"] = diagnose_failure(audits)

    # MD 보고서
    lines = ["# Audit v4 Report\n"]
    lines.append(f"**production_ready:** {audits['all_pass']}\n")
    lines.append("| 지표 | 값 | 합격선 | 통과 |")
    lines.append("|:---|---:|---:|:---:|")
    for k in ["random_wape", "ts_wape", "mnar_wape", "lodo_wape", "q1_wape"]:
        v = audits[k]["mean"] * 100
        lines.append(f"| {k} | {v:.2f}% | ≤ {THRESHOLDS[k] * 100:.0f}% | {'✅' if audits[k]['pass'] else '❌'} |")
    for k in ["pearson_r", "rmsle", "oom_accuracy", "f1_4tier", "mase"]:
        v = audits[k]["value"]
        op = "≥" if k in ("pearson_r", "oom_accuracy", "f1_4tier") else "≤"
        lines.append(f"| {k} | {v:.4f} | {op} {THRESHOLDS[k]} | {'✅' if audits[k]['pass'] else '❌'} |")
    if audits["diagnoses"]:
        lines.append("\n## Diagnoses\n")
        for d in audits["diagnoses"]:
            lines.append(f"- {d}")
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"[saved] {OUT_MD}")
    print(f"\n[종합] production_ready = {audits['all_pass']}")


if __name__ == "__main__":
    main()
