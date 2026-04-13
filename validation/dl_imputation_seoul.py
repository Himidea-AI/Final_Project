"""DL Imputation Test on Seoul-wide data (87,938 rows vs Mapo 3,703 rows).

Same 4 methods, but trained on Seoul full dataset then evaluated on Mapo-gu.
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
# DL Imputation Models
# ===========================================================================

class ImputationAutoencoder(nn.Module):
    def __init__(self, input_size, hidden_size=128):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Linear(hidden_size // 2, hidden_size // 4),
            nn.ReLU(),
        )
        self.decoder = nn.Sequential(
            nn.Linear(hidden_size // 4, hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_size // 2, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, input_size),
        )

    def forward(self, x):
        return self.decoder(self.encoder(x))


class LSTMImputer(nn.Module):
    def __init__(self, input_size, hidden_size=64):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers=2,
                           batch_first=True, bidirectional=True, dropout=0.2)
        self.fc = nn.Sequential(
            nn.Linear(hidden_size * 2, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, input_size),
        )

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out)


# ===========================================================================
# DL Imputation on Seoul data, apply to Mapo
# ===========================================================================

def train_ae_seoul(seoul_df, feat_cols, epochs=150):
    """Train autoencoder on Seoul-wide data."""
    data = seoul_df[feat_cols].values.astype(np.float32)
    scaler = MinMaxScaler()
    has_zero = (data == 0).any(axis=1)
    clean = data[~has_zero]
    if len(clean) < 100:
        clean = data
    print(f"    AE training data: {len(clean)} rows (Seoul clean)", flush=True)

    scaled = scaler.fit_transform(clean)
    tensor = torch.from_numpy(scaled)
    dl = DataLoader(TensorDataset(tensor), batch_size=256, shuffle=True)

    model = ImputationAutoencoder(len(feat_cols), hidden_size=128).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    criterion = nn.MSELoss()

    model.train()
    for ep in range(epochs):
        for (batch,) in dl:
            batch = batch.to(device)
            mask = torch.bernoulli(torch.ones_like(batch) * 0.8)
            noisy = batch * mask
            optimizer.zero_grad()
            recon = model(noisy)
            loss = criterion(recon, batch)
            loss.backward()
            optimizer.step()
        if (ep + 1) % 50 == 0:
            print(f"      AE epoch {ep+1}/{epochs} loss={loss.item():.6f}", flush=True)

    return model, scaler


def train_lstm_seoul(seoul_df, feat_cols, seq_len=6, epochs=100):
    """Train LSTM imputer on Seoul-wide time-series."""
    scaler = MinMaxScaler()
    all_data = seoul_df[feat_cols].values.astype(np.float32)
    scaler.fit(all_data)

    sequences = []
    for _, grp in seoul_df.groupby(["dong_code", "industry_code"]):
        if len(grp) < seq_len:
            continue
        vals = scaler.transform(grp[feat_cols].values.astype(np.float32))
        for i in range(len(vals) - seq_len + 1):
            sequences.append(vals[i:i + seq_len])

    seqs = np.array(sequences, dtype=np.float32)
    print(f"    LSTM training sequences: {len(seqs)} (Seoul)", flush=True)
    dl = DataLoader(TensorDataset(torch.from_numpy(seqs)), batch_size=128, shuffle=True)

    model = LSTMImputer(len(feat_cols), hidden_size=64).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    criterion = nn.MSELoss()

    model.train()
    for ep in range(epochs):
        for (batch,) in dl:
            batch = batch.to(device)
            mask = torch.bernoulli(torch.ones_like(batch) * 0.8)
            masked = batch * mask
            optimizer.zero_grad()
            recon = model(masked)
            loss = criterion(recon, batch)
            loss.backward()
            optimizer.step()
        if (ep + 1) % 25 == 0:
            print(f"      LSTM epoch {ep+1}/{epochs} loss={loss.item():.6f}", flush=True)

    return model, scaler


def apply_ae_to_mapo(ae_model, ae_scaler, mapo_df, feat_cols):
    """Apply Seoul-trained AE to Mapo data."""
    df = mapo_df.copy()
    data = df[feat_cols].values.astype(np.float32)
    scaled = ae_scaler.transform(data)
    tensor = torch.from_numpy(scaled)

    ae_model.eval()
    with torch.no_grad():
        recon = ae_model(tensor).numpy()
    recon = ae_scaler.inverse_transform(recon)

    result = data.copy()
    zero_mask = (data == 0)
    result[zero_mask] = recon[zero_mask]

    for i, col in enumerate(feat_cols):
        df[col] = result[:, i].astype(float)

    feat = [c for c in ALL_FEATURES if c in df.columns]
    df[feat] = df[feat].fillna(0)
    return df


def apply_lstm_to_mapo(lstm_model, lstm_scaler, mapo_df, feat_cols, seq_len=6):
    """Apply Seoul-trained LSTM to Mapo data."""
    df = mapo_df.copy()
    for col in feat_cols:
        df[col] = df[col].astype(float)
    data = df[feat_cols].values.astype(np.float32)
    result = data.copy()

    lstm_model.eval()
    for _, grp in df.groupby(["dong_code", "industry_code"]):
        n = len(grp)
        if n < seq_len:
            continue
        grp_data = lstm_scaler.transform(grp[feat_cols].values.astype(np.float32))
        seq = torch.from_numpy(grp_data[-seq_len:]).unsqueeze(0).to(device)
        with torch.no_grad():
            recon = lstm_model(seq).cpu().numpy()[0]
        recon_full = lstm_scaler.inverse_transform(recon)

        grp_indices = grp.index.tolist()
        for i, gi in enumerate(grp_indices[-seq_len:]):
            pos = df.index.get_loc(gi)
            zero_mask = (result[pos] == 0)
            result[pos][zero_mask] = recon_full[i][zero_mask]

    for i, col in enumerate(feat_cols):
        df[col] = result[:, i].astype(float)
    feat = [c for c in ALL_FEATURES if c in df.columns]
    df[feat] = df[feat].fillna(0)
    return df


# ===========================================================================
# Guide-density baseline
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
                    pn = str(dn).replace(ps, pd_)
                    pr = d[d[dn_col]==pn][col]
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
# Forecasting (on Mapo only)
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


def print_results(name, df_r):
    a, p = df_r["actual"].values, df_r["predicted"].values
    print(f"\n  {name}: MAPE={mape(a,p):.1f}% MAE={mae(a,p):,.0f} R2={r_squared(a,p):.4f}")

    # Dong
    dong_list = sorted(DONG_MAP.values())
    for dong in dong_list:
        g = df_r[df_r["dong"]==dong]
        if len(g) > 0:
            da, dp = g["actual"].values, g["predicted"].values
            print(f"    {dong:<8} {mape(da,dp):>6.1f}%", end="")
    print()

    # Industry
    ind_order = ["한식","중식","일식","양식","제과","패스트푸드","치킨","분식","호프","커피"]
    for ind in ind_order:
        g = df_r[df_r["ind"]==ind]
        if len(g) > 0:
            ia, ip = g["actual"].values, g["predicted"].values
            print(f"    {ind:<8} {mape(ia,ip):>6.1f}%", end="")
    print()


def main():
    t0 = time.time()
    print("=" * 80)
    print("  DL Imputation: Seoul-wide Training (87K rows)")
    print("=" * 80)

    # Load Seoul-wide data for DL training
    print("\n  [Loading Seoul data]")
    seoul_sales = load_sales_data(dong_prefix=None)
    seoul_stores = load_store_data(dong_prefix=None)
    # Use common features (no mapo-only features like resident_pop, trend_score)
    mapo_only = {"trend_score", "resident_pop"}
    seoul_feats = [f for f in ALL_FEATURES if f not in mapo_only]
    ts_seoul = build_timeseries(seoul_sales, seoul_stores, seoul_feats)
    feat_cols_seoul = [c for c in seoul_feats if c in ts_seoul.columns]
    print(f"  Seoul data: {ts_seoul.shape}, features: {len(feat_cols_seoul)}")

    # Load Mapo data
    print("  [Loading Mapo data]")
    mapo_sales = load_sales_data(dong_prefix="11440")
    mapo_stores = load_store_data(dong_prefix="11440")
    ts_mapo_raw = build_timeseries(mapo_sales, mapo_stores, seoul_feats)
    feat_cols_mapo = [c for c in seoul_feats if c in ts_mapo_raw.columns]
    print(f"  Mapo data: {ts_mapo_raw.shape}, features: {len(feat_cols_mapo)}")

    # Common features
    common_fc = [c for c in feat_cols_seoul if c in feat_cols_mapo]
    print(f"  Common features: {len(common_fc)}")

    # Zero counts
    seoul_zeros = (ts_seoul[common_fc] == 0).sum().sum()
    mapo_zeros = (ts_mapo_raw[common_fc] == 0).sum().sum()
    print(f"  Seoul zeros: {seoul_zeros} ({seoul_zeros/(ts_seoul.shape[0]*len(common_fc))*100:.1f}%)")
    print(f"  Mapo zeros: {mapo_zeros} ({mapo_zeros/(ts_mapo_raw.shape[0]*len(common_fc))*100:.1f}%)")

    experiments = {}

    # 1. Baseline: guide-density
    print(f"\n  [1] Guide-density baseline")
    np.random.seed(42)
    ts1 = impute_guide(ts_mapo_raw.copy())
    ts1["pop_per_store"] = np.where(ts1["store_count"]>0, ts1["total_pop"]/ts1["store_count"], 0)
    experiments["1. Guide-density"] = ts1

    # 2. Seoul AE
    print(f"\n  [2] Autoencoder (Seoul {len(ts_seoul)} rows)")
    np.random.seed(42); torch.manual_seed(42)
    ae_model, ae_scaler = train_ae_seoul(ts_seoul, common_fc, epochs=150)
    ts2 = apply_ae_to_mapo(ae_model, ae_scaler, ts_mapo_raw.copy(), common_fc)
    ts2["pop_per_store"] = np.where(ts2["store_count"]>0, ts2["total_pop"]/ts2["store_count"], 0)
    experiments["2. Seoul AE"] = ts2

    # 3. Seoul LSTM
    print(f"\n  [3] LSTM Imputer (Seoul {len(ts_seoul)} rows)")
    np.random.seed(42); torch.manual_seed(42)
    lstm_model, lstm_scaler = train_lstm_seoul(ts_seoul, common_fc, epochs=100)
    ts3 = apply_lstm_to_mapo(lstm_model, lstm_scaler, ts_mapo_raw.copy(), common_fc)
    ts3["pop_per_store"] = np.where(ts3["store_count"]>0, ts3["total_pop"]/ts3["store_count"], 0)
    experiments["3. Seoul LSTM"] = ts3

    # 4. Hybrid: Seoul LSTM + guide-density
    print(f"\n  [4] Hybrid (Seoul LSTM + Guide-density)")
    np.random.seed(42); torch.manual_seed(42)
    ts4 = apply_lstm_to_mapo(lstm_model, lstm_scaler, ts_mapo_raw.copy(), common_fc)
    ts4 = impute_guide(ts4)
    ts4["pop_per_store"] = np.where(ts4["store_count"]>0, ts4["total_pop"]/ts4["store_count"], 0)
    experiments["4. Hybrid"] = ts4

    # Forecast
    fc_final = common_fc + ["pop_per_store"]
    print(f"\n{'='*80}")
    print(f"  Forecasting (features: {len(fc_final)})")
    print(f"{'='*80}")

    all_evals = {}
    print(f"\n  {'Method':<22} | {'MAPE':>7} {'MAE':>14} {'R2':>8} | {'Q1':>6} {'Q2':>6} {'Q3':>6} {'Q4':>6}")
    print("  " + "-" * 85)

    for name, ts_df in experiments.items():
        np.random.seed(42); torch.manual_seed(42)
        df_r = train_and_backtest(ts_df, fc_final)
        if len(df_r) == 0: continue

        a, p = df_r["actual"].values, df_r["predicted"].values
        steps = {}
        for s in range(1, N_STEPS+1):
            ds = df_r[df_r["step"]==s]
            steps[s] = mape(ds["actual"].values, ds["predicted"].values) if len(ds) > 0 else 0

        all_evals[name] = df_r
        print(f"  {name:<22} | {mape(a,p):>6.1f}% {mae(a,p):>13,.0f} {r_squared(a,p):>7.4f} | "
              f"{steps[1]:>5.1f}% {steps[2]:>5.1f}% {steps[3]:>5.1f}% {steps[4]:>5.1f}%")

    # Dong comparison
    print(f"\n{'='*80}")
    print("  Dong MAPE Comparison")
    print(f"{'='*80}")
    dong_order = sorted(DONG_MAP.values())
    header = f"  {'동':<8}"
    for name in all_evals:
        short = name.split(". ")[1][:10]
        header += f" {short:>10}"
    print(header)
    print("  " + "-" * (8 + 11 * len(all_evals)))
    for dong in dong_order:
        line = f"  {dong:<8}"
        for name, df_r in all_evals.items():
            g = df_r[df_r["dong"]==dong]
            if len(g) > 0:
                line += f" {mape(g['actual'].values, g['predicted'].values):>9.1f}%"
            else:
                line += f" {'N/A':>10}"
        print(line)

    # Industry comparison
    print(f"\n{'='*80}")
    print("  Industry MAPE Comparison")
    print(f"{'='*80}")
    ind_order = ["한식","중식","일식","양식","제과","패스트푸드","치킨","분식","호프","커피"]
    header = f"  {'업종':<10}"
    for name in all_evals:
        short = name.split(". ")[1][:10]
        header += f" {short:>10}"
    print(header)
    print("  " + "-" * (10 + 11 * len(all_evals)))
    for ind in ind_order:
        line = f"  {ind:<10}"
        for name, df_r in all_evals.items():
            g = df_r[df_r["ind"]==ind]
            if len(g) > 0:
                line += f" {mape(g['actual'].values, g['predicted'].values):>9.1f}%"
            else:
                line += f" {'N/A':>10}"
        print(line)

    elapsed = time.time() - t0
    print(f"\n  Total time: {elapsed:.0f}s ({elapsed/60:.1f}min)")


if __name__ == "__main__":
    main()
