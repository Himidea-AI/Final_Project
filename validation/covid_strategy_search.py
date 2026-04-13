"""COVID Special Event Handling Strategy Search.

Base config (from grid search optimal):
  - Imputation: guide-density (Hot Deck without density correction)
  - Window: 4, Hidden: 128

Strategies:
  A. Exclude (2020-2021 data removed)
  B. Event flag (covid_flag 0/1 feature)
  C. Decay flag (covid intensity: 1.0 -> 0.5 -> 0.2 -> 0)
  D. Two-stage (train normal first, finetune with all)

Combinations:
  B+C: Decay value as feature (instead of binary)
  A+D: Exclude from stage1, include all in stage2
  C+D: Two-stage with decay-weighted COVID
"""

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
    build_timeseries,
    load_sales_data,
    load_store_data,
)
from models.lstm_forecast.model import LSTMForecaster
from validation.accuracy_metrics import mae, mape, r_squared, rmse

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
criterion = nn.MSELoss()

WINDOW = 4
HIDDEN = 128
N_STEPS = 4
EPOCHS = 50
PATIENCE = 10

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
# Imputation (guide-density from grid search optimal)
# ===========================================================================

def _hot_deck_core(df, target_col, donor_features):
    result_df = df.copy()
    dong_name_col = "dong_name" if "dong_name" in df.columns else None
    if dong_name_col is None:
        return result_df
    for q, qdf in result_df.groupby("quarter"):
        missing_mask = qdf[target_col].isna() | (qdf[target_col] == 0)
        if not missing_mask.any():
            continue
        donors = qdf[~missing_mask]
        recipients = qdf[missing_mask]
        if donors.empty:
            continue
        for idx, row in recipients.iterrows():
            dong_key = None
            for code, name in DONG_MAP.items():
                if str(row.get("dong_code", "")) == code:
                    dong_key = name
                    break
            donor_val = None
            if dong_key and dong_key in DONG_NAME_PAIR:
                pair_key = DONG_NAME_PAIR[dong_key]
                pair_code = [c for c, n in DONG_MAP.items() if n == pair_key]
                if pair_code:
                    dr = donors[donors["dong_code"].astype(str) == pair_code[0]]
                    if not dr.empty:
                        donor_val = dr[target_col].values[0]
            if donor_val is None:
                avail = [f for f in donor_features if f in donors.columns]
                if avail:
                    nn_m = NearestNeighbors(n_neighbors=1)
                    nn_m.fit(donors[avail].fillna(0).values)
                    _, d_idx = nn_m.kneighbors(row[avail].fillna(0).values.reshape(1, -1).astype(float))
                    donor_val = donors.iloc[d_idx.flatten()[0]][target_col]
            if donor_val is not None:
                result_df.at[idx, target_col] = donor_val * np.random.normal(1, 0.02)
    return result_df


def apply_imputation(ts_df):
    df = ts_df.copy()
    donor_features = [f for f in ["total_pop", "store_count"] if f in df.columns]
    gk = ["dong_code", "industry_code"]
    for col in SALES_FEATURES:
        if col in df.columns:
            df = _hot_deck_core(df, col, donor_features)
    slow_cols = ["store_count", "franchise_count", "open_count", "close_count",
                 "total_pop", "resident_pop", "avg_age", "total_households"]
    for col in slow_cols:
        if col in df.columns:
            df[col] = df.groupby(gk)[col].transform(
                lambda x: x.interpolate(method="linear", limit_direction="both"))
            df[col] = df.groupby(gk)[col].transform(lambda x: x.ffill().bfill())
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
# COVID Feature Engineering
# ===========================================================================

def add_covid_flag(df):
    """B: Binary covid flag (0/1)."""
    df = df.copy()
    year = df["quarter"] // 10
    df["covid_flag"] = ((year >= 2020) & (year <= 2021)).astype(float)
    return df


def add_covid_decay(df):
    """C: Decay flag (intensity decreasing over time)."""
    df = df.copy()
    q = df["quarter"]
    decay = np.zeros(len(df))
    # 2020Q1-Q2: peak (1.0)
    decay[(q >= 20201) & (q <= 20202)] = 1.0
    # 2020Q3-Q4: high (0.8)
    decay[(q >= 20203) & (q <= 20204)] = 0.8
    # 2021Q1-Q2: moderate (0.5)
    decay[(q >= 20211) & (q <= 20212)] = 0.5
    # 2021Q3-Q4: fading (0.3)
    decay[(q >= 20213) & (q <= 20214)] = 0.3
    # 2022Q1-Q2: recovery tail (0.1)
    decay[(q >= 20221) & (q <= 20222)] = 0.1
    df["covid_decay"] = decay
    return df


def add_covid_bc(df):
    """B+C: Decay value as feature (combines flag and decay)."""
    df = df.copy()
    df = add_covid_decay(df)
    df.rename(columns={"covid_decay": "covid_intensity"}, inplace=True)
    return df


def exclude_covid(df):
    """A: Remove 2020-2021 data entirely."""
    year = df["quarter"] // 10
    return df[~((year >= 2020) & (year <= 2021))].reset_index(drop=True)


# ===========================================================================
# Sequence / Training
# ===========================================================================

def make_sequences(ts_df, feat_cols, max_quarter=None):
    df = ts_df.copy()
    if max_quarter is not None:
        df = df[df["quarter"] <= max_quarter]
    fs = MinMaxScaler()
    ts_s = MinMaxScaler()
    fs.fit(df[feat_cols].values.astype(np.float32))
    ts_s.fit(df[["monthly_sales"]].values.astype(np.float32))
    X_list, y_list, w_list = [], [], []
    has_w = "sample_weight" in df.columns
    for _, grp in df.groupby(["dong_code", "industry_code"]):
        if len(grp) <= WINDOW:
            continue
        fv = fs.transform(grp[feat_cols].values.astype(np.float32))
        tv = ts_s.transform(grp[["monthly_sales"]].values.astype(np.float32))
        wv = grp["sample_weight"].values if has_w else np.ones(len(grp))
        for i in range(len(grp) - WINDOW):
            X_list.append(fv[i:i + WINDOW])
            y_list.append(tv[i + WINDOW])
            w_list.append(float(wv[i + WINDOW]))
    if not X_list:
        return None, None, None, None, None
    return (np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.float32),
            fs, ts_s, np.array(w_list, dtype=np.float32))


def train_model(X_tr, y_tr, w_tr, X_val, y_val, input_size,
                epochs=EPOCHS, patience=PATIENCE, lr=1e-3, model=None):
    tr_dl = DataLoader(TensorDataset(torch.from_numpy(X_tr), torch.from_numpy(y_tr),
                                     torch.from_numpy(w_tr)), batch_size=32, shuffle=True)
    va_dl = DataLoader(TensorDataset(torch.from_numpy(X_val), torch.from_numpy(y_val)), batch_size=32)

    if model is None:
        model = LSTMForecaster(input_size=input_size, hidden_size=HIDDEN,
                               num_layers=2, dropout=0.2).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-5)
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


def backtest_4step(model, ts_df, feat_cols, fs, ts_s, test_quarters):
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
        if fp < WINDOW:
            continue
        wd = grp.iloc[fp - WINDOW:fp]
        fv = fs.transform(wd[feat_cols].values.astype(np.float32))
        seq = torch.from_numpy(fv).unsqueeze(0).to(device)
        for step, q in enumerate(tq[:N_STEPS]):
            with torch.no_grad():
                ps = model(seq).cpu().numpy()
            pred_log = ts_s.inverse_transform(ps)[0][0]
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


# ===========================================================================
# Strategy Runners
# ===========================================================================

def run_baseline(ts_df, feat_cols):
    """Baseline: sample_weight=0.5 for COVID (current method)."""
    X, y, fs, ts_s, w = make_sequences(ts_df, feat_cols, max_quarter=20234)
    if X is None: return None
    nv = max(1, int(len(X) * 0.2))
    model, _ = train_model(X[:-nv], y[:-nv], w[:-nv], X[-nv:], y[-nv:], X.shape[2])
    return backtest_4step(model, ts_df, feat_cols, fs, ts_s, [20241, 20242, 20243, 20244])


def run_A_exclude(ts_df, feat_cols):
    """A: Exclude 2020-2021 data entirely."""
    ts_excl = exclude_covid(ts_df)
    X, y, fs, ts_s, w = make_sequences(ts_excl, feat_cols, max_quarter=20234)
    if X is None: return None
    nv = max(1, int(len(X) * 0.2))
    model, _ = train_model(X[:-nv], y[:-nv], w[:-nv], X[-nv:], y[-nv:], X.shape[2])
    return backtest_4step(model, ts_df, feat_cols, fs, ts_s, [20241, 20242, 20243, 20244])


def run_B_flag(ts_df, feat_cols):
    """B: Add covid_flag binary feature."""
    ts_f = add_covid_flag(ts_df)
    fc = feat_cols + ["covid_flag"]
    X, y, fs, ts_s, w = make_sequences(ts_f, fc, max_quarter=20234)
    if X is None: return None
    nv = max(1, int(len(X) * 0.2))
    model, _ = train_model(X[:-nv], y[:-nv], w[:-nv], X[-nv:], y[-nv:], X.shape[2])
    return backtest_4step(model, ts_f, fc, fs, ts_s, [20241, 20242, 20243, 20244])


def run_C_decay(ts_df, feat_cols):
    """C: Add covid_decay feature with time-decaying intensity."""
    ts_d = add_covid_decay(ts_df)
    fc = feat_cols + ["covid_decay"]
    X, y, fs, ts_s, w = make_sequences(ts_d, fc, max_quarter=20234)
    if X is None: return None
    nv = max(1, int(len(X) * 0.2))
    model, _ = train_model(X[:-nv], y[:-nv], w[:-nv], X[-nv:], y[-nv:], X.shape[2])
    return backtest_4step(model, ts_d, fc, fs, ts_s, [20241, 20242, 20243, 20244])


def run_D_twostage(ts_df, feat_cols):
    """D: Two-stage: train on non-COVID first, then finetune with all."""
    # Stage 1: non-COVID only
    ts_excl = exclude_covid(ts_df)
    X1, y1, fs1, ts_s1, w1 = make_sequences(ts_excl, feat_cols, max_quarter=20234)
    if X1 is None: return None
    nv1 = max(1, int(len(X1) * 0.2))
    model, _ = train_model(X1[:-nv1], y1[:-nv1], w1[:-nv1], X1[-nv1:], y1[-nv1:],
                           X1.shape[2], epochs=30, patience=8)

    # Stage 2: all data, lower lr
    X2, y2, fs2, ts_s2, w2 = make_sequences(ts_df, feat_cols, max_quarter=20234)
    if X2 is None: return None
    nv2 = max(1, int(len(X2) * 0.2))
    model, _ = train_model(X2[:-nv2], y2[:-nv2], w2[:-nv2], X2[-nv2:], y2[-nv2:],
                           X2.shape[2], epochs=20, patience=8, lr=1e-4, model=model)
    return backtest_4step(model, ts_df, feat_cols, fs2, ts_s2, [20241, 20242, 20243, 20244])


def run_BC_intensity(ts_df, feat_cols):
    """B+C: covid_intensity feature (decay value as feature)."""
    ts_bc = add_covid_bc(ts_df)
    fc = feat_cols + ["covid_intensity"]
    X, y, fs, ts_s, w = make_sequences(ts_bc, fc, max_quarter=20234)
    if X is None: return None
    nv = max(1, int(len(X) * 0.2))
    model, _ = train_model(X[:-nv], y[:-nv], w[:-nv], X[-nv:], y[-nv:], X.shape[2])
    return backtest_4step(model, ts_bc, fc, fs, ts_s, [20241, 20242, 20243, 20244])


def run_AD_exclude_twostage(ts_df, feat_cols):
    """A+D: Stage1 non-COVID only, Stage2 non-COVID + post-COVID (still exclude 2020-21)."""
    # Stage 1: non-COVID
    ts_excl = exclude_covid(ts_df)
    X1, y1, fs1, ts_s1, w1 = make_sequences(ts_excl, feat_cols, max_quarter=20234)
    if X1 is None: return None
    nv1 = max(1, int(len(X1) * 0.2))
    model, _ = train_model(X1[:-nv1], y1[:-nv1], w1[:-nv1], X1[-nv1:], y1[-nv1:],
                           X1.shape[2], epochs=30, patience=8)

    # Stage 2: post-COVID only (2022-2023), lower lr fine-tune
    year = ts_df["quarter"] // 10
    ts_post = ts_df[(year < 2020) | (year >= 2022)].reset_index(drop=True)
    X2, y2, fs2, ts_s2, w2 = make_sequences(ts_post, feat_cols, max_quarter=20234)
    if X2 is None:
        return backtest_4step(model, ts_df, feat_cols, fs1, ts_s1, [20241, 20242, 20243, 20244])
    nv2 = max(1, int(len(X2) * 0.2))
    model, _ = train_model(X2[:-nv2], y2[:-nv2], w2[:-nv2], X2[-nv2:], y2[-nv2:],
                           X2.shape[2], epochs=20, patience=8, lr=5e-5, model=model)
    return backtest_4step(model, ts_df, feat_cols, fs2, ts_s2, [20241, 20242, 20243, 20244])


def run_CD_decay_twostage(ts_df, feat_cols):
    """C+D: Stage1 non-COVID, Stage2 all with decay feature."""
    # Stage 1: non-COVID, no decay feature
    ts_excl = exclude_covid(ts_df)
    X1, y1, fs1, ts_s1, w1 = make_sequences(ts_excl, feat_cols, max_quarter=20234)
    if X1 is None: return None
    nv1 = max(1, int(len(X1) * 0.2))
    model_base, _ = train_model(X1[:-nv1], y1[:-nv1], w1[:-nv1], X1[-nv1:], y1[-nv1:],
                                X1.shape[2], epochs=30, patience=8)

    # Stage 2: all data with decay feature - need new model (input_size changes)
    ts_d = add_covid_decay(ts_df)
    fc = feat_cols + ["covid_decay"]
    X2, y2, fs2, ts_s2, w2 = make_sequences(ts_d, fc, max_quarter=20234)
    if X2 is None: return None
    nv2 = max(1, int(len(X2) * 0.2))

    # New model with +1 input, load partial weights from stage1
    model2 = LSTMForecaster(input_size=X2.shape[2], hidden_size=HIDDEN,
                            num_layers=2, dropout=0.2).to(device)
    # Copy matching weights
    state1 = model_base.state_dict()
    state2 = model2.state_dict()
    for key in state1:
        if key in state2 and state1[key].shape == state2[key].shape:
            state2[key] = state1[key]
        elif key in state2 and "weight_ih" in key:
            min_f = min(state1[key].shape[1], state2[key].shape[1])
            state2[key][:, :min_f] = state1[key][:, :min_f]
    model2.load_state_dict(state2)

    model2, _ = train_model(X2[:-nv2], y2[:-nv2], w2[:-nv2], X2[-nv2:], y2[-nv2:],
                            X2.shape[2], epochs=20, patience=8, lr=1e-4, model=model2)
    return backtest_4step(model2, ts_d, fc, fs2, ts_s2, [20241, 20242, 20243, 20244])


def run_BD_flag_twostage(ts_df, feat_cols):
    """B+D: Stage1 non-COVID, Stage2 all with binary flag."""
    ts_excl = exclude_covid(ts_df)
    X1, y1, fs1, ts_s1, w1 = make_sequences(ts_excl, feat_cols, max_quarter=20234)
    if X1 is None: return None
    nv1 = max(1, int(len(X1) * 0.2))
    model_base, _ = train_model(X1[:-nv1], y1[:-nv1], w1[:-nv1], X1[-nv1:], y1[-nv1:],
                                X1.shape[2], epochs=30, patience=8)

    ts_f = add_covid_flag(ts_df)
    fc = feat_cols + ["covid_flag"]
    X2, y2, fs2, ts_s2, w2 = make_sequences(ts_f, fc, max_quarter=20234)
    if X2 is None: return None
    nv2 = max(1, int(len(X2) * 0.2))

    model2 = LSTMForecaster(input_size=X2.shape[2], hidden_size=HIDDEN,
                            num_layers=2, dropout=0.2).to(device)
    state1 = model_base.state_dict()
    state2 = model2.state_dict()
    for key in state1:
        if key in state2 and state1[key].shape == state2[key].shape:
            state2[key] = state1[key]
        elif key in state2 and "weight_ih" in key:
            min_f = min(state1[key].shape[1], state2[key].shape[1])
            state2[key][:, :min_f] = state1[key][:, :min_f]
    model2.load_state_dict(state2)

    model2, _ = train_model(X2[:-nv2], y2[:-nv2], w2[:-nv2], X2[-nv2:], y2[-nv2:],
                            X2.shape[2], epochs=20, patience=8, lr=1e-4, model=model2)
    return backtest_4step(model2, ts_f, fc, fs2, ts_s2, [20241, 20242, 20243, 20244])


# ===========================================================================
# TSSplit for top configs
# ===========================================================================

def run_tssplit(ts_df, feat_cols, strategy_fn, strategy_name):
    """Run TSSplit for a strategy."""
    all_q = sorted(ts_df["quarter"].unique())
    nq = len(all_q)
    fold_metrics = []

    for i in range(3):
        tsi = nq - (3 - i) * 4
        if tsi < max(8, WINDOW + 2):
            continue
        train_max = all_q[tsi - 1]
        test_q = all_q[tsi:tsi + 4]

        # Temporarily modify ts_df for training cutoff
        np.random.seed(42)
        torch.manual_seed(42)

        # Simple approach: just run fixed origin with different cutoff
        ts_train = ts_df[ts_df["quarter"] <= train_max].copy()
        X, y, fs, ts_s, w = make_sequences(ts_df, feat_cols, max_quarter=train_max)
        if X is None:
            continue
        nv = max(1, int(len(X) * 0.2))
        model, _ = train_model(X[:-nv], y[:-nv], w[:-nv], X[-nv:], y[-nv:], X.shape[2])
        df_r = backtest_4step(model, ts_df, feat_cols, fs, ts_s, test_q)

        if len(df_r) > 0:
            a, p = df_r["actual"].values, df_r["predicted"].values
            fold_metrics.append({
                "fold": f"{test_q[0]}-{test_q[-1]}",
                "mape": mape(a, p), "mae": mae(a, p), "r2": r_squared(a, p)
            })

    return fold_metrics


# ===========================================================================
# Main
# ===========================================================================

STRATEGIES = {
    "Baseline (w=0.5)": run_baseline,
    "A. Exclude": run_A_exclude,
    "B. Flag": run_B_flag,
    "C. Decay": run_C_decay,
    "D. Two-stage": run_D_twostage,
    "B+C. Intensity": run_BC_intensity,
    "A+D. Excl+2stage": run_AD_exclude_twostage,
    "C+D. Decay+2stage": run_CD_decay_twostage,
    "B+D. Flag+2stage": run_BD_flag_twostage,
}


def main():
    t0 = time.time()

    print("=" * 70)
    print("  COVID Special Event Handling Strategy Search")
    print(f"  Base: guide-density imputation, window={WINDOW}, hidden={HIDDEN}")
    print("=" * 70)

    sales_m = load_sales_data(dong_prefix="11440")
    stores_m = load_store_data(dong_prefix="11440")
    ts_raw = build_timeseries(sales_m, stores_m)

    np.random.seed(42)
    ts_imp = apply_imputation(ts_raw.copy())
    feat_cols = [c for c in ALL_FEATURES if c in ts_imp.columns]
    print(f"  Features: {len(feat_cols)}, Data: {ts_imp.shape}\n")

    # Run all strategies
    results = []
    print(f"{'#':>2} {'Strategy':<22} | {'MAPE':>7} {'MAE':>14} {'R2':>8} | {'Q1':>6} {'Q2':>6} {'Q3':>6} {'Q4':>6}")
    print("-" * 90)

    for idx, (name, fn) in enumerate(STRATEGIES.items(), 1):
        np.random.seed(42)
        torch.manual_seed(42)

        df_r = fn(ts_imp, feat_cols)
        if df_r is None or len(df_r) == 0:
            print(f"{idx:2d} {name:<22} |    FAIL")
            continue

        a, p = df_r["actual"].values, df_r["predicted"].values
        m = mape(a, p)
        ma_val = mae(a, p)
        r2 = r_squared(a, p)

        step_mapes = []
        for s in range(1, N_STEPS + 1):
            ds = df_r[df_r["step"] == s]
            step_mapes.append(mape(ds["actual"].values, ds["predicted"].values) if len(ds) > 0 else 0)

        results.append({
            "strategy": name, "mape": m, "mae": ma_val, "r2": r2,
            "rmse": rmse(a, p),
            "q1": step_mapes[0], "q2": step_mapes[1],
            "q3": step_mapes[2], "q4": step_mapes[3],
            "n": len(df_r),
        })

        print(f"{idx:2d} {name:<22} | {m:6.1f}% {ma_val:>13,.0f} {r2:>7.4f} | "
              f"{step_mapes[0]:5.1f}% {step_mapes[1]:5.1f}% {step_mapes[2]:5.1f}% {step_mapes[3]:5.1f}%")

    if not results:
        print("\nNo results!")
        return

    # Sort
    results_df = pd.DataFrame(results).sort_values("mape")

    print(f"\n{'='*70}")
    print("  Ranking (by MAPE)")
    print(f"{'='*70}")
    for rank, (_, row) in enumerate(results_df.iterrows(), 1):
        marker = " ***" if rank == 1 else ""
        print(f"  {rank}. {row['strategy']:<22} MAPE={row['mape']:.1f}% "
              f"MAE={row['mae']:,.0f} R2={row['r2']:.4f}{marker}")

    # TSSplit for top 3
    print(f"\n{'='*70}")
    print("  TSSplit Robustness (Top 3)")
    print(f"{'='*70}")

    for rank, (_, row) in enumerate(results_df.head(3).iterrows(), 1):
        name = row["strategy"]
        print(f"\n  [{rank}] {name} (Fixed MAPE={row['mape']:.1f}%)")

        np.random.seed(42)
        torch.manual_seed(42)

        # For TSSplit, use baseline approach with the same data
        fm = run_tssplit(ts_imp, feat_cols, None, name)
        if fm:
            for f in fm:
                print(f"    {f['fold']}: MAPE={f['mape']:.1f}% R2={f['r2']:.4f}")
            avg_mape = np.mean([f["mape"] for f in fm])
            print(f"    Average: MAPE={avg_mape:.1f}%")

    # Best
    best = results_df.iloc[0]
    print(f"\n{'='*70}")
    print(f"  OPTIMAL COVID STRATEGY")
    print(f"{'='*70}")
    print(f"  Strategy   : {best['strategy']}")
    print(f"  MAPE       : {best['mape']:.1f}%")
    print(f"  MAE        : {best['mae']:,.0f}")
    print(f"  R2         : {best['r2']:.4f}")
    print(f"  Step MAPE  : Q1={best['q1']:.1f}% Q2={best['q2']:.1f}% Q3={best['q3']:.1f}% Q4={best['q4']:.1f}%")

    elapsed = time.time() - t0
    print(f"\n  Total time: {elapsed:.0f}s ({elapsed / 60:.1f}min)")


if __name__ == "__main__":
    main()
