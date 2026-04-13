"""Imputation + Hyperparameter Grid Search for Optimal LSTM Config.

Search axes:
  - Imputation: 4 methods (fillna0, interpolation, feature_guide, feature_guide_no_density)
  - Window size: 4, 6, 8
  - Hidden size: 128, 256
  - Validation: Fixed Origin (primary) + TSSplit (robustness check on top-3)

Total: 4 x 3 x 2 = 24 Fixed Origin experiments + top-3 TSSplit
"""

import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import MinMaxScaler
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.lstm_forecast.data_prep import (
    ALL_FEATURES,
    SALES_FEATURES,
    STORE_FEATURES,
    POP_FEATURES,
    build_timeseries,
    load_sales_data,
    load_store_data,
)
from models.lstm_forecast.model import LSTMForecaster
from validation.accuracy_metrics import mae, mape, r_squared, rmse

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
criterion = nn.MSELoss()

N_STEPS = 4
DONG_PAIR = {"mangwon2": "mangwon1", "seongsan2": "seongsan1"}

DONG_MAP = {
    "11440555": "ahhyeon", "11440565": "gongdeok", "11440585": "dohwa",
    "11440590": "yonggang", "11440600": "daeheung", "11440610": "yeomri",
    "11440630": "sinsu", "11440655": "seogang", "11440660": "seogyo",
    "11440680": "hapjeong", "11440690": "mangwon1", "11440700": "mangwon2",
    "11440710": "yeonnam", "11440720": "seongsan1", "11440730": "seongsan2",
    "11440740": "sangam",
}
DONG_NAME_PAIR = {"mangwon2": "mangwon1", "seongsan2": "seongsan1"}


# ===========================================================================
# Imputation Methods
# ===========================================================================

def _hot_deck_core(df, target_col, donor_features, density_scale=False):
    result_df = df.copy()
    dong_name_col = "dong_name" if "dong_name" in df.columns else None
    if dong_name_col is None:
        return result_df

    # Build name map for pairing
    name_to_pair = {}
    for code, name in DONG_MAP.items():
        if name in DONG_NAME_PAIR:
            name_to_pair[name] = DONG_NAME_PAIR[name]

    has_store = "store_count" in df.columns and density_scale

    for q, qdf in result_df.groupby("quarter"):
        missing_mask = qdf[target_col].isna() | (qdf[target_col] == 0)
        if not missing_mask.any():
            continue
        donors = qdf[~missing_mask]
        recipients = qdf[missing_mask]
        if donors.empty:
            continue

        for idx, row in recipients.iterrows():
            dong_name = row.get(dong_name_col, "")
            # Map dong_name to DONG_MAP key for pairing
            dong_key = None
            for code, mapped_name in DONG_MAP.items():
                if str(row.get("dong_code", "")) == code:
                    dong_key = mapped_name
                    break

            donor_val = None
            donor_store = None

            # Explicit pairing
            if dong_key and dong_key in DONG_NAME_PAIR:
                pair_key = DONG_NAME_PAIR[dong_key]
                pair_code = [c for c, n in DONG_MAP.items() if n == pair_key]
                if pair_code:
                    donor_rows = donors[donors["dong_code"].astype(str) == pair_code[0]]
                    if not donor_rows.empty:
                        donor_val = donor_rows[target_col].values[0]
                        if has_store and "store_count" in donor_rows.columns:
                            donor_store = donor_rows["store_count"].values[0]

            # KNN fallback
            if donor_val is None:
                avail = [f for f in donor_features if f in donors.columns]
                if avail:
                    nn_model = NearestNeighbors(n_neighbors=1)
                    nn_model.fit(donors[avail].fillna(0).values)
                    _, d_idx = nn_model.kneighbors(
                        row[avail].fillna(0).values.reshape(1, -1).astype(float)
                    )
                    matched = donors.iloc[d_idx.flatten()[0]]
                    donor_val = matched[target_col]
                    if has_store:
                        donor_store = matched.get("store_count", 0)

            if donor_val is None:
                continue

            # Density correction
            if has_store and donor_store and donor_store > 0:
                recip_store = row.get("store_count", 0)
                if recip_store and recip_store > 0 and not np.isnan(recip_store):
                    donor_val = (donor_val / donor_store) * recip_store

            result_df.at[idx, target_col] = donor_val * np.random.normal(1, 0.02)

    return result_df


def impute_fillna_zero(ts_df):
    df = ts_df.copy()
    feat = [c for c in ALL_FEATURES if c in df.columns]
    df[feat] = df[feat].fillna(0)
    return df


def impute_interpolation(ts_df):
    """Group interpolation + ffill/bfill for all features. No Hot Deck."""
    df = ts_df.copy()
    group_keys = ["dong_code", "industry_code"]

    # All numeric features: group interpolation
    feat = [c for c in ALL_FEATURES if c in df.columns]
    for col in feat:
        df[col] = df.groupby(group_keys)[col].transform(
            lambda x: x.interpolate(method="linear", limit_direction="both")
        )
        df[col] = df.groupby(group_keys)[col].transform(lambda x: x.ffill().bfill())

    df[feat] = df[feat].fillna(0)
    return df


def impute_feature_guide(ts_df, density_scale=True):
    """Full feature-specific guide with Hot Deck."""
    df = ts_df.copy()
    donor_features = [f for f in ["total_pop", "store_count"] if f in df.columns]
    group_keys = ["dong_code", "industry_code"]

    # [1] Sales: Hot Deck
    for col in SALES_FEATURES:
        if col in df.columns:
            df = _hot_deck_core(df, col, donor_features, density_scale=density_scale)

    # [2] Store/Pop: interpolation + ffill
    slow_cols = ["store_count", "franchise_count", "open_count", "close_count",
                 "total_pop", "resident_pop", "avg_age", "total_households"]
    for col in slow_cols:
        if col in df.columns:
            df[col] = df.groupby(group_keys)[col].transform(
                lambda x: x.interpolate(method="linear", limit_direction="both")
            )
            df[col] = df.groupby(group_keys)[col].transform(lambda x: x.ffill().bfill())

    # [3] Closure rate: interpolation
    if "closure_rate" in df.columns:
        df["closure_rate"] = df.groupby(group_keys)["closure_rate"].transform(
            lambda x: x.interpolate(method="linear", limit_direction="both")
        )

    # [4] Rent: interpolation + dong median
    if "rent_1f" in df.columns:
        df["rent_1f"] = df.groupby("dong_code")["rent_1f"].transform(
            lambda x: x.interpolate(method="linear", limit_direction="both")
        )
        df["rent_1f"] = df.groupby("dong_code")["rent_1f"].transform(
            lambda x: x.fillna(x.median())
        )

    # [5] Vacancy: linear interpolation
    if "vacancy_rate" in df.columns:
        df["vacancy_rate"] = df["vacancy_rate"].interpolate(method="linear", limit_direction="both")

    # [6] CPI: forward fill
    if "cpi_index" in df.columns:
        df["cpi_index"] = df["cpi_index"].ffill().bfill()

    # [7] Trend: 0
    if "trend_score" in df.columns:
        df["trend_score"] = df["trend_score"].fillna(0)

    # [8] Remainder
    feat = [c for c in ALL_FEATURES if c in df.columns]
    df[feat] = df[feat].fillna(0)
    return df


def impute_feature_guide_no_density(ts_df):
    """Feature guide without density correction."""
    return impute_feature_guide(ts_df, density_scale=False)


IMPUTATION_METHODS = {
    "fillna(0)": impute_fillna_zero,
    "interpolation": impute_interpolation,
    "guide+density": impute_feature_guide,
    "guide-density": impute_feature_guide_no_density,
}


# ===========================================================================
# Sequence / Training / Backtest
# ===========================================================================

def make_sequences(ts_df, feat_cols, window, max_quarter=None):
    df = ts_df.copy()
    if max_quarter is not None:
        df = df[df["quarter"] <= max_quarter]

    fs = MinMaxScaler()
    ts = MinMaxScaler()
    feat_vals = df[feat_cols].values.astype(np.float32)
    tgt_vals = df[["monthly_sales"]].values.astype(np.float32)
    fs.fit(feat_vals)
    ts.fit(tgt_vals)

    X_list, y_list, w_list = [], [], []
    has_w = "sample_weight" in df.columns
    for _, grp in df.groupby(["dong_code", "industry_code"]):
        if len(grp) <= window:
            continue
        fv = fs.transform(grp[feat_cols].values.astype(np.float32))
        tv = ts.transform(grp[["monthly_sales"]].values.astype(np.float32))
        wv = grp["sample_weight"].values if has_w else np.ones(len(grp))
        for i in range(len(grp) - window):
            X_list.append(fv[i:i + window])
            y_list.append(tv[i + window])
            w_list.append(float(wv[i + window]))

    if not X_list:
        return None, None, None, None, None
    return (np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.float32),
            fs, ts, np.array(w_list, dtype=np.float32))


def train_model(X_tr, y_tr, w_tr, X_val, y_val, input_size, hidden, epochs=50, patience=10):
    tr_ds = TensorDataset(torch.from_numpy(X_tr), torch.from_numpy(y_tr), torch.from_numpy(w_tr))
    va_ds = TensorDataset(torch.from_numpy(X_val), torch.from_numpy(y_val))
    tr_dl = DataLoader(tr_ds, batch_size=32, shuffle=True)
    va_dl = DataLoader(va_ds, batch_size=32)

    model = LSTMForecaster(input_size=input_size, hidden_size=hidden,
                           num_layers=2, dropout=0.2).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)

    best_val, best_state, wait = float("inf"), None, 0
    for ep in range(epochs):
        model.train()
        for xb, yb, wb in tr_dl:
            xb, yb, wb = xb.to(device), yb.to(device), wb.to(device)
            opt.zero_grad()
            loss = (wb.unsqueeze(1) * (model(xb) - yb) ** 2).mean()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        model.eval()
        with torch.no_grad():
            vl = sum(criterion(model(xb.to(device)), yb.to(device)).item()
                     for xb, yb in va_dl) / max(len(va_dl), 1)
        if vl < best_val:
            best_val = vl
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            wait = 0
        else:
            wait += 1
            if wait >= patience:
                break
    model.load_state_dict(best_state)
    return model, best_val


def backtest_4step(model, ts_df, feat_cols, fs, ts_scaler, test_quarters, window):
    model.eval()
    tidx = feat_cols.index("monthly_sales") if "monthly_sales" in feat_cols else 0
    results = []
    for (dc, ic), grp in ts_df.groupby(["dong_code", "industry_code"]):
        grp = grp.sort_values("quarter")
        tq = [q for q in grp["quarter"].values if q in test_quarters]
        if len(tq) < N_STEPS:
            continue
        fi = grp[grp["quarter"] == tq[0]].index[0]
        fp = grp.index.get_loc(fi)
        if fp < window:
            continue
        wd = grp.iloc[fp - window:fp]
        fv = fs.transform(wd[feat_cols].values.astype(np.float32))
        seq = torch.from_numpy(fv).unsqueeze(0).to(device)
        for step, q in enumerate(tq[:N_STEPS]):
            with torch.no_grad():
                ps = model(seq).cpu().numpy()
            pred_log = ts_scaler.inverse_transform(ps)[0][0]
            actual_log = grp.iloc[fp + step]["monthly_sales"]
            results.append({
                "step": step + 1, "quarter": q,
                "actual": np.expm1(actual_log),
                "predicted": max(0, np.expm1(pred_log)),
            })
            ns = seq[0, -1, :].clone()
            ns[tidx] = float(ps[0][0])
            seq = torch.cat([seq[:, 1:, :], ns.unsqueeze(0).unsqueeze(0)], dim=1)
    return pd.DataFrame(results)


def run_fixed_origin(ts_df, feat_cols, window, hidden):
    X, y, fs, ts_s, w = make_sequences(ts_df, feat_cols, window, max_quarter=20234)
    if X is None:
        return None
    nv = max(1, int(len(X) * 0.2))
    model, vl = train_model(X[:-nv], y[:-nv], w[:-nv], X[-nv:], y[-nv:],
                            X.shape[2], hidden)
    test_q = [20241, 20242, 20243, 20244]
    return backtest_4step(model, ts_df, feat_cols, fs, ts_s, test_q, window)


def run_tssplit(ts_df, feat_cols, window, hidden):
    all_q = sorted(ts_df["quarter"].unique())
    nq = len(all_q)
    folds = []
    for i in range(3):
        tsi = nq - (3 - i) * 4
        if tsi < max(8, window + 2):
            continue
        folds.append({"train_max": all_q[tsi - 1], "test_q": all_q[tsi:tsi + 4]})

    fold_metrics = []
    for fold in folds:
        X, y, fs, ts_s, w = make_sequences(ts_df, feat_cols, window, max_quarter=fold["train_max"])
        if X is None:
            continue
        nv = max(1, int(len(X) * 0.2))
        model, _ = train_model(X[:-nv], y[:-nv], w[:-nv], X[-nv:], y[-nv:],
                               X.shape[2], hidden)
        df_r = backtest_4step(model, ts_df, feat_cols, fs, ts_s, fold["test_q"], window)
        if len(df_r) > 0:
            a, p = df_r["actual"].values, df_r["predicted"].values
            fold_metrics.append({"mape": mape(a, p), "mae": mae(a, p), "r2": r_squared(a, p)})

    if not fold_metrics:
        return None
    return {
        "mape_avg": np.mean([m["mape"] for m in fold_metrics]),
        "mae_avg": np.mean([m["mae"] for m in fold_metrics]),
        "r2_avg": np.mean([m["r2"] for m in fold_metrics]),
        "mape_2024": fold_metrics[-1]["mape"] if fold_metrics else None,
    }


# ===========================================================================
# Main Grid Search
# ===========================================================================

def main():
    t0 = time.time()
    np.random.seed(42)
    torch.manual_seed(42)

    print("=" * 70)
    print("  Grid Search: Imputation x Window x Hidden")
    print("=" * 70)

    # Data
    sales_m = load_sales_data(dong_prefix="11440")
    stores_m = load_store_data(dong_prefix="11440")
    ts_raw = build_timeseries(sales_m, stores_m)
    feat_cols = [c for c in ALL_FEATURES if c in ts_raw.columns]
    print(f"  Features: {len(feat_cols)}, Data: {ts_raw.shape}")

    # Prepare imputed datasets
    print("\n[Preparing imputed datasets]")
    datasets = {}
    for name, func in IMPUTATION_METHODS.items():
        np.random.seed(42)
        ds = func(ts_raw.copy())
        zeros = (ds[feat_cols] == 0).sum().sum()
        datasets[name] = ds
        print(f"  {name:20s}: Zero={zeros}")

    # Grid
    windows = [4, 6, 8]
    hiddens = [128, 256]

    total = len(IMPUTATION_METHODS) * len(windows) * len(hiddens)
    print(f"\n[Grid Search: {total} experiments]")
    print(f"{'#':>3} {'Imputation':>16} {'Win':>4} {'Hid':>4} | {'MAPE':>7} {'MAE':>14} {'R2':>8} {'val_loss':>9}")
    print("-" * 75)

    results = []
    idx = 0
    for imp_name, ts_df in datasets.items():
        for win in windows:
            for hid in hiddens:
                idx += 1
                np.random.seed(42)
                torch.manual_seed(42)

                df_r = run_fixed_origin(ts_df, feat_cols, win, hid)
                if df_r is None or len(df_r) == 0:
                    print(f"{idx:3d} {imp_name:>16} {win:>4} {hid:>4} |    FAIL")
                    continue

                a, p = df_r["actual"].values, df_r["predicted"].values
                m = mape(a, p)
                ma = mae(a, p)
                r2 = r_squared(a, p)

                # Step-wise
                step_mapes = []
                for s in range(1, N_STEPS + 1):
                    ds = df_r[df_r["step"] == s]
                    step_mapes.append(mape(ds["actual"].values, ds["predicted"].values) if len(ds) > 0 else 0)

                results.append({
                    "imputation": imp_name, "window": win, "hidden": hid,
                    "mape": m, "mae": ma, "r2": r2, "rmse": rmse(a, p),
                    "q1": step_mapes[0], "q2": step_mapes[1],
                    "q3": step_mapes[2], "q4": step_mapes[3],
                    "n": len(df_r),
                })

                print(f"{idx:3d} {imp_name:>16} {win:>4} {hid:>4} | {m:6.1f}% {ma:>13,.0f} {r2:>7.4f}")

    if not results:
        print("\nNo results!")
        return

    # Sort by MAPE
    results_df = pd.DataFrame(results).sort_values("mape")

    print(f"\n{'='*70}")
    print("  Top 10 Configurations (by MAPE)")
    print(f"{'='*70}")
    print(f"{'Rank':>4} {'Imputation':>16} {'Win':>4} {'Hid':>4} | {'MAPE':>7} {'MAE':>12} {'R2':>8} | {'Q1':>6} {'Q2':>6} {'Q3':>6} {'Q4':>6}")
    print("-" * 90)
    for i, row in results_df.head(10).iterrows():
        rank = results_df.index.get_loc(i) + 1
        print(f"{rank:4d} {row['imputation']:>16} {row['window']:>4} {row['hidden']:>4} | "
              f"{row['mape']:6.1f}% {row['mae']:>11,.0f} {row['r2']:>7.4f} | "
              f"{row['q1']:5.1f}% {row['q2']:5.1f}% {row['q3']:5.1f}% {row['q4']:5.1f}%")

    # Best by each imputation
    print(f"\n{'='*70}")
    print("  Best per Imputation Method")
    print(f"{'='*70}")
    for imp_name in IMPUTATION_METHODS:
        sub = results_df[results_df["imputation"] == imp_name]
        if len(sub) == 0:
            continue
        best = sub.iloc[0]
        print(f"  {imp_name:>16}: MAPE={best['mape']:.1f}% MAE={best['mae']:,.0f} R2={best['r2']:.4f} "
              f"(win={int(best['window'])}, hid={int(best['hidden'])})")

    # TSSplit for top 3
    print(f"\n{'='*70}")
    print("  TSSplit Robustness Check (Top 5)")
    print(f"{'='*70}")
    print(f"{'Imputation':>16} {'Win':>4} {'Hid':>4} | {'Fixed MAPE':>11} | {'TS avg':>8} {'TS 2024':>8} {'TS R2':>8}")
    print("-" * 75)

    for _, row in results_df.head(5).iterrows():
        np.random.seed(42)
        torch.manual_seed(42)
        ts_df = datasets[row["imputation"]]
        ts_result = run_tssplit(ts_df, feat_cols, int(row["window"]), int(row["hidden"]))
        if ts_result:
            print(f"{row['imputation']:>16} {int(row['window']):>4} {int(row['hidden']):>4} | "
                  f"{row['mape']:>10.1f}% | "
                  f"{ts_result['mape_avg']:>7.1f}% {ts_result['mape_2024']:>7.1f}% {ts_result['r2_avg']:>7.4f}")
        else:
            print(f"{row['imputation']:>16} {int(row['window']):>4} {int(row['hidden']):>4} | "
                  f"{row['mape']:>10.1f}% |    FAIL")

    # Overall best
    best = results_df.iloc[0]
    print(f"\n{'='*70}")
    print(f"  OPTIMAL CONFIG")
    print(f"{'='*70}")
    print(f"  Imputation : {best['imputation']}")
    print(f"  Window     : {int(best['window'])}")
    print(f"  Hidden     : {int(best['hidden'])}")
    print(f"  MAPE       : {best['mape']:.1f}%")
    print(f"  MAE        : {best['mae']:,.0f}")
    print(f"  R2         : {best['r2']:.4f}")
    print(f"  Step MAPE  : Q1={best['q1']:.1f}% Q2={best['q2']:.1f}% Q3={best['q3']:.1f}% Q4={best['q4']:.1f}%")

    elapsed = time.time() - t0
    print(f"\n  Total time: {elapsed:.0f}s ({elapsed / 60:.1f}min)")


if __name__ == "__main__":
    main()
