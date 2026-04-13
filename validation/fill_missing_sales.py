"""Fill missing sales rows using same-industry adjacent dong data.

Problem: 75 quarter-rows where stores exist but sales data is missing.
Solution: For each missing (dong, industry, quarter), find the most similar
dong with sales data and estimate sales proportional to store count.

Then re-run full prediction pipeline and compare.
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

# Adjacent dong pairs for Hot Deck
DONG_NEIGHBORS = {
    "11440555": ["11440565","11440600"],           # 아현 -> 공덕, 대흥
    "11440565": ["11440555","11440585","11440600"], # 공덕 -> 아현, 도화, 대흥
    "11440585": ["11440565","11440590"],            # 도화 -> 공덕, 용강
    "11440590": ["11440585","11440600"],            # 용강 -> 도화, 대흥
    "11440600": ["11440555","11440610","11440630"], # 대흥 -> 아현, 염리, 신수
    "11440610": ["11440600","11440630"],            # 염리 -> 대흥, 신수
    "11440630": ["11440600","11440655"],            # 신수 -> 대흥, 서강
    "11440655": ["11440630","11440660"],            # 서강 -> 신수, 서교
    "11440660": ["11440655","11440680","11440710"], # 서교 -> 서강, 합정, 연남
    "11440680": ["11440660","11440690"],            # 합정 -> 서교, 망원1
    "11440690": ["11440680","11440700"],            # 망원1 -> 합정, 망원2
    "11440700": ["11440690","11440710"],            # 망원2 -> 망원1, 연남
    "11440710": ["11440660","11440700"],            # 연남 -> 서교, 망원2
    "11440720": ["11440730","11440740"],            # 성산1 -> 성산2, 상암
    "11440730": ["11440720","11440740"],            # 성산2 -> 성산1, 상암
    "11440740": ["11440720","11440730"],            # 상암 -> 성산1, 성산2
}


def compute_dong_ratio(sales_df, stores_df, target_dc, donor_dc, quarter):
    """Compute the relative scale ratio between two dongs using multiple signals.

    Uses:
      1. Sales ratio across other industries where both dongs have data
      2. Store count ratio for the same quarter
      3. Population ratio (if available)

    Returns a ratio: target_dong / donor_dong
    """
    s = sales_df
    st = stores_df

    ratios = []

    # 1. Other industry sales ratio for the same quarter
    target_sales = s[(s["dong_code"]==target_dc) & (s["quarter"]==quarter)]
    donor_sales = s[(s["dong_code"]==donor_dc) & (s["quarter"]==quarter)]

    if len(target_sales) > 0 and len(donor_sales) > 0:
        # Find common industries
        target_inds = set(target_sales["industry_code"].unique())
        donor_inds = set(donor_sales["industry_code"].unique())
        common_inds = target_inds & donor_inds

        for ind in common_inds:
            t_val = target_sales[target_sales["industry_code"]==ind]["monthly_sales"].iloc[0]
            d_val = donor_sales[donor_sales["industry_code"]==ind]["monthly_sales"].iloc[0]
            if d_val > 0 and t_val > 0:
                ratios.append(t_val / d_val)

    # 2. Total store count ratio
    target_stores = st[(st["dong_code"]==target_dc) & (st["quarter"]==quarter)]
    donor_stores = st[(st["dong_code"]==donor_dc) & (st["quarter"]==quarter)]
    t_total_stores = target_stores["store_count"].sum() if len(target_stores) > 0 else 0
    d_total_stores = donor_stores["store_count"].sum() if len(donor_stores) > 0 else 0
    if t_total_stores > 0 and d_total_stores > 0:
        ratios.append(t_total_stores / d_total_stores)

    if not ratios:
        return None

    # Use median to be robust against outliers
    return float(np.median(ratios))


def fill_missing_sales(sales_df, stores_df):
    """Fill missing sales rows using multi-factor dong ratio estimation.

    For each missing (dong, industry, quarter):
      1. Find adjacent dong with sales data as donor
      2. Compute dong ratio using other industries' sales + store count
      3. Estimate: donor_sales * dong_ratio * (target_stores / donor_stores) * noise
    """
    sales = sales_df.copy()
    stores = stores_df.copy()
    sales["dong_code"] = sales["dong_code"].astype(str)
    sales["industry_code"] = sales["industry_code"].astype(str)
    stores["dong_code"] = stores["dong_code"].astype(str)
    stores["industry_code"] = stores["industry_code"].astype(str)

    all_q = sorted(sales["quarter"].unique())
    sales_keys = set(zip(sales["dong_code"], sales["industry_code"], sales["quarter"]))

    sales_cols = [c for c in sales.columns if c not in
                  ["dong_code","industry_code","quarter","dong_name","year"]]

    new_rows = []
    filled_count = 0
    skipped_count = 0

    for dc in sorted(DONG_MAP.keys()):
        for ic in sorted(IND_MAP.keys()):
            for q in all_q:
                if (dc, ic, q) in sales_keys:
                    continue

                # Check if store exists
                st_row = stores[(stores["dong_code"]==dc) &
                               (stores["industry_code"]==ic) &
                               (stores["quarter"]==q)]
                if len(st_row) == 0:
                    continue
                target_store_count = st_row["store_count"].iloc[0]
                if target_store_count <= 0:
                    continue

                # Find donor from adjacent dongs
                donor = None
                donor_dc = None
                donor_store_count = None
                dong_ratio = None

                neighbors = DONG_NEIGHBORS.get(dc, [])
                for ndc in neighbors:
                    if (ndc, ic, q) in sales_keys:
                        donor_row = sales[(sales["dong_code"]==ndc) &
                                         (sales["industry_code"]==ic) &
                                         (sales["quarter"]==q)]
                        if len(donor_row) > 0:
                            # Compute multi-factor ratio
                            ratio = compute_dong_ratio(sales, stores, dc, ndc, q)
                            if ratio is not None:
                                donor = donor_row.iloc[0]
                                donor_dc = ndc
                                dong_ratio = ratio
                                n_st = stores[(stores["dong_code"]==ndc) &
                                             (stores["industry_code"]==ic) &
                                             (stores["quarter"]==q)]
                                donor_store_count = n_st["store_count"].iloc[0] if len(n_st) > 0 else target_store_count
                                break

                # Fallback: median dong with ratio
                if donor is None:
                    same_ind = sales[(sales["industry_code"]==ic) & (sales["quarter"]==q)]
                    if len(same_ind) > 0:
                        for _, candidate in same_ind.iterrows():
                            cdc = candidate["dong_code"]
                            ratio = compute_dong_ratio(sales, stores, dc, cdc, q)
                            if ratio is not None:
                                donor = candidate
                                donor_dc = cdc
                                dong_ratio = ratio
                                n_st = stores[(stores["dong_code"]==cdc) &
                                             (stores["industry_code"]==ic) &
                                             (stores["quarter"]==q)]
                                donor_store_count = n_st["store_count"].iloc[0] if len(n_st) > 0 else target_store_count
                                break

                if donor is None or dong_ratio is None:
                    skipped_count += 1
                    continue

                # === Check for dying business (skip if last sales dropped 50%+) ===
                target_recent = sales[(sales["dong_code"]==dc) & (sales["industry_code"]==ic)].sort_values("quarter")
                if len(target_recent) >= 2:
                    last_val = target_recent["monthly_sales"].iloc[-1]
                    prev_val = target_recent["monthly_sales"].iloc[-2]
                    if prev_val > 0 and (last_val / prev_val) < 0.5:
                        skipped_count += 1
                        continue

                # === Industry share method (primary) ===
                industry_share = None
                if len(target_recent) > 0:
                    last_q_with_data = target_recent["quarter"].max()
                    last_sales = target_recent[target_recent["quarter"]==last_q_with_data]["monthly_sales"].iloc[0]
                    total_dong_sales = sales[(sales["dong_code"]==dc) & (sales["quarter"]==last_q_with_data)]["monthly_sales"].sum()
                    if total_dong_sales > 0:
                        industry_share = last_sales / total_dong_sales

                if industry_share is not None and industry_share > 0:
                    # Use industry share: target dong's total sales this quarter * share
                    target_total_q = sales[(sales["dong_code"]==dc) & (sales["quarter"]==q)]["monthly_sales"].sum()
                    donor_monthly = donor["monthly_sales"] if "monthly_sales" in donor.index else 1
                    if target_total_q > 0 and donor_monthly > 0:
                        scale = (industry_share * target_total_q) / donor_monthly
                        scale *= np.random.normal(1.0, 0.03)
                        if dc == "11440720" and ic == "CS100005":
                            print(f"    [DBG] 성산1동 제과 {q}: share={industry_share:.6f} total_q={target_total_q:,.0f} donor={donor_monthly:,.0f} scale={scale:.6f}")
                    else:
                        # No other sales either, fall back to dong ratio
                        scale = dong_ratio * np.random.normal(1.0, 0.03)
                else:
                    # No prior data at all (completely new), use dong ratio + store ratio
                    if donor_store_count and donor_store_count > 0:
                        store_ratio = target_store_count / donor_store_count
                    else:
                        store_ratio = 1.0
                    scale = (dong_ratio * 0.7 + store_ratio * 0.3) * np.random.normal(1.0, 0.03)

                # Create new row
                new_row = {"dong_code": dc, "industry_code": ic, "quarter": q}
                if "dong_name" in sales.columns:
                    new_row["dong_name"] = DONG_MAP.get(dc, dc)
                if "industry_name" in sales.columns:
                    new_row["industry_name"] = donor.get("industry_name", "")

                for col in sales_cols:
                    if col in ["dong_name", "industry_name"]:
                        continue
                    val = donor.get(col, 0)
                    if isinstance(val, (int, float, np.integer, np.floating)) and not (isinstance(val, float) and np.isnan(val)):
                        new_row[col] = float(val) * scale
                    else:
                        new_row[col] = val

                new_row["is_estimated"] = 1
                new_rows.append(new_row)
                filled_count += 1

    if new_rows:
        new_df = pd.DataFrame(new_rows)
        sales = pd.concat([sales, new_df], ignore_index=True)
        sales = sales.sort_values(["dong_code", "industry_code", "quarter"]).reset_index(drop=True)

    return sales, filled_count


# ===========================================================================
# Standard pipeline (same as previous tests)
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


def train_and_backtest(ts_df, feat_cols, label=""):
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
    np.random.seed(42)
    print("=" * 90)
    print("  Missing Sales Fill + Re-evaluation")
    print("=" * 90)

    # Load raw
    sales_raw = load_sales_data(dong_prefix="11440")
    stores_raw = load_store_data(dong_prefix="11440")
    print(f"  Before: sales={len(sales_raw)} rows")

    # Fill missing sales
    sales_filled, n_filled = fill_missing_sales(sales_raw, stores_raw)
    print(f"  After:  sales={len(sales_filled)} rows (+{n_filled} filled)")

    # Verify: check 성산1동 제과 2024Q3
    sf = sales_filled
    sf["dong_code"] = sf["dong_code"].astype(str)
    sf["industry_code"] = sf["industry_code"].astype(str)
    check = sf[(sf["dong_code"]=="11440720") & (sf["industry_code"]=="CS100005") & (sf["quarter"]==20243)]
    if len(check) > 0:
        print(f"  [CHECK] 성산1동 제과 2024Q3: sales={check['monthly_sales'].iloc[0]:,.0f}")
    else:
        print(f"  [CHECK] 성산1동 제과 2024Q3: NOT FOUND")

    # Check coverage
    filled_keys = set(zip(sales_filled["dong_code"].astype(str),
                          sales_filled["industry_code"].astype(str)))
    print(f"  Dong x Industry combos: {len(filled_keys)} (was {len(set(zip(sales_raw['dong_code'].astype(str), sales_raw['industry_code'].astype(str))))})")

    # Build timeseries - Before
    print(f"\n  [Baseline - without fill]")
    ts_before = build_timeseries(sales_raw, stores_raw)
    ts_before = impute_guide(ts_before)
    ts_before["pop_per_store"] = np.where(ts_before["store_count"]>0, ts_before["total_pop"]/ts_before["store_count"], 0)
    fc = [c for c in ALL_FEATURES if c in ts_before.columns] + ["pop_per_store"]
    print(f"    timeseries: {ts_before.shape}")

    df_before = train_and_backtest(ts_before, fc, "before")
    combos_before = df_before.groupby(["dong","ind"]).size().reset_index(name="n")
    before_set = set(zip(combos_before["dong"], combos_before["ind"]))

    # Mark estimated rows in filled sales before build_timeseries
    if "is_estimated" not in sales_filled.columns:
        sales_filled["is_estimated"] = 0

    # Build timeseries - After (with low weight for estimated rows)
    ESTIMATED_WEIGHTS = [0.1, 0.2, 0.3]
    for est_w in ESTIMATED_WEIGHTS:
        print(f"\n  [After fill - estimated weight={est_w}]")
        ts_after = build_timeseries(sales_filled, stores_raw)
        ts_after = impute_guide(ts_after)
        ts_after["pop_per_store"] = np.where(ts_after["store_count"]>0, ts_after["total_pop"]/ts_after["store_count"], 0)

        # Merge is_estimated flag back
        sales_est = sales_filled[["dong_code","industry_code","quarter","is_estimated"]].copy()
        sales_est["dong_code"] = sales_est["dong_code"].astype(str)
        sales_est["industry_code"] = sales_est["industry_code"].astype(str)
        ts_after["dong_code"] = ts_after["dong_code"].astype(str)
        ts_after["industry_code"] = ts_after["industry_code"].astype(str)
        ts_after = ts_after.merge(sales_est, on=["dong_code","industry_code","quarter"], how="left")
        ts_after["is_estimated"] = ts_after["is_estimated"].fillna(0)

        # Apply lower weight for estimated rows
        if "sample_weight" in ts_after.columns:
            ts_after.loc[ts_after["is_estimated"]==1, "sample_weight"] *= est_w
        else:
            ts_after["sample_weight"] = 1.0
            ts_after.loc[ts_after["is_estimated"]==1, "sample_weight"] = est_w

        fc2 = [c for c in ALL_FEATURES if c in ts_after.columns] + ["pop_per_store"]
        n_est = (ts_after["is_estimated"]==1).sum()
        print(f"    timeseries: {ts_after.shape}, estimated rows: {n_est}, weight: {est_w}")

        df_after = train_and_backtest(ts_after, fc2, f"w={est_w}")
        if len(df_after) == 0:
            continue
        combos_after = df_after.groupby(["dong","ind"]).size().reset_index(name="n")
        a2, p2 = df_after["actual"].values, df_after["predicted"].values
        print(f"    MAPE={mape(a2,p2):.1f}% MAE={mae(a2,p2):,.0f} R2={r_squared(a2,p2):.4f} combos={len(combos_after)} preds={len(df_after)}")

        # New combos
        after_set = set(zip(combos_after["dong"], combos_after["ind"]))
        new_combos = after_set - before_set
        if new_combos:
            print(f"    New combos ({len(new_combos)}):")
            for dong, ind in sorted(new_combos):
                sub = df_after[(df_after["dong"]==dong) & (df_after["ind"]==ind)]
                if len(sub) > 0:
                    print(f"      {dong} {ind}: MAPE={mape(sub['actual'].values, sub['predicted'].values):.1f}%")

    print(f"\n{'='*90}")
    print("  Summary")
    print(f"{'='*90}")

    a1, p1 = df_before["actual"].values, df_before["predicted"].values
    print(f"  Baseline: MAPE={mape(a1,p1):.1f}% MAE={mae(a1,p1):,.0f} R2={r_squared(a1,p1):.4f} combos={len(combos_before)}")


if __name__ == "__main__":
    main()
