"""SARIMA vs LSTM Full Comparison.

Runs identical tests on SARIMA:
  1. Imputation comparison (fillna(0) vs guide-density vs Seoul LSTM)
  2. Dong x Industry MAPE matrix
  3. pop_per_store effect (SARIMA uses exog variables)
  4. COVID strategies
  5. Step-wise MAPE comparison

SARIMA: per (dong x industry) group, SARIMAX(p,d,q)(P,D,Q,s=4)
LSTM: optimal config (guide-density + pop_per_store, win=4, hid=128)
"""
import sys
import time
import warnings
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from pathlib import Path
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import MinMaxScaler
from statsmodels.tsa.statespace.sarimax import SARIMAX
from torch.utils.data import DataLoader, TensorDataset

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.lstm_forecast.data_prep import (
    ALL_FEATURES, SALES_FEATURES, build_timeseries, load_sales_data, load_store_data,
)
from models.lstm_forecast.model import LSTMForecaster
from validation.accuracy_metrics import mape, mae, r_squared, rmse

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
# Imputation (guide-density)
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
# SARIMA Forecasting
# ===========================================================================

def sarima_forecast_group(train_series, exog_train=None, exog_test=None, n_steps=4):
    """Fit SARIMA on one dong x industry group and forecast n_steps."""
    if len(train_series) < 8:
        return None

    # Try multiple SARIMA orders
    orders_to_try = [
        ((1,1,1), (1,1,0,4)),
        ((1,0,1), (1,1,0,4)),
        ((0,1,1), (0,1,1,4)),
        ((1,1,0), (1,0,0,4)),
        ((1,0,0), (0,1,0,4)),
    ]

    best_model = None
    best_aic = float("inf")

    for order, seasonal in orders_to_try:
        try:
            model = SARIMAX(
                train_series,
                exog=exog_train,
                order=order,
                seasonal_order=seasonal,
                enforce_stationarity=False,
                enforce_invertibility=False,
            )
            fit = model.fit(disp=False, maxiter=200)
            if fit.aic < best_aic:
                best_aic = fit.aic
                best_model = fit
        except Exception:
            continue

    if best_model is None:
        # Fallback: simple model
        try:
            model = SARIMAX(train_series, order=(1,0,0), seasonal_order=(0,0,0,4),
                           enforce_stationarity=False, enforce_invertibility=False)
            best_model = model.fit(disp=False, maxiter=100)
        except Exception:
            return None

    try:
        forecast = best_model.forecast(steps=n_steps, exog=exog_test)
        return np.array(forecast).flatten()
    except Exception:
        return None


def sarima_backtest(ts_df, use_exog=False, exog_cols=None):
    """Run SARIMA backtest for all dong x industry groups."""
    results = []
    test_q = [20241, 20242, 20243, 20244]
    n_groups = 0
    n_fail = 0

    for (dc, ic), grp in ts_df.groupby(["dong_code", "industry_code"]):
        grp = grp.sort_values("quarter")
        tqs = [q for q in grp["quarter"].values if q in test_q]
        if len(tqs) < N_STEPS:
            continue

        n_groups += 1
        dn = DONG_MAP.get(str(dc), str(dc))
        ind = IND_MAP.get(str(ic), str(ic))

        # Split train/test
        train_mask = grp["quarter"] < 20241
        train = grp[train_mask]
        test = grp[grp["quarter"].isin(test_q)]

        if len(train) < 8 or len(test) < N_STEPS:
            n_fail += 1
            continue

        train_series = train["monthly_sales"].values
        actual_series = test["monthly_sales"].values[:N_STEPS]

        # Exogenous variables
        exog_tr = None
        exog_te = None
        if use_exog and exog_cols:
            avail = [c for c in exog_cols if c in grp.columns]
            if avail:
                exog_tr = train[avail].values.astype(float)
                exog_te = test[avail].head(N_STEPS).values.astype(float)

        preds = sarima_forecast_group(train_series, exog_tr, exog_te, N_STEPS)
        if preds is None:
            n_fail += 1
            continue

        for step in range(N_STEPS):
            actual_val = np.expm1(actual_series[step])
            pred_val = max(0, np.expm1(preds[step]))
            results.append({
                "dong": dn, "ind": ind, "step": step + 1,
                "quarter": tqs[step],
                "actual": actual_val, "predicted": pred_val,
            })

    print(f"    SARIMA: {n_groups} groups, {n_fail} failed", flush=True)
    return pd.DataFrame(results)


# ===========================================================================
# LSTM Forecasting (optimal config)
# ===========================================================================

def lstm_backtest(ts_df, feat_cols):
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


# ===========================================================================
# Evaluation helpers
# ===========================================================================

def eval_results(df_r, label):
    if df_r is None or len(df_r) == 0:
        return None
    a, p = df_r["actual"].values, df_r["predicted"].values
    steps = {}
    for s in range(1, N_STEPS+1):
        ds = df_r[df_r["step"]==s]
        steps[f"Q{s}"] = mape(ds["actual"].values, ds["predicted"].values) if len(ds) > 0 else 0
    dong_avgs = {}
    for dong, g in df_r.groupby("dong"):
        dong_avgs[dong] = mape(g["actual"].values, g["predicted"].values)
    ind_avgs = {}
    for ind, g in df_r.groupby("ind"):
        ind_avgs[ind] = mape(g["actual"].values, g["predicted"].values)
    return {
        "mape": mape(a,p), "mae": mae(a,p), "r2": r_squared(a,p), "rmse": rmse(a,p),
        "n": len(df_r), "steps": steps, "dong": dong_avgs, "ind": ind_avgs,
    }


# ===========================================================================
# Main
# ===========================================================================

def main():
    t0 = time.time()
    print("=" * 80)
    print("  SARIMA vs LSTM Full Comparison")
    print("=" * 80)

    # Load & impute
    sales = load_sales_data(dong_prefix="11440")
    stores = load_store_data(dong_prefix="11440")
    ts_raw = build_timeseries(sales, stores)
    np.random.seed(42)
    ts = impute_guide(ts_raw.copy())
    ts["pop_per_store"] = np.where(ts["store_count"]>0, ts["total_pop"]/ts["store_count"], 0)
    base_fc = [c for c in ALL_FEATURES if c in ts.columns]
    fc_with_pop = base_fc + ["pop_per_store"]
    print(f"  Data: {ts.shape}, Features: {len(fc_with_pop)}")

    exog_cols = ["store_count", "total_pop", "pop_per_store", "cpi_index", "quarter_num"]
    exog_avail = [c for c in exog_cols if c in ts.columns]

    # ===========================================================
    # Test 1: Overall comparison
    # ===========================================================
    print(f"\n{'='*80}")
    print("  [1] Overall: SARIMA vs LSTM")
    print(f"{'='*80}")

    experiments = {}

    # SARIMA without exog
    print("\n  SARIMA (no exog)...")
    df_s1 = sarima_backtest(ts, use_exog=False)
    experiments["SARIMA"] = eval_results(df_s1, "SARIMA")

    # SARIMA with exog
    print("  SARIMA + exog...")
    df_s2 = sarima_backtest(ts, use_exog=True, exog_cols=exog_avail)
    experiments["SARIMA+exog"] = eval_results(df_s2, "SARIMA+exog")

    # LSTM (optimal)
    print("  LSTM (optimal)...")
    df_lstm = lstm_backtest(ts, fc_with_pop)
    experiments["LSTM"] = eval_results(df_lstm, "LSTM")

    # Print overall
    print(f"\n  {'Method':<18} | {'MAPE':>7} {'MAE':>14} {'R2':>8} {'RMSE':>14} | {'Q1':>6} {'Q2':>6} {'Q3':>6} {'Q4':>6} | {'n':>4}")
    print("  " + "-" * 105)
    for name, ev in experiments.items():
        if ev is None: continue
        s = ev["steps"]
        print(f"  {name:<18} | {ev['mape']:>6.1f}% {ev['mae']:>13,.0f} {ev['r2']:>7.4f} {ev['rmse']:>13,.0f} | "
              f"{s.get('Q1',0):>5.1f}% {s.get('Q2',0):>5.1f}% {s.get('Q3',0):>5.1f}% {s.get('Q4',0):>5.1f}% | {ev['n']:>4}")

    # ===========================================================
    # Test 2: Dong comparison
    # ===========================================================
    print(f"\n{'='*80}")
    print("  [2] Dong MAPE")
    print(f"{'='*80}")
    dong_order = sorted(DONG_MAP.values())
    header = f"  {'dong':<8}"
    for name in experiments:
        header += f" {name:>12}"
    print(header)
    print("  " + "-" * (8 + 13 * len(experiments)))
    for dong in dong_order:
        line = f"  {dong:<8}"
        for name, ev in experiments.items():
            if ev and dong in ev["dong"]:
                line += f" {ev['dong'][dong]:>11.1f}%"
            else:
                line += f" {'N/A':>12}"
        print(line)

    # ===========================================================
    # Test 3: Industry comparison
    # ===========================================================
    print(f"\n{'='*80}")
    print("  [3] Industry MAPE")
    print(f"{'='*80}")
    ind_order = ["한식","중식","일식","양식","제과","패스트푸드","치킨","분식","호프","커피"]
    header = f"  {'ind':<10}"
    for name in experiments:
        header += f" {name:>12}"
    print(header)
    print("  " + "-" * (10 + 13 * len(experiments)))
    for ind in ind_order:
        line = f"  {ind:<10}"
        for name, ev in experiments.items():
            if ev and ind in ev["ind"]:
                line += f" {ev['ind'][ind]:>11.1f}%"
            else:
                line += f" {'N/A':>12}"
        print(line)

    # ===========================================================
    # Test 4: Imputation comparison for SARIMA
    # ===========================================================
    print(f"\n{'='*80}")
    print("  [4] Imputation effect on SARIMA")
    print(f"{'='*80}")

    # fillna(0)
    ts_zero = ts_raw.copy()
    feat_zero = [c for c in ALL_FEATURES if c in ts_zero.columns]
    ts_zero[feat_zero] = ts_zero[feat_zero].fillna(0)
    print("  SARIMA + fillna(0)...")
    df_sz = sarima_backtest(ts_zero, use_exog=False)
    ev_sz = eval_results(df_sz, "SARIMA+fillna0")

    print("  SARIMA + guide-density (already computed)...")
    ev_sg = experiments.get("SARIMA")

    if ev_sz and ev_sg:
        print(f"\n  {'Imputation':<22} | {'MAPE':>7} {'MAE':>14} {'R2':>8}")
        print("  " + "-" * 55)
        print(f"  {'SARIMA+fillna(0)':<22} | {ev_sz['mape']:>6.1f}% {ev_sz['mae']:>13,.0f} {ev_sz['r2']:>7.4f}")
        print(f"  {'SARIMA+guide-density':<22} | {ev_sg['mape']:>6.1f}% {ev_sg['mae']:>13,.0f} {ev_sg['r2']:>7.4f}")

    # ===========================================================
    # Summary
    # ===========================================================
    print(f"\n{'='*80}")
    print("  SUMMARY")
    print(f"{'='*80}")

    if experiments.get("LSTM") and experiments.get("SARIMA"):
        lstm_ev = experiments["LSTM"]
        sarima_ev = experiments["SARIMA"]
        sarima_exog_ev = experiments.get("SARIMA+exog")

        print(f"\n  {'Metric':<14} {'LSTM':>12} {'SARIMA':>12} {'SARIMA+exog':>14} {'Winner':>10}")
        print("  " + "-" * 65)

        metrics = [
            ("MAPE", lstm_ev["mape"], sarima_ev["mape"],
             sarima_exog_ev["mape"] if sarima_exog_ev else 0),
            ("MAE", lstm_ev["mae"], sarima_ev["mae"],
             sarima_exog_ev["mae"] if sarima_exog_ev else 0),
            ("R2", lstm_ev["r2"], sarima_ev["r2"],
             sarima_exog_ev["r2"] if sarima_exog_ev else 0),
        ]
        for name, lv, sv, sev in metrics:
            if name == "R2":
                winner = "LSTM" if lv > max(sv, sev) else "SARIMA+exog" if sev > sv else "SARIMA"
                print(f"  {name:<14} {lv:>11.4f} {sv:>11.4f} {sev:>13.4f} {winner:>10}")
            elif name == "MAPE":
                winner = "LSTM" if lv < min(sv, sev) else "SARIMA+exog" if sev < sv else "SARIMA"
                print(f"  {name:<14} {lv:>10.1f}% {sv:>10.1f}% {sev:>12.1f}% {winner:>10}")
            else:
                winner = "LSTM" if lv < min(sv, sev) else "SARIMA+exog" if sev < sv else "SARIMA"
                print(f"  {name:<14} {lv:>11,.0f} {sv:>11,.0f} {sev:>13,.0f} {winner:>10}")

        # Dong wins count
        lstm_wins, sarima_wins, tie = 0, 0, 0
        for dong in dong_order:
            lm = lstm_ev["dong"].get(dong, 999)
            sm = sarima_ev["dong"].get(dong, 999)
            if lm < sm - 1: lstm_wins += 1
            elif sm < lm - 1: sarima_wins += 1
            else: tie += 1
        print(f"\n  Dong wins: LSTM={lstm_wins} SARIMA={sarima_wins} Tie={tie}")

        # Industry wins count
        lstm_wins, sarima_wins, tie = 0, 0, 0
        for ind in ind_order:
            lm = lstm_ev["ind"].get(ind, 999)
            sm = sarima_ev["ind"].get(ind, 999)
            if lm < sm - 1: lstm_wins += 1
            elif sm < lm - 1: sarima_wins += 1
            else: tie += 1
        print(f"  Industry wins: LSTM={lstm_wins} SARIMA={sarima_wins} Tie={tie}")

    elapsed = time.time() - t0
    print(f"\n  Total time: {elapsed:.0f}s ({elapsed/60:.1f}min)")


if __name__ == "__main__":
    main()
