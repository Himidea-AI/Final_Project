"""Bus ridership feature test - real monthly boarding/alighting data.

Process:
  1. Load 89 monthly bus CSVs (2019.01 ~ 2026.03)
  2. Map bus stops to Mapo-gu dongs by station name keywords
  3. Aggregate to quarterly dong-level ridership
  4. Add as time-series feature to fine-tuning
  5. Compare with baseline
"""
import sys
import glob
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

# Bus stop name -> dong code mapping (keyword-based)
STATION_DONG_MAP = {
    # 아현동 (11440555)
    "아현": "11440555", "이대": "11440555", "이대역": "11440555",
    # 공덕동 (11440565)
    "공덕": "11440565", "마포구청": "11440565", "마포대교": "11440565",
    "마포역": "11440565",
    # 도화동 (11440585)
    "도화": "11440585", "마포소방서": "11440585",
    # 용강동 (11440590)
    "용강": "11440590", "대흥빌딩": "11440590",
    # 대흥동 (11440600)
    "대흥": "11440600", "대흥역": "11440600",
    # 염리동 (11440610)
    "염리": "11440610",
    # 신수동 (11440630)
    "신수": "11440630", "광흥창": "11440630", "광흥창역": "11440630",
    # 서강동 (11440655)
    "서강": "11440655",
    # 서교동 (11440660)
    "서교": "11440660", "홍대입구": "11440660", "홍대": "11440660",
    "상수": "11440660", "상수역": "11440660",
    # 합정동 (11440680)
    "합정": "11440680",
    # 망원1동 (11440690)
    "망원역": "11440690", "망원1동": "11440690", "망원동주민": "11440690",
    # 망원2동 (11440700)
    "망원2동": "11440700",
    # 연남동 (11440710)
    "연남": "11440710",
    # 성산1동 (11440720)
    "성산1동": "11440720", "성산시장": "11440720",
    # 성산2동 (11440730)
    "성산2동": "11440730",
    # 상암동 (11440740)
    "상암": "11440740", "DMC": "11440740", "월드컵": "11440740",
    "월드컵경기장": "11440740", "누리꿈": "11440740", "YTN": "11440740",
    "MBC": "11440740", "디지털미디어": "11440740",
}


def map_station_to_dong(station_name):
    """Map bus station name to dong code."""
    for keyword, dong_code in STATION_DONG_MAP.items():
        if keyword in str(station_name):
            return dong_code
    return None


def load_bus_data():
    """Load all monthly bus CSV files and aggregate to quarterly dong-level."""
    bus_dir = r"C:\Users\804\Desktop\데이터 파일"
    files = sorted(glob.glob(f"{bus_dir}/BUS_STATION_BOARDING_MONTH_*.csv"))

    print(f"  Loading {len(files)} bus CSV files...", flush=True)

    all_data = []
    for f in files:
        # Extract year-month from filename
        ym = Path(f).stem.split("_")[-1]  # e.g., "201901"
        year = int(ym[:4])
        month = int(ym[4:6])
        quarter = year * 10 + ((month - 1) // 3 + 1)

        if quarter > 20244:  # Only use up to 2024Q4
            continue

        try:
            df = pd.read_csv(f, encoding="cp949", low_memory=False)
            cols = df.columns.tolist()
            # 2023+ files have extra column (9 cols vs 8 cols)
            if len(cols) == 9:
                station_col = cols[5]   # station name
                boarding_col = cols[6]  # boarding
                alighting_col = cols[7] # alighting
            else:
                station_col = cols[4]
                boarding_col = cols[5]
                alighting_col = cols[6]

            # Map to dong
            df["dong_code"] = df[station_col].apply(map_station_to_dong)
            mapo = df[df["dong_code"].notna()].copy()

            if len(mapo) == 0:
                continue

            # Aggregate by dong
            agg = mapo.groupby("dong_code").agg({
                boarding_col: "sum",
                alighting_col: "sum",
            }).reset_index()
            agg["quarter"] = quarter
            agg["year_month"] = ym
            agg.columns = ["dong_code", "bus_boarding", "bus_alighting", "quarter", "year_month"]
            all_data.append(agg)
        except Exception as e:
            continue

    if not all_data:
        return None

    bus_df = pd.concat(all_data, ignore_index=True)

    # Aggregate monthly -> quarterly
    quarterly = bus_df.groupby(["dong_code", "quarter"]).agg({
        "bus_boarding": "sum",
        "bus_alighting": "sum",
    }).reset_index()
    quarterly["bus_total"] = quarterly["bus_boarding"] + quarterly["bus_alighting"]

    print(f"  Bus data: {len(quarterly)} dong-quarter rows", flush=True)
    print(f"  Quarters: {sorted(quarterly['quarter'].unique())[:5]}...{sorted(quarterly['quarter'].unique())[-3:]}", flush=True)
    print(f"  Dongs mapped: {quarterly['dong_code'].nunique()}", flush=True)

    return quarterly


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
    print("  Bus Ridership Feature Test (Real Data)")
    print("=" * 80)

    # Load bus data
    bus_q = load_bus_data()
    if bus_q is None:
        print("  Bus data loading failed!")
        return

    # Show bus data summary per dong
    print(f"\n  Bus ridership per dong (2024 quarterly avg):")
    bus_2024 = bus_q[bus_q["quarter"] // 10 == 2024]
    for dc in sorted(DONG_MAP.keys()):
        dn = DONG_MAP[dc]
        sub = bus_2024[bus_2024["dong_code"] == dc]
        if len(sub) > 0:
            avg = sub["bus_total"].mean()
            print(f"    {dn:<8} {avg:>12,.0f}")
        else:
            print(f"    {dn:<8} {'no data':>12}")

    # Load main data
    sales = load_sales_data(dong_prefix="11440")
    stores = load_store_data(dong_prefix="11440")
    ts_raw = build_timeseries(sales, stores)
    np.random.seed(42)
    ts = impute_guide(ts_raw.copy())
    ts["pop_per_store"] = np.where(ts["store_count"]>0, ts["total_pop"]/ts["store_count"], 0)
    base_fc = [c for c in ALL_FEATURES if c in ts.columns] + ["pop_per_store"]

    # Merge bus data
    ts["dong_code"] = ts["dong_code"].astype(str)
    bus_q["dong_code"] = bus_q["dong_code"].astype(str)

    ts_bus = ts.merge(bus_q[["dong_code", "quarter", "bus_boarding", "bus_alighting", "bus_total"]],
                      on=["dong_code", "quarter"], how="left")
    # Log scale for bus data
    for col in ["bus_boarding", "bus_alighting", "bus_total"]:
        ts_bus[col] = np.log1p(ts_bus[col].fillna(0))

    # Derived: bus_per_store
    ts_bus["bus_per_store"] = np.where(
        ts_bus["store_count"] > 0,
        ts_bus["bus_total"] / ts_bus["store_count"], 0
    )

    bus_null = ts_bus["bus_total"].isna().sum()
    bus_zero = (ts_bus["bus_total"] == 0).sum()
    print(f"\n  Bus data merge: NaN={bus_null}, Zero={bus_zero} / {len(ts_bus)}")

    # Experiments
    experiments = {
        "1. Baseline (27feat)": (ts, base_fc),
        "2. + bus_total": (ts_bus, base_fc + ["bus_total"]),
        "3. + bus_boarding+alighting": (ts_bus, base_fc + ["bus_boarding", "bus_alighting"]),
        "4. + bus_per_store": (ts_bus, base_fc + ["bus_per_store"]),
        "5. + all bus features": (ts_bus, base_fc + ["bus_boarding", "bus_alighting", "bus_total", "bus_per_store"]),
    }

    print(f"\n{'='*80}")
    print("  Results")
    print(f"{'='*80}")
    print(f"\n  {'Experiment':<30} | {'Feat':>4} {'MAPE':>7} {'MAE':>14} {'R2':>8} | {'Q1':>6} {'Q2':>6} {'Q3':>6} {'Q4':>6}")
    print("  " + "-" * 95)

    all_results = {}
    for name, (ts_data, fc) in experiments.items():
        df_r = train_and_backtest(ts_data, fc)
        if len(df_r) == 0: continue
        a, p = df_r["actual"].values, df_r["predicted"].values
        steps = {s: mape(df_r[df_r["step"]==s]["actual"].values, df_r[df_r["step"]==s]["predicted"].values)
                 for s in range(1, N_STEPS+1)}
        all_results[name] = df_r
        print(f"  {name:<30} | {len(fc):>4} {mape(a,p):>6.1f}% {mae(a,p):>13,.0f} {r_squared(a,p):>7.4f} | "
              f"{steps[1]:>5.1f}% {steps[2]:>5.1f}% {steps[3]:>5.1f}% {steps[4]:>5.1f}%")

    # Dong comparison
    if len(all_results) >= 2:
        best_name = min(all_results, key=lambda k: mape(all_results[k]["actual"].values, all_results[k]["predicted"].values))
        base_name = "1. Baseline (27feat)"

        print(f"\n{'='*80}")
        print(f"  Dong: Baseline vs Best ({best_name})")
        print(f"{'='*80}")
        dong_order = sorted(DONG_MAP.values())
        print(f"  {'dong':<8} {'Baseline':>10} {'Best':>10} {'Diff':>8}")
        print("  " + "-" * 40)
        for dong in dong_order:
            g1 = all_results[base_name][all_results[base_name]["dong"]==dong]
            g2 = all_results[best_name][all_results[best_name]["dong"]==dong]
            m1 = mape(g1["actual"].values, g1["predicted"].values) if len(g1) > 0 else 0
            m2 = mape(g2["actual"].values, g2["predicted"].values) if len(g2) > 0 else 0
            diff = m1 - m2
            arrow = "v" if diff > 1 else "^" if diff < -1 else "="
            print(f"  {dong:<8} {m1:>9.1f}% {m2:>9.1f}% {diff:>+7.1f} {arrow}")

        # Industry comparison
        print(f"\n  {'ind':<10} {'Baseline':>10} {'Best':>10} {'Diff':>8}")
        print("  " + "-" * 42)
        ind_order = ["한식","중식","일식","양식","제과","패스트푸드","치킨","분식","호프","커피"]
        for ind in ind_order:
            g1 = all_results[base_name][all_results[base_name]["ind"]==ind]
            g2 = all_results[best_name][all_results[best_name]["ind"]==ind]
            m1 = mape(g1["actual"].values, g1["predicted"].values) if len(g1) > 0 else 0
            m2 = mape(g2["actual"].values, g2["predicted"].values) if len(g2) > 0 else 0
            diff = m1 - m2
            arrow = "v" if diff > 1 else "^" if diff < -1 else "="
            print(f"  {ind:<10} {m1:>9.1f}% {m2:>9.1f}% {diff:>+7.1f} {arrow}")

    elapsed = time.time() - t0
    print(f"\n  Total time: {elapsed:.0f}s ({elapsed/60:.1f}min)")


if __name__ == "__main__":
    main()
