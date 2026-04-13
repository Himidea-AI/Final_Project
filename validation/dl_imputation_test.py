"""Deep Learning Imputation Test.

Methods:
  1. Baseline: guide-density (Hot Deck) + pop_per_store
  2. Autoencoder Imputation: encode-decode missing values
  3. LSTM Imputation: temporal pattern-based reconstruction
  4. Hybrid: DL impute first, then guide-density fallback

All evaluated with optimal config (window=4, hidden=128) + pop_per_store.
"""
import sys
import time
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from pathlib import Path
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import MinMaxScaler
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models.lstm_forecast.data_prep import (
    ALL_FEATURES, SALES_FEATURES, build_timeseries, load_sales_data, load_store_data,
)
from models.lstm_forecast.model import LSTMForecaster
from validation.accuracy_metrics import mape, mae, r_squared

device = torch.device("cpu")
WINDOW, HIDDEN, N_STEPS = 4, 128, 4

DONG_MAP = {
    "11440555":"아현동","11440565":"공덕동","11440585":"도화동",
    "11440590":"용강동","11440600":"대흥동","11440610":"염리동",
    "11440630":"신수동","11440655":"서강동","11440660":"서교동",
    "11440680":"합정동","11440690":"망원1동","11440700":"망원2동",
    "11440710":"연남동","11440720":"성산1동","11440730":"성산2동",
    "11440740":"상암동",
}
IND_MAP = {
    "CS100001":"한식","CS100002":"중식","CS100003":"일식",
    "CS100004":"양식","CS100005":"제과","CS100006":"패스트푸드",
    "CS100007":"치킨","CS100008":"분식","CS100009":"호프",
    "CS100010":"커피",
}


# ===========================================================================
# 1. Autoencoder Imputation
# ===========================================================================

class ImputationAutoencoder(nn.Module):
    """Denoising Autoencoder for feature imputation."""
    def __init__(self, input_size, hidden_size=64):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
        )
        self.decoder = nn.Sequential(
            nn.Linear(hidden_size // 2, hidden_size),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_size, input_size),
        )

    def forward(self, x):
        z = self.encoder(x)
        return self.decoder(z)


def train_autoencoder(df, feat_cols, epochs=100):
    """Train autoencoder on non-missing rows, then impute missing."""
    data = df[feat_cols].values.astype(np.float32)
    scaler = MinMaxScaler()

    # Identify rows with any zero (potential missing)
    has_zero = (data == 0).any(axis=1)
    clean_data = data[~has_zero]

    if len(clean_data) < 50:
        # Not enough clean data, use all
        clean_data = data

    scaled = scaler.fit_transform(clean_data)
    tensor = torch.from_numpy(scaled)

    model = ImputationAutoencoder(len(feat_cols), hidden_size=64).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    criterion = nn.MSELoss()

    # Train with denoising: randomly mask 20% of features
    model.train()
    for ep in range(epochs):
        mask = torch.bernoulli(torch.ones_like(tensor) * 0.8)
        noisy = tensor * mask
        optimizer.zero_grad()
        recon = model(noisy)
        loss = criterion(recon, tensor)
        loss.backward()
        optimizer.step()

    # Impute: for rows with zeros, reconstruct
    model.eval()
    all_scaled = scaler.transform(data)
    all_tensor = torch.from_numpy(all_scaled.astype(np.float32))

    with torch.no_grad():
        reconstructed = model(all_tensor).numpy()

    # Inverse transform
    reconstructed = scaler.inverse_transform(reconstructed)

    # Only replace zero values
    result = data.copy()
    zero_mask = (data == 0)
    result[zero_mask] = reconstructed[zero_mask]

    return result


# ===========================================================================
# 2. LSTM Imputation
# ===========================================================================

class LSTMImputer(nn.Module):
    """Bidirectional LSTM for time-series imputation."""
    def __init__(self, input_size, hidden_size=32):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers=1,
                           batch_first=True, bidirectional=True)
        self.fc = nn.Linear(hidden_size * 2, input_size)

    def forward(self, x):
        # x: (batch, seq_len, features)
        out, _ = self.lstm(x)
        return self.fc(out)


def train_lstm_imputer(df, feat_cols, seq_len=6, epochs=80):
    """Train LSTM imputer on group time-series, then fill missing."""
    scaler = MinMaxScaler()
    all_data = df[feat_cols].values.astype(np.float32)
    scaler.fit(all_data)

    # Build sequences from groups
    sequences = []
    for _, grp in df.groupby(["dong_code", "industry_code"]):
        if len(grp) < seq_len:
            continue
        vals = scaler.transform(grp[feat_cols].values.astype(np.float32))
        for i in range(len(vals) - seq_len + 1):
            sequences.append(vals[i:i + seq_len])

    if not sequences:
        return all_data

    seqs = np.array(sequences, dtype=np.float32)
    tensor = torch.from_numpy(seqs)

    model = LSTMImputer(len(feat_cols), hidden_size=32).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    criterion = nn.MSELoss()

    # Train: mask random timesteps and reconstruct
    dl = DataLoader(TensorDataset(tensor), batch_size=32, shuffle=True)
    model.train()
    for ep in range(epochs):
        for (batch,) in dl:
            batch = batch.to(device)
            # Mask 20% of values
            mask = torch.bernoulli(torch.ones_like(batch) * 0.8)
            masked = batch * mask
            optimizer.zero_grad()
            recon = model(masked)
            loss = criterion(recon, batch)
            loss.backward()
            optimizer.step()

    # Impute: for each group, run through LSTM and fill zeros
    model.eval()
    result = all_data.copy()
    row_idx = 0

    for _, grp in df.groupby(["dong_code", "industry_code"]):
        n = len(grp)
        grp_data = scaler.transform(grp[feat_cols].values.astype(np.float32))

        if n >= seq_len:
            # Use last seq_len rows
            seq = torch.from_numpy(grp_data[-seq_len:]).unsqueeze(0).to(device)
            with torch.no_grad():
                recon = model(seq).cpu().numpy()[0]
            recon_full = scaler.inverse_transform(recon)

            # Map back: fill zeros in last seq_len rows
            grp_indices = grp.index.tolist()
            for i, gi in enumerate(grp_indices[-seq_len:]):
                pos = df.index.get_loc(gi)
                zero_mask = (result[pos] == 0)
                result[pos][zero_mask] = recon_full[i][zero_mask]

        row_idx += n

    return result


# ===========================================================================
# Guide-density imputation (baseline)
# ===========================================================================

def hot_deck(df, col, donors_f):
    r = df.copy()
    dn_col = "dong_name" if "dong_name" in df.columns else None
    if dn_col is None: return r
    for q, qdf in r.groupby("quarter"):
        miss = qdf[col].isna() | (qdf[col] == 0)
        if not miss.any(): continue
        d = qdf[~miss]; rec = qdf[miss]
        if d.empty: continue
        for idx, row in rec.iterrows():
            dn = row.get(dn_col, ""); dv = None
            for ps, pd_ in [("2동","1동")]:
                if ps in str(dn):
                    pair_name = str(dn).replace(ps, pd_)
                    pr = d[d[dn_col]==pair_name][col]
                    if not pr.empty: dv = pr.values[0]; break
            if dv is None:
                af = [f for f in donors_f if f in d.columns]
                if af:
                    nn_m = NearestNeighbors(n_neighbors=1)
                    nn_m.fit(d[af].fillna(0).values)
                    _, di = nn_m.kneighbors(row[af].fillna(0).values.reshape(1,-1).astype(float))
                    dv = d.iloc[di.flatten()[0]][col]
            if dv is not None: r.at[idx, col] = dv * np.random.normal(1, 0.02)
    return r


def impute_guide(ts):
    df = ts.copy()
    df_f = [f for f in ["total_pop","store_count"] if f in df.columns]
    gk = ["dong_code","industry_code"]
    for c in SALES_FEATURES:
        if c in df.columns: df = hot_deck(df, c, df_f)
    for c in ["store_count","franchise_count","open_count","close_count",
              "total_pop","resident_pop","avg_age","total_households"]:
        if c in df.columns:
            df[c] = df.groupby(gk)[c].transform(lambda x: x.interpolate(method="linear",limit_direction="both"))
            df[c] = df.groupby(gk)[c].transform(lambda x: x.ffill().bfill())
    if "closure_rate" in df.columns:
        df["closure_rate"] = df.groupby(gk)["closure_rate"].transform(lambda x: x.interpolate(method="linear",limit_direction="both"))
    if "rent_1f" in df.columns:
        df["rent_1f"] = df.groupby("dong_code")["rent_1f"].transform(lambda x: x.interpolate(method="linear",limit_direction="both"))
        df["rent_1f"] = df.groupby("dong_code")["rent_1f"].transform(lambda x: x.fillna(x.median()))
    if "vacancy_rate" in df.columns: df["vacancy_rate"] = df["vacancy_rate"].interpolate(method="linear",limit_direction="both")
    if "cpi_index" in df.columns: df["cpi_index"] = df["cpi_index"].ffill().bfill()
    if "trend_score" in df.columns: df["trend_score"] = df["trend_score"].fillna(0)
    feat = [c for c in ALL_FEATURES if c in df.columns]
    df[feat] = df[feat].fillna(0)
    return df


# ===========================================================================
# DL Imputation Wrappers
# ===========================================================================

def impute_autoencoder(ts_raw, feat_cols):
    """Apply autoencoder imputation then guide-density fallback."""
    df = ts_raw.copy()
    print("    Training Autoencoder...", end=" ", flush=True)
    imputed = train_autoencoder(df, feat_cols)
    for i, col in enumerate(feat_cols):
        df[col] = imputed[:, i]
    # Fallback for remaining issues
    feat = [c for c in ALL_FEATURES if c in df.columns]
    df[feat] = df[feat].fillna(0)
    print("done")
    return df


def impute_lstm(ts_raw, feat_cols):
    """Apply LSTM imputation then guide-density fallback."""
    df = ts_raw.copy()
    print("    Training LSTM Imputer...", end=" ", flush=True)
    imputed = train_lstm_imputer(df, feat_cols)
    for i, col in enumerate(feat_cols):
        df[col] = imputed[:, i]
    feat = [c for c in ALL_FEATURES if c in df.columns]
    df[feat] = df[feat].fillna(0)
    print("done")
    return df


def impute_hybrid(ts_raw, feat_cols):
    """LSTM impute first, then guide-density for remaining."""
    df = ts_raw.copy()
    # Convert feature columns to float to avoid dtype issues
    for col in feat_cols:
        df[col] = df[col].astype(float)
    print("    Training LSTM (hybrid)...", end=" ", flush=True)
    imputed = train_lstm_imputer(df, feat_cols)
    # Only replace zeros with LSTM output
    for i, col in enumerate(feat_cols):
        mask = (df[col] == 0) | df[col].isna()
        df.loc[mask, col] = imputed[mask.values, i].astype(float)
    print("done")
    # Then apply guide-density for anything still missing
    df = impute_guide(df)
    return df


# ===========================================================================
# Forecasting pipeline
# ===========================================================================

def train_and_backtest(ts_df, feat_cols):
    np.random.seed(42); torch.manual_seed(42)
    fs = MinMaxScaler(); tsc = MinMaxScaler()
    dt = ts_df[ts_df["quarter"] <= 20234]
    fs.fit(dt[feat_cols].values.astype(np.float32))
    tsc.fit(dt[["monthly_sales"]].values.astype(np.float32))
    X_l, y_l, w_l = [], [], []
    hw = "sample_weight" in dt.columns
    for _, g in dt.groupby(["dong_code","industry_code"]):
        if len(g) <= WINDOW: continue
        fv = fs.transform(g[feat_cols].values.astype(np.float32))
        tv = tsc.transform(g[["monthly_sales"]].values.astype(np.float32))
        wv = g["sample_weight"].values if hw else np.ones(len(g))
        for i in range(len(g)-WINDOW):
            X_l.append(fv[i:i+WINDOW]); y_l.append(tv[i+WINDOW]); w_l.append(float(wv[i+WINDOW]))
    X=np.array(X_l,dtype=np.float32); y=np.array(y_l,dtype=np.float32); w=np.array(w_l,dtype=np.float32)
    nv = max(1,int(len(X)*0.2))
    tr = DataLoader(TensorDataset(torch.from_numpy(X[:-nv]),torch.from_numpy(y[:-nv]),torch.from_numpy(w[:-nv])),batch_size=32,shuffle=True)
    va = DataLoader(TensorDataset(torch.from_numpy(X[-nv:]),torch.from_numpy(y[-nv:])),batch_size=32)
    model = LSTMForecaster(input_size=X.shape[2],hidden_size=HIDDEN,num_layers=2,dropout=0.2).to(device)
    opt = torch.optim.Adam(model.parameters(),lr=1e-3,weight_decay=1e-5); crit = nn.MSELoss()
    bv,bs,wt_ = float("inf"),None,0
    for ep in range(50):
        model.train()
        for xb,yb,wb in tr:
            opt.zero_grad(); loss=(wb.unsqueeze(1)*(model(xb)-yb)**2).mean()
            loss.backward(); nn.utils.clip_grad_norm_(model.parameters(),1.0); opt.step()
        model.eval()
        with torch.no_grad():
            vl = sum(crit(model(xb),yb).item() for xb,yb in va)/max(len(va),1)
        if vl < bv: bv=vl; bs={k:v.cpu().clone() for k,v in model.state_dict().items()}; wt_=0
        else:
            wt_+=1
            if wt_>=10: break
    model.load_state_dict(bs); model.eval()

    tidx = feat_cols.index("monthly_sales")
    test_q = [20241,20242,20243,20244]
    results = []
    for (dc,ic), g in ts_df.groupby(["dong_code","industry_code"]):
        g = g.sort_values("quarter")
        tqs = [q for q in g["quarter"].values if q in test_q]
        if len(tqs) < N_STEPS: continue
        fi = g[g["quarter"]==tqs[0]].index[0]; fp = g.index.get_loc(fi)
        if fp < WINDOW: continue
        wd = g.iloc[fp-WINDOW:fp]
        fv = fs.transform(wd[feat_cols].values.astype(np.float32))
        seq = torch.from_numpy(fv).unsqueeze(0)
        dn = DONG_MAP.get(str(dc),str(dc)); ind = IND_MAP.get(str(ic),str(ic))
        for step, q in enumerate(tqs[:N_STEPS]):
            with torch.no_grad(): ps = model(seq).cpu().numpy()
            pl = tsc.inverse_transform(ps)[0][0]; al = g.iloc[fp+step]["monthly_sales"]
            results.append({"dong":dn,"ind":ind,"step":step+1,
                           "actual":np.expm1(al),"predicted":max(0,np.expm1(pl))})
            ns = seq[0,-1,:].clone(); ns[tidx]=float(ps[0][0])
            seq = torch.cat([seq[:,1:,:],ns.unsqueeze(0).unsqueeze(0)],dim=1)
    return pd.DataFrame(results)


def evaluate(df_r, label):
    if df_r is None or len(df_r) == 0:
        return None

    a, p = df_r["actual"].values, df_r["predicted"].values
    overall = {"mape": mape(a,p), "mae": mae(a,p), "r2": r_squared(a,p)}

    # Dong averages
    dong_avgs = {}
    for dong, g in df_r.groupby("dong"):
        da, dp = g["actual"].values, g["predicted"].values
        dong_avgs[dong] = mape(da, dp)

    # Industry averages
    ind_avgs = {}
    for ind, g in df_r.groupby("ind"):
        ia, ip = g["actual"].values, g["predicted"].values
        ind_avgs[ind] = mape(ia, ip)

    # Step-wise
    steps = {}
    for s in range(1, N_STEPS+1):
        ds = df_r[df_r["step"]==s]
        if len(ds) > 0:
            steps[f"Q{s}"] = mape(ds["actual"].values, ds["predicted"].values)

    return {"overall": overall, "dong": dong_avgs, "ind": ind_avgs, "steps": steps}


# ===========================================================================
# Main
# ===========================================================================

def main():
    t0 = time.time()
    print("=" * 80)
    print("  Deep Learning Imputation Comparison")
    print("=" * 80)

    sales = load_sales_data(dong_prefix="11440")
    stores = load_store_data(dong_prefix="11440")
    ts_raw = build_timeseries(sales, stores)
    base_fc = [c for c in ALL_FEATURES if c in ts_raw.columns]

    # Prepare datasets with different imputation methods
    experiments = {}

    # 1. Baseline: guide-density
    print("\n  [1] Guide-density (baseline)")
    np.random.seed(42)
    ts1 = impute_guide(ts_raw.copy())
    ts1["pop_per_store"] = np.where(ts1["store_count"]>0, ts1["total_pop"]/ts1["store_count"], 0)
    experiments["1. Guide-density"] = ts1

    # 2. Autoencoder
    print("  [2] Autoencoder Imputation")
    np.random.seed(42); torch.manual_seed(42)
    ts2 = impute_autoencoder(ts_raw.copy(), base_fc)
    ts2["pop_per_store"] = np.where(ts2["store_count"]>0, ts2["total_pop"]/ts2["store_count"], 0)
    experiments["2. Autoencoder"] = ts2

    # 3. LSTM Imputation
    print("  [3] LSTM Imputation")
    np.random.seed(42); torch.manual_seed(42)
    ts3 = impute_lstm(ts_raw.copy(), base_fc)
    ts3["pop_per_store"] = np.where(ts3["store_count"]>0, ts3["total_pop"]/ts3["store_count"], 0)
    experiments["3. LSTM Imputer"] = ts3

    # 4. Hybrid: LSTM + guide-density
    print("  [4] Hybrid (LSTM + Guide-density)")
    np.random.seed(42); torch.manual_seed(42)
    ts4 = impute_hybrid(ts_raw.copy(), base_fc)
    ts4["pop_per_store"] = np.where(ts4["store_count"]>0, ts4["total_pop"]/ts4["store_count"], 0)
    experiments["4. Hybrid"] = ts4

    # Run forecasting for each
    fc = base_fc + ["pop_per_store"]
    all_results = {}

    print(f"\n{'='*80}")
    print("  Forecasting & Evaluation")
    print(f"{'='*80}")

    for name, ts_df in experiments.items():
        print(f"\n  Training {name}...")
        np.random.seed(42); torch.manual_seed(42)
        df_r = train_and_backtest(ts_df, fc)
        ev = evaluate(df_r, name)
        all_results[name] = ev

    # === Overall comparison ===
    print(f"\n{'='*80}")
    print("  Overall Comparison")
    print(f"{'='*80}")
    print(f"  {'Method':<25} {'MAPE':>7} {'MAE':>14} {'R2':>8} | {'Q1':>6} {'Q2':>6} {'Q3':>6} {'Q4':>6}")
    print("  " + "-" * 85)
    for name, ev in all_results.items():
        if ev is None: continue
        o = ev["overall"]
        s = ev["steps"]
        print(f"  {name:<25} {o['mape']:>6.1f}% {o['mae']:>13,.0f} {o['r2']:>7.4f} | "
              f"{s.get('Q1',0):>5.1f}% {s.get('Q2',0):>5.1f}% {s.get('Q3',0):>5.1f}% {s.get('Q4',0):>5.1f}%")

    # === Dong comparison ===
    print(f"\n{'='*80}")
    print("  Dong MAPE Comparison")
    print(f"{'='*80}")
    dong_order = sorted(DONG_MAP.values())
    header = f"  {'동':<8}"
    for name in all_results:
        short = name.split(". ")[1][:10]
        header += f" {short:>10}"
    print(header)
    print("  " + "-" * (8 + 11 * len(all_results)))

    for dong in dong_order:
        line = f"  {dong:<8}"
        for name, ev in all_results.items():
            if ev and dong in ev["dong"]:
                line += f" {ev['dong'][dong]:>9.1f}%"
            else:
                line += f" {'N/A':>10}"
        print(line)

    # === Industry comparison ===
    print(f"\n{'='*80}")
    print("  Industry MAPE Comparison")
    print(f"{'='*80}")
    ind_order = ["한식","중식","일식","양식","제과","패스트푸드","치킨","분식","호프","커피"]
    header = f"  {'업종':<10}"
    for name in all_results:
        short = name.split(". ")[1][:10]
        header += f" {short:>10}"
    print(header)
    print("  " + "-" * (10 + 11 * len(all_results)))

    for ind in ind_order:
        line = f"  {ind:<10}"
        for name, ev in all_results.items():
            if ev and ind in ev["ind"]:
                line += f" {ev['ind'][ind]:>9.1f}%"
            else:
                line += f" {'N/A':>10}"
        print(line)

    elapsed = time.time() - t0
    print(f"\n  Total time: {elapsed:.0f}s ({elapsed/60:.1f}min)")


if __name__ == "__main__":
    main()
