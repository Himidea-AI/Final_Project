"""VIF Feature Selection + Scaler Comparison Test.

Tests:
  1. VIF analysis: identify and remove multicollinear features
  2. Scaler comparison: MinMaxScaler vs StandardScaler
  3. Combine: VIF-filtered features + best scaler

Base config: guide-density imputation, window=4, hidden=128
"""

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from statsmodels.stats.outliers_influence import variance_inflation_factor
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.lstm_forecast.data_prep import (
    ALL_FEATURES,
    SALES_FEATURES,
    build_timeseries,
    load_sales_data,
    load_store_data,
)
from models.lstm_forecast.model import LSTMForecaster
from validation.accuracy_metrics import mae, mape, r_squared, rmse

np.random.seed(42)
torch.manual_seed(42)
device = torch.device("cpu")

WINDOW = 4
HIDDEN = 128
N_STEPS = 4
DONG_NAME_PAIR = {"mangwon2": "mangwon1", "seongsan2": "seongsan1"}
DONG_MAP = {
    "11440555": "mangwon2", "11440565": "gongdeok", "11440585": "dohwa",
    "11440590": "yonggang", "11440600": "daeheung", "11440610": "yeomri",
    "11440630": "sinsu", "11440655": "seogang", "11440660": "seogyo",
    "11440680": "hapjeong", "11440690": "mangwon1", "11440700": "mangwon2",
    "11440710": "yeonnam", "11440720": "seongsan1", "11440730": "seongsan2",
    "11440740": "sangam",
}
KR_DONG_NAME_PAIR = {"mangwon2dong": "mangwon1dong", "seongsan2dong": "seongsan1dong"}


# ===========================================================================
# Imputation (guide-density)
# ===========================================================================

def hot_deck(df, col, donors_f):
    r = df.copy()
    dn_col = "dong_name" if "dong_name" in df.columns else None
    if dn_col is None:
        return r
    pair_map = {"mangwon2dong": "mangwon1dong", "seongsan2dong": "seongsan1dong"}
    for q, qdf in r.groupby("quarter"):
        miss = qdf[col].isna() | (qdf[col] == 0)
        if not miss.any():
            continue
        d = qdf[~miss]
        rec = qdf[miss]
        if d.empty:
            continue
        for idx, row in rec.iterrows():
            dn = row.get(dn_col, "")
            dv = None
            # Try known pairs by dong_name content
            for pair_src, pair_dst in [("mangwon2", "mangwon1"), ("seongsan2", "seongsan1")]:
                if pair_src in str(dn).lower().replace(" ", ""):
                    pair_rows = d[d[dn_col].str.contains(pair_dst.replace("dong", ""), case=False, na=False)]
                    if not pair_rows.empty:
                        dv = pair_rows[col].values[0]
                        break
            if dv is None:
                af = [f for f in donors_f if f in d.columns]
                if af:
                    nn_m = NearestNeighbors(n_neighbors=1)
                    nn_m.fit(d[af].fillna(0).values)
                    _, di = nn_m.kneighbors(row[af].fillna(0).values.reshape(1, -1).astype(float))
                    dv = d.iloc[di.flatten()[0]][col]
            if dv is not None:
                r.at[idx, col] = dv * np.random.normal(1, 0.02)
    return r


def impute(ts):
    df = ts.copy()
    df_f = [f for f in ["total_pop", "store_count"] if f in df.columns]
    gk = ["dong_code", "industry_code"]
    for c in SALES_FEATURES:
        if c in df.columns:
            df = hot_deck(df, c, df_f)
    for c in ["store_count", "franchise_count", "open_count", "close_count",
              "total_pop", "resident_pop", "avg_age", "total_households"]:
        if c in df.columns:
            df[c] = df.groupby(gk)[c].transform(
                lambda x: x.interpolate(method="linear", limit_direction="both"))
            df[c] = df.groupby(gk)[c].transform(lambda x: x.ffill().bfill())
    if "closure_rate" in df.columns:
        df["closure_rate"] = df.groupby(gk)["closure_rate"].transform(
            lambda x: x.interpolate(method="linear", limit_direction="both"))
    if "rent_1f" in df.columns:
        df["rent_1f"] = df.groupby("dong_code")["rent_1f"].transform(
            lambda x: x.interpolate(method="linear", limit_direction="both"))
        df["rent_1f"] = df.groupby("dong_code")["rent_1f"].transform(
            lambda x: x.fillna(x.median()))
    if "vacancy_rate" in df.columns:
        df["vacancy_rate"] = df["vacancy_rate"].interpolate(method="linear", limit_direction="both")
    if "cpi_index" in df.columns:
        df["cpi_index"] = df["cpi_index"].ffill().bfill()
    if "trend_score" in df.columns:
        df["trend_score"] = df["trend_score"].fillna(0)
    feat = [c for c in ALL_FEATURES if c in df.columns]
    df[feat] = df[feat].fillna(0)
    return df


# ===========================================================================
# VIF Analysis
# ===========================================================================

def compute_vif(df, feature_cols, threshold=10.0):
    """VIF >= threshold features are candidates for removal."""
    data = df[feature_cols].dropna().values.astype(np.float64)
    # Add small noise to avoid perfect collinearity
    data = data + np.random.normal(0, 1e-10, data.shape)

    vif_data = []
    for i, col in enumerate(feature_cols):
        try:
            vif_val = variance_inflation_factor(data, i)
            vif_data.append({"feature": col, "VIF": vif_val})
        except Exception:
            vif_data.append({"feature": col, "VIF": float("inf")})

    vif_df = pd.DataFrame(vif_data).sort_values("VIF", ascending=False)
    return vif_df


def iterative_vif_removal(df, feature_cols, threshold=10.0):
    """Iteratively remove highest VIF feature until all < threshold."""
    remaining = list(feature_cols)
    removed = []

    while True:
        if len(remaining) < 3:
            break
        vif_df = compute_vif(df, remaining, threshold)
        max_vif = vif_df["VIF"].max()
        if max_vif < threshold or np.isinf(max_vif):
            break
        worst = vif_df.iloc[0]["feature"]
        # Don't remove target
        if worst == "monthly_sales":
            if len(vif_df) > 1:
                worst = vif_df.iloc[1]["feature"]
            else:
                break
        removed.append(worst)
        remaining.remove(worst)

    return remaining, removed


# ===========================================================================
# Training / Backtest
# ===========================================================================

def make_sequences(ts_df, feat_cols, scaler_class=MinMaxScaler, max_quarter=None):
    df = ts_df.copy()
    if max_quarter is not None:
        df = df[df["quarter"] <= max_quarter]
    fs = scaler_class()
    tsc = scaler_class()
    fs.fit(df[feat_cols].values.astype(np.float32))
    tsc.fit(df[["monthly_sales"]].values.astype(np.float32))
    X_l, y_l, w_l = [], [], []
    hw = "sample_weight" in df.columns
    for _, g in df.groupby(["dong_code", "industry_code"]):
        if len(g) <= WINDOW:
            continue
        fv = fs.transform(g[feat_cols].values.astype(np.float32))
        tv = tsc.transform(g[["monthly_sales"]].values.astype(np.float32))
        wv = g["sample_weight"].values if hw else np.ones(len(g))
        for i in range(len(g) - WINDOW):
            X_l.append(fv[i:i + WINDOW])
            y_l.append(tv[i + WINDOW])
            w_l.append(float(wv[i + WINDOW]))
    if not X_l:
        return None, None, None, None, None
    return (np.array(X_l, dtype=np.float32), np.array(y_l, dtype=np.float32),
            fs, tsc, np.array(w_l, dtype=np.float32))


def train_and_backtest(ts_df, feat_cols, scaler_class=MinMaxScaler, label="test"):
    np.random.seed(42)
    torch.manual_seed(42)

    X, y, fs, tsc, w = make_sequences(ts_df, feat_cols, scaler_class, max_quarter=20234)
    if X is None:
        return None

    nv = max(1, int(len(X) * 0.2))
    tr = DataLoader(TensorDataset(torch.from_numpy(X[:-nv]), torch.from_numpy(y[:-nv]),
                                  torch.from_numpy(w[:-nv])), batch_size=32, shuffle=True)
    va = DataLoader(TensorDataset(torch.from_numpy(X[-nv:]), torch.from_numpy(y[-nv:])), batch_size=32)

    model = LSTMForecaster(input_size=X.shape[2], hidden_size=HIDDEN, num_layers=2, dropout=0.2).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)
    crit = nn.MSELoss()
    bv, bs, wt = float("inf"), None, 0
    for ep in range(50):
        model.train()
        for xb, yb, wb in tr:
            opt.zero_grad()
            loss = (wb.unsqueeze(1) * (model(xb) - yb) ** 2).mean()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        model.eval()
        with torch.no_grad():
            vl = sum(crit(model(xb), yb).item() for xb, yb in va) / max(len(va), 1)
        if vl < bv:
            bv = vl
            bs = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            wt = 0
        else:
            wt += 1
            if wt >= 10:
                break
    model.load_state_dict(bs)

    # Backtest
    model.eval()
    tidx = feat_cols.index("monthly_sales") if "monthly_sales" in feat_cols else 0
    results = []
    test_q = [20241, 20242, 20243, 20244]
    for (dc, ic), g in ts_df.groupby(["dong_code", "industry_code"]):
        g = g.sort_values("quarter")
        tqs = [q for q in g["quarter"].values if q in test_q]
        if len(tqs) < N_STEPS:
            continue
        fi = g[g["quarter"] == tqs[0]].index[0]
        fp = g.index.get_loc(fi)
        if fp < WINDOW:
            continue
        wd = g.iloc[fp - WINDOW:fp]
        fv = fs.transform(wd[feat_cols].values.astype(np.float32))
        seq = torch.from_numpy(fv).unsqueeze(0)
        for step, q in enumerate(tqs[:N_STEPS]):
            with torch.no_grad():
                ps = model(seq).cpu().numpy()
            pl = tsc.inverse_transform(ps)[0][0]
            al = g.iloc[fp + step]["monthly_sales"]
            results.append({"step": step + 1, "actual": np.expm1(al),
                            "predicted": max(0, np.expm1(pl))})
            ns = seq[0, -1, :].clone()
            ns[tidx] = float(ps[0][0])
            seq = torch.cat([seq[:, 1:, :], ns.unsqueeze(0).unsqueeze(0)], dim=1)

    df_r = pd.DataFrame(results)
    if len(df_r) == 0:
        return None
    a, p = df_r["actual"].values, df_r["predicted"].values
    step_mapes = []
    for s in range(1, N_STEPS + 1):
        ds = df_r[df_r["step"] == s]
        step_mapes.append(mape(ds["actual"].values, ds["predicted"].values) if len(ds) > 0 else 0)

    return {
        "mape": mape(a, p), "mae": mae(a, p), "r2": r_squared(a, p),
        "rmse_val": rmse(a, p), "n": len(df_r), "n_features": len(feat_cols),
        "q1": step_mapes[0], "q2": step_mapes[1], "q3": step_mapes[2], "q4": step_mapes[3],
    }


# ===========================================================================
# Main
# ===========================================================================

def main():
    t0 = time.time()

    print("=" * 70)
    print("  VIF Feature Selection + Scaler Comparison")
    print("=" * 70)

    # Load & impute
    sales = load_sales_data(dong_prefix="11440")
    stores = load_store_data(dong_prefix="11440")
    ts = build_timeseries(sales, stores)
    ts = impute(ts)
    all_fc = [c for c in ALL_FEATURES if c in ts.columns]
    print(f"  Total features: {len(all_fc)}")

    # === VIF Analysis ===
    print(f"\n{'='*70}")
    print("  [1] VIF Analysis")
    print(f"{'='*70}")

    vif_df = compute_vif(ts, all_fc)
    print("\n  Feature VIF values:")
    for _, row in vif_df.iterrows():
        marker = " ***" if row["VIF"] >= 10 else ""
        print(f"    {row['feature']:<25} VIF={row['VIF']:>10.1f}{marker}")

    # Iterative removal
    vif_features, removed = iterative_vif_removal(ts, all_fc, threshold=10.0)
    print(f"\n  Removed ({len(removed)}): {removed}")
    print(f"  Remaining ({len(vif_features)}): {vif_features}")

    # Also try threshold=5
    vif5_features, removed5 = iterative_vif_removal(ts, all_fc, threshold=5.0)
    print(f"\n  VIF<5 Removed ({len(removed5)}): {removed5}")
    print(f"  VIF<5 Remaining ({len(vif5_features)}): {vif5_features}")

    # === Experiments ===
    print(f"\n{'='*70}")
    print("  [2] Experiments")
    print(f"{'='*70}")

    experiments = {
        "Baseline (MinMax, 26feat)": (all_fc, MinMaxScaler),
        "Standard Scaler (26feat)": (all_fc, StandardScaler),
        "VIF<10 + MinMax": (vif_features, MinMaxScaler),
        "VIF<10 + Standard": (vif_features, StandardScaler),
        "VIF<5 + MinMax": (vif5_features, MinMaxScaler),
        "VIF<5 + Standard": (vif5_features, StandardScaler),
    }

    print(f"\n{'#':>2} {'Experiment':<30} | {'Feat':>4} {'MAPE':>7} {'MAE':>14} {'R2':>8} | {'Q1':>6} {'Q2':>6} {'Q3':>6} {'Q4':>6}")
    print("-" * 100)

    results = []
    for idx, (name, (fc, scaler)) in enumerate(experiments.items(), 1):
        r = train_and_backtest(ts, fc, scaler, name)
        if r is None:
            print(f"{idx:2d} {name:<30} |    FAIL")
            continue
        results.append({"name": name, **r})
        print(f"{idx:2d} {name:<30} | {r['n_features']:>4} {r['mape']:>6.1f}% {r['mae']:>13,.0f} {r['r2']:>7.4f} | "
              f"{r['q1']:>5.1f}% {r['q2']:>5.1f}% {r['q3']:>5.1f}% {r['q4']:>5.1f}%")

    # Ranking
    if results:
        results_df = pd.DataFrame(results).sort_values("mape")
        print(f"\n{'='*70}")
        print("  Ranking (MAPE)")
        print(f"{'='*70}")
        for rank, (_, row) in enumerate(results_df.iterrows(), 1):
            marker = " <-- BEST" if rank == 1 else ""
            print(f"  {rank}. {row['name']:<30} MAPE={row['mape']:.1f}% MAE={row['mae']:,.0f} R2={row['r2']:.4f} ({int(row['n_features'])}feat){marker}")

    elapsed = time.time() - t0
    print(f"\n  Total time: {elapsed:.0f}s ({elapsed / 60:.1f}min)")


if __name__ == "__main__":
    main()
