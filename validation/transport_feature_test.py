"""Bus stop + Subway feature test for fine-tuning.

Mapo-gu transport infrastructure data (public information):
- Bus stop count per dong
- Subway station count per dong
- Bus ridership index (relative, based on stop density)

Test: add transport features to fine-tuning and compare with baseline.
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
# Mapo-gu transport data (public information / Seoul Open Data)
# ===========================================================================

# Bus stops per dong (approximate, based on Seoul bus information system)
BUS_STOPS = {
    "11440555": 18,   # 아현동 - 아현역, 이대역 인근
    "11440565": 22,   # 공덕동 - 공덕역(4노선 환승), 마포역
    "11440585": 12,   # 도화동 - 주거지역
    "11440590": 10,   # 용강동 - 소규모
    "11440600": 15,   # 대흥동 - 대흥역
    "11440610": 8,    # 염리동 - 소규모 주거
    "11440630": 11,   # 신수동 - 주거 혼합
    "11440655": 10,   # 서강동 - 서강대 인근
    "11440660": 32,   # 서교동 - 홍대입구역, 상수역
    "11440680": 25,   # 합정동 - 합정역(2,6호선)
    "11440690": 14,   # 망원1동 - 망원역
    "11440700": 12,   # 망원2동
    "11440710": 16,   # 연남동 - 홍대 북측
    "11440720": 15,   # 성산1동
    "11440730": 13,   # 성산2동
    "11440740": 35,   # 상암동 - DMC역, 월드컵경기장역
}

# Subway stations per dong
SUBWAY_STATIONS = {
    "11440555": 2,    # 아현동 - 아현역(2호선), 이대역(2호선)
    "11440565": 2,    # 공덕동 - 공덕역(5,6호선,경의,공항), 마포역(5호선)
    "11440585": 0,    # 도화동 - 역 없음
    "11440590": 0,    # 용강동 - 역 없음
    "11440600": 1,    # 대흥동 - 대흥역(6호선)
    "11440610": 0,    # 염리동 - 역 없음
    "11440630": 0,    # 신수동 - 역 없음(광흥창역 인접)
    "11440655": 0,    # 서강동 - 역 없음(서강대 인접)
    "11440660": 2,    # 서교동 - 홍대입구역(2호선,경의,공항), 상수역(6호선)
    "11440680": 1,    # 합정동 - 합정역(2,6호선)
    "11440690": 1,    # 망원1동 - 망원역(6호선)
    "11440700": 0,    # 망원2동 - 역 없음
    "11440710": 0,    # 연남동 - 역 없음(홍대입구 인접)
    "11440720": 0,    # 성산1동 - 역 없음
    "11440730": 0,    # 성산2동 - 역 없음
    "11440740": 2,    # 상암동 - DMC역(6호선,경의,공항), 월드컵경기장역(6호선)
}

# Subway transfer lines (major hub indicator)
SUBWAY_LINES = {
    "11440555": 1,    # 아현 - 2호선만
    "11440565": 4,    # 공덕 - 5,6호선,경의,공항 (4개 노선!)
    "11440585": 0,
    "11440590": 0,
    "11440600": 1,    # 대흥 - 6호선
    "11440610": 0,
    "11440630": 0,
    "11440655": 0,
    "11440660": 3,    # 서교 - 2호선,경의,공항
    "11440680": 2,    # 합정 - 2,6호선
    "11440690": 1,    # 망원 - 6호선
    "11440700": 0,
    "11440710": 0,
    "11440720": 0,
    "11440730": 0,
    "11440740": 3,    # 상암 - 6호선,경의,공항
}


# ===========================================================================
# Imputation
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
# Add transport features
# ===========================================================================

def add_transport_features(df, mode="all"):
    df = df.copy()
    dc = df["dong_code"].astype(str)

    if mode in ("bus", "bus+subway", "all"):
        df["bus_stops"] = dc.map(BUS_STOPS).fillna(0).astype(float)

    if mode in ("subway", "bus+subway", "all"):
        df["subway_stations"] = dc.map(SUBWAY_STATIONS).fillna(0).astype(float)
        df["subway_lines"] = dc.map(SUBWAY_LINES).fillna(0).astype(float)

    if mode in ("ratios", "all"):
        # Transport accessibility per store
        bus = dc.map(BUS_STOPS).fillna(0).astype(float)
        subway = dc.map(SUBWAY_STATIONS).fillna(0).astype(float)
        lines = dc.map(SUBWAY_LINES).fillna(0).astype(float)
        sc = df["store_count"].replace(0, 1)
        df["bus_per_store"] = bus / sc
        df["transport_score"] = (bus + subway * 10 + lines * 5) / sc

    return df


# ===========================================================================
# Train & Backtest
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


def main():
    t0 = time.time()
    print("=" * 80)
    print("  Transport Feature Test (Bus + Subway)")
    print("=" * 80)

    sales = load_sales_data(dong_prefix="11440")
    stores = load_store_data(dong_prefix="11440")
    ts_raw = build_timeseries(sales, stores)
    np.random.seed(42)
    ts = impute_guide(ts_raw.copy())
    ts["pop_per_store"] = np.where(ts["store_count"]>0, ts["total_pop"]/ts["store_count"], 0)
    base_fc = [c for c in ALL_FEATURES if c in ts.columns] + ["pop_per_store"]

    print(f"  Base features: {len(base_fc)}")

    # Transport data summary
    print(f"\n  Transport data (Mapo-gu):")
    for dc, dn in sorted(DONG_MAP.items(), key=lambda x: x[1]):
        print(f"    {dn:<8} bus={BUS_STOPS[dc]:>2} subway={SUBWAY_STATIONS[dc]} lines={SUBWAY_LINES[dc]}")

    # Experiments
    experiments = {
        "1. Baseline (27feat)": (ts.copy(), base_fc),
    }

    for mode, extra, desc in [
        ("bus", ["bus_stops"], "2. + bus_stops"),
        ("subway", ["subway_stations", "subway_lines"], "3. + subway"),
        ("bus+subway", ["bus_stops", "subway_stations", "subway_lines"], "4. + bus+subway"),
        ("ratios", ["bus_per_store", "transport_score"], "5. + transport ratios"),
        ("all", ["bus_stops", "subway_stations", "subway_lines", "bus_per_store", "transport_score"],
         "6. + all transport"),
    ]:
        ts_ext = add_transport_features(ts.copy(), mode)
        fc_ext = base_fc + [c for c in extra if c in ts_ext.columns]
        experiments[desc] = (ts_ext, fc_ext)

    print(f"\n{'='*80}")
    print("  Results")
    print(f"{'='*80}")
    print(f"\n  {'Experiment':<28} | {'Feat':>4} {'MAPE':>7} {'MAE':>14} {'R2':>8} | {'Q1':>6} {'Q2':>6} {'Q3':>6} {'Q4':>6}")
    print("  " + "-" * 95)

    all_results = {}
    for name, (ts_data, fc) in experiments.items():
        df_r = train_and_backtest(ts_data, fc)
        if len(df_r) == 0: continue
        a, p = df_r["actual"].values, df_r["predicted"].values
        steps = {}
        for s in range(1, N_STEPS+1):
            ds = df_r[df_r["step"]==s]
            steps[s] = mape(ds["actual"].values, ds["predicted"].values) if len(ds) > 0 else 0
        all_results[name] = df_r
        print(f"  {name:<28} | {len(fc):>4} {mape(a,p):>6.1f}% {mae(a,p):>13,.0f} {r_squared(a,p):>7.4f} | "
              f"{steps[1]:>5.1f}% {steps[2]:>5.1f}% {steps[3]:>5.1f}% {steps[4]:>5.1f}%")

    # Dong comparison for best vs baseline
    if len(all_results) >= 2:
        # Find best
        best_name = min(all_results, key=lambda k: mape(all_results[k]["actual"].values, all_results[k]["predicted"].values))
        base_name = "1. Baseline (27feat)"

        print(f"\n{'='*80}")
        print(f"  Dong: Baseline vs Best ({best_name})")
        print(f"{'='*80}")
        dong_order = sorted(DONG_MAP.values())
        print(f"  {'dong':<8} {'Baseline':>10} {'Best':>10} {'Diff':>8}")
        print("  " + "-" * 40)
        for dong in dong_order:
            g1 = all_results[base_name]; g1d = g1[g1["dong"]==dong]
            g2 = all_results[best_name]; g2d = g2[g2["dong"]==dong]
            m1 = mape(g1d["actual"].values, g1d["predicted"].values) if len(g1d) > 0 else 0
            m2 = mape(g2d["actual"].values, g2d["predicted"].values) if len(g2d) > 0 else 0
            diff = m1 - m2
            arrow = "v" if diff > 1 else "^" if diff < -1 else "="
            print(f"  {dong:<8} {m1:>9.1f}% {m2:>9.1f}% {diff:>+7.1f} {arrow}")

        # Industry comparison
        print(f"\n{'='*80}")
        print(f"  Industry: Baseline vs Best ({best_name})")
        print(f"{'='*80}")
        ind_order = ["한식","중식","일식","양식","제과","패스트푸드","치킨","분식","호프","커피"]
        print(f"  {'ind':<10} {'Baseline':>10} {'Best':>10} {'Diff':>8}")
        print("  " + "-" * 42)
        for ind in ind_order:
            g1 = all_results[base_name]; g1i = g1[g1["ind"]==ind]
            g2 = all_results[best_name]; g2i = g2[g2["ind"]==ind]
            m1 = mape(g1i["actual"].values, g1i["predicted"].values) if len(g1i) > 0 else 0
            m2 = mape(g2i["actual"].values, g2i["predicted"].values) if len(g2i) > 0 else 0
            diff = m1 - m2
            arrow = "v" if diff > 1 else "^" if diff < -1 else "="
            print(f"  {ind:<10} {m1:>9.1f}% {m2:>9.1f}% {diff:>+7.1f} {arrow}")

    elapsed = time.time() - t0
    print(f"\n  Total time: {elapsed:.0f}s ({elapsed/60:.1f}min)")


if __name__ == "__main__":
    main()
