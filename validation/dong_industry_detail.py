"""Optimal config (guide-density, win=4, hid=128) dong/industry breakdown."""
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

np.random.seed(42)
torch.manual_seed(42)
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
DONG_NAME_PAIR = {"망원2동": "망원1동", "성산2동": "성산1동"}


def hot_deck(df, col, donors_f):
    r = df.copy()
    for q, qdf in r.groupby("quarter"):
        miss = qdf[col].isna() | (qdf[col] == 0)
        if not miss.any():
            continue
        d = qdf[~miss]
        rec = qdf[miss]
        if d.empty:
            continue
        for idx, row in rec.iterrows():
            dn = row.get("dong_name", "")
            dv = None
            if dn in DONG_NAME_PAIR:
                pr = d[d["dong_name"] == DONG_NAME_PAIR[dn]][col]
                if not pr.empty:
                    dv = pr.values[0]
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


def main():
    sales = load_sales_data(dong_prefix="11440")
    stores = load_store_data(dong_prefix="11440")
    ts = build_timeseries(sales, stores)
    ts = impute(ts)
    fc = [c for c in ALL_FEATURES if c in ts.columns]

    # Sequences
    fs = MinMaxScaler()
    tsc = MinMaxScaler()
    df_train = ts[ts["quarter"] <= 20234]
    fs.fit(df_train[fc].values.astype(np.float32))
    tsc.fit(df_train[["monthly_sales"]].values.astype(np.float32))
    X_l, y_l, w_l = [], [], []
    hw = "sample_weight" in df_train.columns
    for _, g in df_train.groupby(["dong_code", "industry_code"]):
        if len(g) <= WINDOW:
            continue
        fv = fs.transform(g[fc].values.astype(np.float32))
        tv = tsc.transform(g[["monthly_sales"]].values.astype(np.float32))
        wv = g["sample_weight"].values if hw else np.ones(len(g))
        for i in range(len(g) - WINDOW):
            X_l.append(fv[i:i + WINDOW])
            y_l.append(tv[i + WINDOW])
            w_l.append(float(wv[i + WINDOW]))
    X = np.array(X_l, dtype=np.float32)
    y = np.array(y_l, dtype=np.float32)
    w = np.array(w_l, dtype=np.float32)

    # Train
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
    tidx = fc.index("monthly_sales")
    results = []
    test_q = [20241, 20242, 20243, 20244]
    for (dc, ic), g in ts.groupby(["dong_code", "industry_code"]):
        g = g.sort_values("quarter")
        tqs = [q for q in g["quarter"].values if q in test_q]
        if len(tqs) < N_STEPS:
            continue
        fi = g[g["quarter"] == tqs[0]].index[0]
        fp = g.index.get_loc(fi)
        if fp < WINDOW:
            continue
        wd = g.iloc[fp - WINDOW:fp]
        fv = fs.transform(wd[fc].values.astype(np.float32))
        seq = torch.from_numpy(fv).unsqueeze(0)
        dn = DONG_MAP.get(str(dc), str(dc))
        ind = IND_MAP.get(str(ic), str(ic))
        for step, q in enumerate(tqs[:N_STEPS]):
            with torch.no_grad():
                ps = model(seq).cpu().numpy()
            pl = tsc.inverse_transform(ps)[0][0]
            al = g.iloc[fp + step]["monthly_sales"]
            results.append({"dong": dn, "ind": ind, "step": step + 1, "quarter": q,
                            "actual": np.expm1(al), "predicted": max(0, np.expm1(pl))})
            ns = seq[0, -1, :].clone()
            ns[tidx] = float(ps[0][0])
            seq = torch.cat([seq[:, 1:, :], ns.unsqueeze(0).unsqueeze(0)], dim=1)

    df = pd.DataFrame(results)
    a_all, p_all = df["actual"].values, df["predicted"].values

    print("=" * 60)
    print(f"  전체: MAPE={mape(a_all, p_all):.1f}%  MAE={mae(a_all, p_all):,.0f}  R2={r_squared(a_all, p_all):.4f}  (n={len(df)})")
    print("=" * 60)

    # 동별
    print(f"\n{'동':<8} {'MAPE':>7} {'MAE':>14} {'R2':>8} {'n':>4}")
    print("-" * 45)
    for dong, g in sorted(df.groupby("dong"), key=lambda x: mape(x[1]["actual"].values, x[1]["predicted"].values)):
        a, p = g["actual"].values, g["predicted"].values
        print(f"{dong:<8} {mape(a, p):>6.1f}% {mae(a, p):>13,.0f} {r_squared(a, p):>7.4f} {len(g):>4}")

    # 업종별
    print(f"\n{'업종':<10} {'MAPE':>7} {'MAE':>14} {'R2':>8} {'n':>4}")
    print("-" * 47)
    for ind, g in sorted(df.groupby("ind"), key=lambda x: mape(x[1]["actual"].values, x[1]["predicted"].values)):
        a, p = g["actual"].values, g["predicted"].values
        print(f"{ind:<10} {mape(a, p):>6.1f}% {mae(a, p):>13,.0f} {r_squared(a, p):>7.4f} {len(g):>4}")

    # 동x업종 상위/하위
    cross = []
    for (dong, ind), g in df.groupby(["dong", "ind"]):
        a, p = g["actual"].values, g["predicted"].values
        cross.append({"dong": dong, "ind": ind, "mape": mape(a, p),
                      "mae": mae(a, p), "r2": r_squared(a, p), "n": len(g)})
    cx = pd.DataFrame(cross).sort_values("mape")

    print(f"\n{'='*60}")
    print("  동x업종 상위 10 (가장 정확)")
    print(f"{'='*60}")
    print(f"{'동':<8} {'업종':<10} {'MAPE':>7} {'MAE':>14} {'R2':>8}")
    print("-" * 50)
    for _, r in cx.head(10).iterrows():
        print(f"{r['dong']:<8} {r['ind']:<10} {r['mape']:>6.1f}% {r['mae']:>13,.0f} {r['r2']:>7.4f}")

    print(f"\n{'='*60}")
    print("  동x업종 하위 10 (가장 부정확)")
    print(f"{'='*60}")
    print(f"{'동':<8} {'업종':<10} {'MAPE':>7} {'MAE':>14} {'R2':>8}")
    print("-" * 50)
    for _, r in cx.tail(10).iterrows():
        print(f"{r['dong']:<8} {r['ind']:<10} {r['mape']:>6.1f}% {r['mae']:>13,.0f} {r['r2']:>7.4f}")


if __name__ == "__main__":
    main()
