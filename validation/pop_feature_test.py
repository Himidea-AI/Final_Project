"""Population feature analysis for small-scale commerce improvement.

Tests:
  1. Baseline (current 26 features)
  2. + pop_per_store (유동인구/점포수)
  3. + resident_per_store (주거인구/점포수)
  4. + both ratios
  5. + pop_store_ratio + sales_per_pop (매출/유동인구)

Compare overall AND specifically for small-scale combos (bottom 25% sales+stores).
"""
import sys
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from pathlib import Path
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import MinMaxScaler
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models.lstm_forecast.data_prep import ALL_FEATURES, SALES_FEATURES, build_timeseries, load_sales_data, load_store_data
from models.lstm_forecast.model import LSTMForecaster
from validation.accuracy_metrics import mape, mae, r_squared

np.random.seed(42); torch.manual_seed(42)
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

# Small-scale combos (from previous analysis: sales bottom 25% AND stores bottom 25%)
SMALL_COMBOS = {
    ("망원2동","중식"),("염리동","패스트푸드"),("염리동","치킨"),("아현동","패스트푸드"),
    ("아현동","일식"),("아현동","치킨"),("대흥동","패스트푸드"),("성산1동","분식"),
    ("용강동","일식"),("공덕동","패스트푸드"),("성산1동","패스트푸드"),("연남동","패스트푸드"),
    ("성산2동","치킨"),("성산2동","양식"),("염리동","호프"),("대흥동","치킨"),
    ("성산1동","치킨"),("성산2동","치킨"),("용강동","패스트푸드"),("도화동","패스트푸드"),
    ("염리동","중식"),("공덕동","중식"),("공덕동","치킨"),("공덕동","제과"),("아현동","제과"),
}


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

def impute(ts):
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


def add_pop_features(df, mode="all"):
    """Add population-derived features."""
    df = df.copy()
    if mode in ("pop_per_store", "both", "all"):
        if "total_pop" in df.columns and "store_count" in df.columns:
            df["pop_per_store"] = np.where(df["store_count"] > 0,
                                           df["total_pop"] / df["store_count"], 0)
    if mode in ("res_per_store", "both", "all"):
        if "resident_pop" in df.columns and "store_count" in df.columns:
            df["resident_per_store"] = np.where(df["store_count"] > 0,
                                                df["resident_pop"] / df["store_count"], 0)
    if mode in ("sales_per_pop", "all"):
        if "monthly_sales" in df.columns and "total_pop" in df.columns:
            df["sales_per_pop"] = np.where(df["total_pop"] > 0,
                                           df["monthly_sales"] / df["total_pop"], 0)
    if mode in ("pop_density", "all"):
        if "total_pop" in df.columns and "resident_pop" in df.columns:
            df["pop_ratio"] = np.where(df["resident_pop"] > 0,
                                       df["total_pop"] / df["resident_pop"], 0)
    return df


def train_and_backtest(ts_df, feat_cols, label="test"):
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

    # Backtest with dong x ind detail
    tidx = feat_cols.index("monthly_sales") if "monthly_sales" in feat_cols else 0
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

    df_r = pd.DataFrame(results)
    if len(df_r) == 0: return None

    # Overall
    a, p = df_r["actual"].values, df_r["predicted"].values
    overall = {"mape": mape(a,p), "mae": mae(a,p), "r2": r_squared(a,p), "n": len(df_r)}

    # Small-scale combos
    small_mask = df_r.apply(lambda r: (r["dong"], r["ind"]) in SMALL_COMBOS, axis=1)
    small_df = df_r[small_mask]
    if len(small_df) > 0:
        sa, sp = small_df["actual"].values, small_df["predicted"].values
        small = {"mape": mape(sa,sp), "mae": mae(sa,sp), "r2": r_squared(sa,sp), "n": len(small_df)}
    else:
        small = {"mape": 0, "mae": 0, "r2": 0, "n": 0}

    # Large-scale (non-small)
    large_df = df_r[~small_mask]
    if len(large_df) > 0:
        la, lp = large_df["actual"].values, large_df["predicted"].values
        large = {"mape": mape(la,lp), "mae": mae(la,lp), "r2": r_squared(la,lp), "n": len(large_df)}
    else:
        large = {"mape": 0, "mae": 0, "r2": 0, "n": 0}

    return {"overall": overall, "small": small, "large": large, "n_features": len(feat_cols)}


def main():
    print("=" * 90)
    print("  Population Feature Test for Small-scale Commerce")
    print("=" * 90)

    sales = load_sales_data(dong_prefix="11440")
    stores = load_store_data(dong_prefix="11440")
    ts = build_timeseries(sales, stores)
    ts = impute(ts)
    base_fc = [c for c in ALL_FEATURES if c in ts.columns]

    experiments = {
        "1. Baseline (26feat)": (ts, base_fc),
    }

    # Add pop features
    for mode, extra_cols, desc in [
        ("pop_per_store", ["pop_per_store"], "2. + pop/store"),
        ("res_per_store", ["resident_per_store"], "3. + resident/store"),
        ("both", ["pop_per_store", "resident_per_store"], "4. + both ratios"),
        ("all", ["pop_per_store", "resident_per_store", "sales_per_pop", "pop_ratio"], "5. + all pop features"),
    ]:
        ts_ext = add_pop_features(ts.copy(), mode)
        fc_ext = base_fc + [c for c in extra_cols if c in ts_ext.columns]
        experiments[desc] = (ts_ext, fc_ext)

    # Results
    print(f"\n{'Experiment':<30} | {'Feat':>4} | {'Overall':>8} | {'Small MAPE':>11} {'Small MAE':>12} | {'Large MAPE':>11} {'Large MAE':>12} | {'Gap':>5}")
    print("-" * 120)

    results = []
    for name, (ts_data, fc) in experiments.items():
        r = train_and_backtest(ts_data, fc, name)
        if r is None:
            print(f"{name:<30} |    FAIL")
            continue

        gap = r["small"]["mape"] - r["large"]["mape"]
        results.append({"name": name, **r})
        print(f"{name:<30} | {r['n_features']:>4} | {r['overall']['mape']:>7.1f}% | "
              f"{r['small']['mape']:>10.1f}% {r['small']['mae']:>11,.0f} | "
              f"{r['large']['mape']:>10.1f}% {r['large']['mae']:>11,.0f} | {gap:>+5.1f}")

    if not results:
        return

    # Best for small-scale
    print(f"\n{'='*90}")
    print("  Analysis")
    print(f"{'='*90}")

    baseline = results[0]
    for r in results[1:]:
        small_diff = r["small"]["mape"] - baseline["small"]["mape"]
        large_diff = r["large"]["mape"] - baseline["large"]["mape"]
        overall_diff = r["overall"]["mape"] - baseline["overall"]["mape"]
        print(f"\n  {r['name']}:")
        print(f"    Overall: {overall_diff:+.1f}%p")
        print(f"    Small:   {small_diff:+.1f}%p {'(improved)' if small_diff < 0 else '(worse)'}")
        print(f"    Large:   {large_diff:+.1f}%p {'(improved)' if large_diff < 0 else '(worse)'}")


if __name__ == "__main__":
    main()
