"""골목상권 신규 피처 효과 테스트

기존 27feat (ALL_FEATURES + pop_per_store) vs
기존 + 골목상권 피처 (생존율, 평균영업기간, 유동인구, 소득, 가구수 등)

dong_industry_detail.py 와 동일한 backtest 구조 사용.
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


def hot_deck(df, col, donors_f):
    r = df.copy()
    dn_col = "dong_name" if "dong_name" in df.columns else None
    if dn_col is None:
        return r
    for q, qdf in r.groupby("quarter"):
        miss = qdf[col].isna() | (qdf[col] == 0)
        if not miss.any():
            continue
        d = qdf[~miss]
        rec = qdf[miss]
        if d.empty:
            continue
        for idx, row in rec.iterrows():
            dn = row.get(dn_col, "")
            dv = None
            for ps, pd_ in [("2동", "1동")]:
                if ps in str(dn):
                    pn = str(dn).replace(ps, pd_)
                    pr = d[d[dn_col] == pn][col]
                    if not pr.empty:
                        dv = pr.values[0]
                        break
            if dv is None:
                af = [f for f in donors_f if f in d.columns]
                if af:
                    nn_m = NearestNeighbors(n_neighbors=1)
                    nn_m.fit(d[af].fillna(0).values)
                    _, di = nn_m.kneighbors(
                        row[af].fillna(0).values.reshape(1, -1).astype(float)
                    )
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
        df["vacancy_rate"] = df["vacancy_rate"].interpolate(
            method="linear", limit_direction="both")
    if "cpi_index" in df.columns:
        df["cpi_index"] = df["cpi_index"].ffill().bfill()
    if "trend_score" in df.columns:
        df["trend_score"] = df["trend_score"].fillna(0)
    feat = [c for c in ALL_FEATURES if c in df.columns]
    df[feat] = df[feat].fillna(0)
    return df


def merge_golmok_features(ts):
    """골목상권 데이터를 기존 timeseries에 병합."""
    golmok_path = Path(__file__).parent.parent / "data" / "processed" / "golmok_merged.csv"
    gm = pd.read_csv(golmok_path)

    # 키 타입 맞추기
    gm["dong_code"] = gm["dong_code"].astype(str)
    gm["industry_code"] = gm["industry_code"].astype(str)
    ts["dong_code"] = ts["dong_code"].astype(str)
    ts["industry_code"] = ts["industry_code"].astype(str)

    # 골목상권 업종별 피처
    ind_feats = ["store_total", "store_normal", "store_franchise"]
    gm_ind = gm[["quarter", "dong_code", "industry_code"] + ind_feats].copy()
    gm_ind = gm_ind.drop_duplicates(subset=["quarter", "dong_code", "industry_code"])

    # 골목상권 동 단위 피처 (floating_pop)
    dong_feats = ["floating_pop"]
    gm_dong = gm[["quarter", "dong_code"] + dong_feats].copy()
    gm_dong = gm_dong.drop_duplicates(subset=["quarter", "dong_code"])

    # 병합
    ts_merged = ts.merge(gm_ind, on=["quarter", "dong_code", "industry_code"], how="left")
    ts_merged = ts_merged.merge(gm_dong, on=["quarter", "dong_code"], how="left")

    new_feats = ind_feats + dong_feats

    # 결측치 보간
    gk = ["dong_code", "industry_code"]
    for feat in new_feats:
        if feat in ts_merged.columns:
            ts_merged[feat] = ts_merged.groupby(gk)[feat].transform(
                lambda x: x.interpolate(method="linear", limit_direction="both"))
            ts_merged[feat] = ts_merged.groupby(gk)[feat].transform(
                lambda x: x.ffill().bfill())
            ts_merged[feat] = ts_merged[feat].fillna(0)

    return ts_merged, new_feats


def run_backtest(ts_df, feat_cols, label):
    np.random.seed(42)
    torch.manual_seed(42)

    fs = MinMaxScaler()
    tsc = MinMaxScaler()
    dt = ts_df[ts_df["quarter"] <= 20234]
    fs.fit(dt[feat_cols].values.astype(np.float32))
    tsc.fit(dt[["monthly_sales"]].values.astype(np.float32))

    X_l, y_l, w_l = [], [], []
    hw = "sample_weight" in dt.columns
    for _, g in dt.groupby(["dong_code", "industry_code"]):
        if len(g) <= WINDOW:
            continue
        fv = fs.transform(g[feat_cols].values.astype(np.float32))
        tv = tsc.transform(g[["monthly_sales"]].values.astype(np.float32))
        wv = g["sample_weight"].values if hw else np.ones(len(g))
        for i in range(len(g) - WINDOW):
            X_l.append(fv[i:i + WINDOW])
            y_l.append(tv[i + WINDOW])
            w_l.append(float(wv[i + WINDOW]))

    X = np.array(X_l, dtype=np.float32)
    y = np.array(y_l, dtype=np.float32)
    w = np.array(w_l, dtype=np.float32)

    nv = max(1, int(len(X) * 0.2))
    tr = DataLoader(TensorDataset(
        torch.from_numpy(X[:-nv]), torch.from_numpy(y[:-nv]),
        torch.from_numpy(w[:-nv])), batch_size=32, shuffle=True)
    va = DataLoader(TensorDataset(
        torch.from_numpy(X[-nv:]), torch.from_numpy(y[-nv:])), batch_size=32)

    model = LSTMForecaster(
        input_size=X.shape[2], hidden_size=HIDDEN,
        num_layers=2, dropout=0.2).to(device)
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
    model.eval()

    # Backtest
    tidx = feat_cols.index("monthly_sales")
    results = []
    test_q = [20241, 20242, 20243, 20244]
    for (dc, ic), g in ts_df.groupby(["dong_code", "industry_code"]):
        g = g.sort_values("quarter")
        tqs = [q for q in g["quarter"].values if q in test_q]
        if len(tqs) < N_STEPS:
            continue
        fi = g[g["quarter"] == tqs[0]].index[0]
        fp = g.index.get_loc(fi)
        if fp < WINDOW:
            continue
        wd = g.iloc[fp - WINDOW:fp]
        fv = fs.transform(wd[feat_cols].values.astype(np.float32))
        seq = torch.from_numpy(fv).unsqueeze(0)
        dn = DONG_MAP.get(str(dc), str(dc))
        ind = IND_MAP.get(str(ic), str(ic))
        for step, q in enumerate(tqs[:N_STEPS]):
            with torch.no_grad():
                ps = model(seq).cpu().numpy()
            pl = tsc.inverse_transform(ps)[0][0]
            al = g.iloc[fp + step]["monthly_sales"]
            results.append({
                "dong": dn, "ind": ind, "step": step + 1,
                "actual": np.expm1(al), "predicted": max(0, np.expm1(pl)),
            })
            ns = seq[0, -1, :].clone()
            ns[tidx] = float(ps[0][0])
            seq = torch.cat([seq[:, 1:, :], ns.unsqueeze(0).unsqueeze(0)], dim=1)

    return pd.DataFrame(results)


def print_results(df, label, feat_count):
    a_all, p_all = df["actual"].values, df["predicted"].values
    print(f"\n{'='*70}")
    print(f"  [{label}] ({feat_count} features)")
    print(f"  전체: MAPE={mape(a_all, p_all):.1f}%  MAE={mae(a_all, p_all):,.0f}  R2={r_squared(a_all, p_all):.4f}  n={len(df)}")
    print(f"{'='*70}")

    # 동별
    print(f"\n  {'동':<8} {'MAPE':>7}")
    print("  " + "-" * 20)
    dong_mapes = {}
    for dong, g in sorted(df.groupby("dong"),
                          key=lambda x: mape(x[1]["actual"].values, x[1]["predicted"].values)):
        a, p = g["actual"].values, g["predicted"].values
        m = mape(a, p)
        dong_mapes[dong] = m
        print(f"  {dong:<8} {m:>6.1f}%")

    # 업종별
    print(f"\n  {'업종':<10} {'MAPE':>7}")
    print("  " + "-" * 22)
    ind_mapes = {}
    for ind, g in sorted(df.groupby("ind"),
                         key=lambda x: mape(x[1]["actual"].values, x[1]["predicted"].values)):
        a, p = g["actual"].values, g["predicted"].values
        m = mape(a, p)
        ind_mapes[ind] = m
        print(f"  {ind:<10} {m:>6.1f}%")

    # 하위 10
    cross = []
    for (dong, ind), g in df.groupby(["dong", "ind"]):
        a, p = g["actual"].values, g["predicted"].values
        cross.append({"dong": dong, "ind": ind, "mape": mape(a, p)})
    cx = pd.DataFrame(cross).sort_values("mape")
    print(f"\n  하위 10 (가장 부정확):")
    print(f"  {'동':<8} {'업종':<10} {'MAPE':>7}")
    print("  " + "-" * 28)
    for _, r in cx.tail(10).iterrows():
        print(f"  {r['dong']:<8} {r['ind']:<10} {r['mape']:>6.1f}%")

    return dong_mapes, ind_mapes, cx


def main():
    print("=" * 70)
    print("  골목상권 피처 개별 효과 테스트")
    print("=" * 70)

    sales = load_sales_data(dong_prefix="11440")
    stores = load_store_data(dong_prefix="11440")
    ts = build_timeseries(sales, stores)
    ts = impute(ts)
    ts["pop_per_store"] = np.where(
        ts["store_count"] > 0, ts["total_pop"] / ts["store_count"], 0)

    # === Baseline ===
    base_fc = [c for c in ALL_FEATURES if c in ts.columns] + ["pop_per_store"]
    print(f"\n  Baseline features: {len(base_fc)}")
    df_base = run_backtest(ts, base_fc, "baseline")
    a_b, p_b = df_base["actual"].values, df_base["predicted"].values
    base_mape = mape(a_b, p_b)
    base_mae = mae(a_b, p_b)
    base_r2 = r_squared(a_b, p_b)
    print(f"  Baseline: MAPE={base_mape:.1f}% MAE={base_mae:,.0f} R2={base_r2:.4f}")

    # 동x업종별 baseline MAPE
    base_cross = {}
    for (dong, ind), g in df_base.groupby(["dong", "ind"]):
        base_cross[(dong, ind)] = mape(g["actual"].values, g["predicted"].values)

    # === 골목상권 피처 병합 ===
    ts_gm, all_new_feats = merge_golmok_features(ts)
    ts_gm["pop_per_store"] = np.where(
        ts_gm["store_count"] > 0, ts_gm["total_pop"] / ts_gm["store_count"], 0)

    # 파생 피처 생성
    ts_gm["franchise_ratio"] = np.where(
        ts_gm["store_total"] > 0,
        ts_gm["store_franchise"] / ts_gm["store_total"], 0)
    ts_gm["normal_ratio"] = np.where(
        ts_gm["store_total"] > 0,
        ts_gm["store_normal"] / ts_gm["store_total"], 0)
    ts_gm["pop_per_store_gm"] = np.where(
        ts_gm["store_total"] > 0,
        ts_gm["floating_pop"] / ts_gm["store_total"], 0)

    # === 개별 피처 테스트 ===
    candidates = all_new_feats + ["franchise_ratio", "normal_ratio", "pop_per_store_gm"]
    results_summary = []

    for feat in candidates:
        print(f"\n  --- Testing: +{feat} ---")
        fc = base_fc + [feat]
        df_test = run_backtest(ts_gm, fc, f"+{feat}")
        a_t, p_t = df_test["actual"].values, df_test["predicted"].values
        m = mape(a_t, p_t)
        ma = mae(a_t, p_t)
        r2 = r_squared(a_t, p_t)
        diff = m - base_mape

        # 하위 10 개선 정도
        worst_improve = 0
        worst_count = 0
        test_cross = {}
        for (dong, ind), g in df_test.groupby(["dong", "ind"]):
            test_cross[(dong, ind)] = mape(g["actual"].values, g["predicted"].values)
        # baseline 하위 10 기준
        sorted_base = sorted(base_cross.items(), key=lambda x: x[1], reverse=True)
        for (dong, ind), bm in sorted_base[:10]:
            tm = test_cross.get((dong, ind), bm)
            if tm < bm - 1:
                worst_improve += bm - tm
                worst_count += 1

        results_summary.append({
            "feat": feat, "mape": m, "mae": ma, "r2": r2,
            "diff": diff, "worst_improve": worst_improve,
            "worst_count": worst_count,
        })
        arrow = "↓개선" if diff < -0.5 else "↑악화" if diff > 0.5 else "=유지"
        print(f"    MAPE={m:.1f}% ({diff:+.1f}%p {arrow}) | 하위10 중 {worst_count}개 개선 (총 {worst_improve:.0f}%p↓)")

    # === 조합 테스트: 개선 피처만 ===
    print(f"\n{'='*70}")
    print("  개별 결과 요약")
    print(f"{'='*70}")
    print(f"\n  {'피처':<20} {'MAPE':>7} {'변화':>8} {'하위개선':>10}")
    print("  " + "-" * 48)
    for r in sorted(results_summary, key=lambda x: x["diff"]):
        print(f"  {r['feat']:<20} {r['mape']:>6.1f}% {r['diff']:>+7.1f}  {r['worst_count']}개/{r['worst_improve']:.0f}%p")

    # 개선 피처만 모아서 조합 테스트
    good_feats = [r["feat"] for r in results_summary if r["diff"] <= 0]
    if good_feats:
        print(f"\n{'='*70}")
        print(f"  조합 테스트: {good_feats}")
        print(f"{'='*70}")
        fc_combo = base_fc + good_feats
        df_combo = run_backtest(ts_gm, fc_combo, "combo")
        combo_dong, combo_ind, combo_cx = print_results(df_combo, f"Baseline + {good_feats}", len(fc_combo))

        # 하위 10 비교
        a_c, p_c = df_combo["actual"].values, df_combo["predicted"].values
        m_c = mape(a_c, p_c)
        print(f"\n  전체 MAPE: {base_mape:.1f}% → {m_c:.1f}% ({m_c - base_mape:+.1f}%p)")
        print(f"\n  하위 10 비교:")
        combo_cross = {}
        for (dong, ind), g in df_combo.groupby(["dong", "ind"]):
            combo_cross[(dong, ind)] = mape(g["actual"].values, g["predicted"].values)
        sorted_base = sorted(base_cross.items(), key=lambda x: x[1], reverse=True)
        print(f"  {'동':<8} {'업종':<10} {'Baseline':>9} {'Combo':>9} {'변화':>8}")
        print("  " + "-" * 48)
        for (dong, ind), bm in sorted_base[:10]:
            cm = combo_cross.get((dong, ind), bm)
            diff = cm - bm
            mark = "↓" if diff < -1 else "↑" if diff > 1 else "="
            print(f"  {dong:<8} {ind:<10} {bm:>8.1f}% {cm:>8.1f}% {diff:>+7.1f} {mark}")
    else:
        print("\n  개선 피처 없음 -- 조합 테스트 스킵")


if __name__ == "__main__":
    main()
