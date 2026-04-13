"""Dong x Industry MAPE matrix - optimal config (guide-density, win=4, hid=128)."""
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
    "11440555": "아현동", "11440565": "공덕동", "11440585": "도화동",
    "11440590": "용강동", "11440600": "대흥동", "11440610": "염리동",
    "11440630": "신수동", "11440655": "서강동", "11440660": "서교동",
    "11440680": "합정동", "11440690": "망원1동", "11440700": "망원2동",
    "11440710": "연남동", "11440720": "성산1동", "11440730": "성산2동",
    "11440740": "상암동",
}
IND_MAP = {
    "CS100001": "한식", "CS100002": "중식", "CS100003": "일식",
    "CS100004": "양식", "CS100005": "제과", "CS100006": "패스트푸드",
    "CS100007": "치킨", "CS100008": "분식", "CS100009": "호프",
    "CS100010": "커피",
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
            for ps, pd_ in [("2동", "1동")]:
                if ps in str(dn):
                    pair_name = str(dn).replace(ps, pd_)
                    pr = d[d[dn_col] == pair_name][col]
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

def main():
    sales = load_sales_data(dong_prefix="11440")
    stores = load_store_data(dong_prefix="11440")
    ts = build_timeseries(sales, stores)
    ts = impute(ts)
    fc = [c for c in ALL_FEATURES if c in ts.columns]

    # Train
    fs = MinMaxScaler(); tsc = MinMaxScaler()
    dt = ts[ts["quarter"] <= 20234]
    fs.fit(dt[fc].values.astype(np.float32))
    tsc.fit(dt[["monthly_sales"]].values.astype(np.float32))
    X_l, y_l, w_l = [], [], []
    hw = "sample_weight" in dt.columns
    for _, g in dt.groupby(["dong_code","industry_code"]):
        if len(g) <= WINDOW: continue
        fv = fs.transform(g[fc].values.astype(np.float32))
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

    # Backtest per dong x ind
    tidx = fc.index("monthly_sales")
    test_q = [20241,20242,20243,20244]
    results = []
    for (dc,ic), g in ts.groupby(["dong_code","industry_code"]):
        g = g.sort_values("quarter")
        tqs = [q for q in g["quarter"].values if q in test_q]
        if len(tqs) < N_STEPS: continue
        fi = g[g["quarter"]==tqs[0]].index[0]; fp = g.index.get_loc(fi)
        if fp < WINDOW: continue
        wd = g.iloc[fp-WINDOW:fp]
        fv = fs.transform(wd[fc].values.astype(np.float32))
        seq = torch.from_numpy(fv).unsqueeze(0)
        dn = DONG_MAP.get(str(dc),str(dc)); ind = IND_MAP.get(str(ic),str(ic))
        for step, q in enumerate(tqs[:N_STEPS]):
            with torch.no_grad(): ps = model(seq).cpu().numpy()
            pl = tsc.inverse_transform(ps)[0][0]; al = g.iloc[fp+step]["monthly_sales"]
            results.append({"dong":dn,"ind":ind,"step":step+1,"quarter":q,
                           "actual":np.expm1(al),"predicted":max(0,np.expm1(pl)),
                           "actual_raw":al,"pred_raw":pl})
            ns = seq[0,-1,:].clone(); ns[tidx]=float(ps[0][0])
            seq = torch.cat([seq[:,1:,:],ns.unsqueeze(0).unsqueeze(0)],dim=1)

    df = pd.DataFrame(results)

    # === MAPE Matrix (dong x ind) ===
    print("=" * 120)
    print("  동 x 업종 MAPE 매트릭스 (%)")
    print("=" * 120)

    ind_order = ["한식","중식","일식","양식","제과","패스트푸드","치킨","분식","호프","커피"]
    dong_order = list(DONG_MAP.values())

    # Build matrix
    matrix = {}
    for (dong, ind), g in df.groupby(["dong","ind"]):
        a, p = g["actual"].values, g["predicted"].values
        matrix[(dong, ind)] = mape(a, p)

    # Print header
    header = f"{'동':<8}"
    for ind in ind_order:
        header += f" {ind:>8}"
    header += f" {'평균':>8}"
    print(header)
    print("-" * 120)

    dong_avgs = {}
    for dong in dong_order:
        line = f"{dong:<8}"
        dong_mapes = []
        for ind in ind_order:
            m = matrix.get((dong, ind))
            if m is not None:
                dong_mapes.append(m)
                if m <= 15:
                    line += f" {m:>7.1f}*"
                elif m <= 25:
                    line += f" {m:>8.1f}"
                elif m <= 40:
                    line += f" {m:>7.1f}!"
                else:
                    line += f" {m:>6.1f}!!"
            else:
                line += f" {'N/A':>8}"
        avg = np.mean(dong_mapes) if dong_mapes else 0
        dong_avgs[dong] = avg
        line += f" {avg:>8.1f}"
        print(line)

    # Industry averages
    print("-" * 120)
    line = f"{'평균':<8}"
    for ind in ind_order:
        ind_mapes = [matrix.get((d, ind)) for d in dong_order if matrix.get((d, ind)) is not None]
        avg = np.mean(ind_mapes) if ind_mapes else 0
        line += f" {avg:>8.1f}"
    all_mapes = [v for v in matrix.values()]
    line += f" {np.mean(all_mapes):>8.1f}"
    print(line)

    print("\n  * = 15% 이하 (우수)  ! = 25~40% (주의)  !! = 40% 이상 (미흡)")

    # === Summary stats ===
    all_m = list(matrix.values())
    print(f"\n{'='*70}")
    print(f"  동x업종 MAPE 분포 (n={len(all_m)})")
    print(f"{'='*70}")
    print(f"  평균: {np.mean(all_m):.1f}%")
    print(f"  중앙값: {np.median(all_m):.1f}%")
    print(f"  최소: {np.min(all_m):.1f}%")
    print(f"  최대: {np.max(all_m):.1f}%")
    print(f"  표준편차: {np.std(all_m):.1f}%")

    # Distribution
    buckets = [(0,10,"10% 이하 (매우 우수)"), (10,15,"10~15% (우수)"),
               (15,20,"15~20% (양호)"), (20,30,"20~30% (보통)"),
               (30,50,"30~50% (주의)"), (50,200,"50% 이상 (미흡)")]
    print(f"\n  MAPE 구간별 분포:")
    for lo, hi, label in buckets:
        cnt = sum(1 for m in all_m if lo <= m < hi)
        pct = cnt / len(all_m) * 100
        bar = "#" * int(pct / 2)
        print(f"    {label:<22} {cnt:>3}개 ({pct:>5.1f}%) {bar}")

    # === Dong ranking ===
    print(f"\n{'='*70}")
    print(f"  동별 평균 MAPE 순위")
    print(f"{'='*70}")
    for rank, (dong, avg) in enumerate(sorted(dong_avgs.items(), key=lambda x: x[1]), 1):
        grade = "A" if avg < 15 else "B" if avg < 20 else "C" if avg < 30 else "D" if avg < 40 else "F"
        print(f"  {rank:>2}. {dong:<8} {avg:>6.1f}%  [{grade}]")

    # === Industry ranking ===
    print(f"\n{'='*70}")
    print(f"  업종별 평균 MAPE 순위")
    print(f"{'='*70}")
    for ind in ind_order:
        ind_mapes = [matrix.get((d, ind)) for d in dong_order if matrix.get((d, ind)) is not None]
        if ind_mapes:
            avg = np.mean(ind_mapes)
            grade = "A" if avg < 15 else "B" if avg < 20 else "C" if avg < 30 else "D" if avg < 40 else "F"
            print(f"  {ind:<10} {avg:>6.1f}%  [{grade}]  (n={len(ind_mapes)})")


if __name__ == "__main__":
    main()
