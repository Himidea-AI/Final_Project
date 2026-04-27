"""Full prediction for all 16 dongs x 10 industries = 160 combinations.

Outputs per combination:
  - Quarterly sales forecast (Q1~Q4 2025)
  - Annual sales estimate
  - Survival rate & risk level
  - BEP months
  - Monthly ROI

Uses optimal config: guide-density + pop_per_store, window=4, hidden=128
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import MinMaxScaler
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models.lstm_forecast.data_prep import (
    ALL_FEATURES,
    SALES_FEATURES,
    build_timeseries,
    load_sales_data,
    load_store_data,
)
from models.lstm_forecast.model import LSTMForecaster

device = torch.device("cpu")
WINDOW, HIDDEN, N_STEPS = 4, 128, 4

# 극단적 MAPE 이상치 조합 제외 (매출 규모 대비 오차율 900%+)
EXCLUDE_COMBOS = {
    ("염리동", "중식"),
    ("성산1동", "제과"),
}

# 예측 신뢰도 낮음 (backtest MAPE 50%+ / 매출 급변·결측·개별점포 이벤트)
LOW_CONFIDENCE_COMBOS = {
    ("신수동", "치킨"),  # 86% — 매출 63% 폭락, 배달수요 감소
    ("성산1동", "양식"),  # 72% — V자 반등, 트렌드 반전
    ("신수동", "패스트푸드"),  # 59% — 매출 41% 하락, 소규모
    ("도화동", "양식"),  # 51% — 6분기 결측 + 스파이크
    ("대흥동", "치킨"),  # 51% — 개별 점포 대박 (CV=102%)
}

DONG_MAP = {
    "11440555": "아현동",
    "11440565": "공덕동",
    "11440585": "도화동",
    "11440590": "용강동",
    "11440600": "대흥동",
    "11440610": "염리동",
    "11440630": "신수동",
    "11440655": "서강동",
    "11440660": "서교동",
    "11440680": "합정동",
    "11440690": "망원1동",
    "11440700": "망원2동",
    "11440710": "연남동",
    "11440720": "성산1동",
    "11440730": "성산2동",
    "11440740": "상암동",
}
IND_MAP = {
    "CS100001": "한식",
    "CS100002": "중식",
    "CS100003": "일식",
    "CS100004": "양식",
    "CS100005": "제과",
    "CS100006": "패스트푸드",
    "CS100007": "치킨",
    "CS100008": "분식",
    "CS100009": "호프",
    "CS100010": "커피",
}

# BEP defaults per industry
BEP_DEFAULTS = {
    "한식": {"initial": 80_000_000, "rent": 2_500_000, "labor": 5_000_000, "variable_rate": 0.35},
    "중식": {"initial": 70_000_000, "rent": 2_300_000, "labor": 4_500_000, "variable_rate": 0.33},
    "일식": {"initial": 100_000_000, "rent": 3_000_000, "labor": 5_500_000, "variable_rate": 0.38},
    "양식": {"initial": 90_000_000, "rent": 2_800_000, "labor": 5_000_000, "variable_rate": 0.35},
    "제과": {"initial": 120_000_000, "rent": 2_500_000, "labor": 4_000_000, "variable_rate": 0.30},
    "패스트푸드": {"initial": 150_000_000, "rent": 3_000_000, "labor": 3_500_000, "variable_rate": 0.32},
    "치킨": {"initial": 80_000_000, "rent": 2_000_000, "labor": 3_500_000, "variable_rate": 0.40},
    "분식": {"initial": 50_000_000, "rent": 1_800_000, "labor": 3_000_000, "variable_rate": 0.30},
    "호프": {"initial": 60_000_000, "rent": 2_200_000, "labor": 4_000_000, "variable_rate": 0.35},
    "커피": {"initial": 100_000_000, "rent": 2_500_000, "labor": 4_000_000, "variable_rate": 0.25},
}


def calc_bep(monthly_revenue, industry):
    """Simple BEP calculation (월 기준, 검증 스크립트 전용)."""
    cfg = BEP_DEFAULTS.get(industry, BEP_DEFAULTS["한식"])
    monthly_fixed = cfg["rent"] + cfg["labor"]
    monthly_variable = monthly_revenue * cfg["variable_rate"]
    monthly_profit = monthly_revenue - monthly_fixed - monthly_variable
    quarterly_profit = monthly_profit * 3
    if quarterly_profit <= 0:
        return {
            "bep_quarters": 999,
            "quarterly_profit": quarterly_profit,
            "initial": cfg["initial"],
            "annual_roi": -100,
        }
    bep_quarters = cfg["initial"] / quarterly_profit
    annual_roi = (quarterly_profit * 4 - cfg["initial"]) / cfg["initial"] * 100
    return {
        "bep_quarters": round(bep_quarters, 1),
        "quarterly_profit": round(quarterly_profit),
        "initial": cfg["initial"],
        "annual_roi": round(annual_roi, 1),
    }


def calc_closure(closure_rate):
    """Estimate closure probability from closure rate."""
    if closure_rate <= 0:
        return 0.15, "safe"
    annual_closure = max(0, min(1, closure_rate / 100))
    if annual_closure <= 0.15:
        return round(annual_closure, 4), "safe"
    elif annual_closure <= 0.30:
        return round(annual_closure, 4), "caution"
    elif annual_closure <= 0.50:
        return round(annual_closure, 4), "warning"
    else:
        return round(annual_closure, 4), "danger"


# Imputation
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
                    _, di = nn_m.kneighbors(row[af].fillna(0).values.reshape(1, -1).astype(float))
                    dv = d.iloc[di.flatten()[0]][col]
            if dv is not None:
                r.at[idx, col] = dv * np.random.normal(1, 0.02)
    return r


def impute_guide(ts):
    df = ts.copy()
    df_f = [f for f in ["total_pop", "store_count"] if f in df.columns]
    gk = ["dong_code", "industry_code"]
    for c in SALES_FEATURES:
        if c in df.columns:
            df = hot_deck(df, c, df_f)
    for c in [
        "store_count",
        "franchise_count",
        "open_count",
        "close_count",
        "total_pop",
        "resident_pop",
        "avg_age",
        "total_households",
    ]:
        if c in df.columns:
            df[c] = df.groupby(gk)[c].transform(lambda x: x.interpolate(method="linear", limit_direction="both"))
            df[c] = df.groupby(gk)[c].transform(lambda x: x.ffill().bfill())
    if "closure_rate" in df.columns:
        df["closure_rate"] = df.groupby(gk)["closure_rate"].transform(
            lambda x: x.interpolate(method="linear", limit_direction="both")
        )
    if "rent_1f" in df.columns:
        df["rent_1f"] = df.groupby("dong_code")["rent_1f"].transform(
            lambda x: x.interpolate(method="linear", limit_direction="both")
        )
        df["rent_1f"] = df.groupby("dong_code")["rent_1f"].transform(lambda x: x.fillna(x.median()))
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
    np.random.seed(42)
    torch.manual_seed(42)

    print("=" * 100)
    print("  Full Prediction: 16 dongs x 10 industries (optimal config)")
    print("=" * 100)

    # Load & prepare
    sales = load_sales_data(dong_prefix="11440")
    stores = load_store_data(dong_prefix="11440")
    ts_raw = build_timeseries(sales, stores)
    ts = impute_guide(ts_raw.copy())
    ts["pop_per_store"] = np.where(ts["store_count"] > 0, ts["total_pop"] / ts["store_count"], 0)
    fc = [c for c in ALL_FEATURES if c in ts.columns] + ["pop_per_store"]

    # Train model on all data (no holdout - this is for prediction, not backtest)
    fs = MinMaxScaler()
    tsc = MinMaxScaler()
    fs.fit(ts[fc].values.astype(np.float32))
    tsc.fit(ts[["monthly_sales"]].values.astype(np.float32))
    X_l, y_l, w_l = [], [], []
    hw = "sample_weight" in ts.columns
    for _, g in ts.groupby(["dong_code", "industry_code"]):
        if len(g) <= WINDOW:
            continue
        fv = fs.transform(g[fc].values.astype(np.float32))
        tv = tsc.transform(g[["monthly_sales"]].values.astype(np.float32))
        wv = g["sample_weight"].values if hw else np.ones(len(g))
        for i in range(len(g) - WINDOW):
            X_l.append(fv[i : i + WINDOW])
            y_l.append(tv[i + WINDOW])
            w_l.append(float(wv[i + WINDOW]))
    X = np.array(X_l, dtype=np.float32)
    y = np.array(y_l, dtype=np.float32)
    w = np.array(w_l, dtype=np.float32)
    nv = max(1, int(len(X) * 0.2))
    tr = DataLoader(
        TensorDataset(torch.from_numpy(X[:-nv]), torch.from_numpy(y[:-nv]), torch.from_numpy(w[:-nv])),
        batch_size=32,
        shuffle=True,
    )
    va = DataLoader(TensorDataset(torch.from_numpy(X[-nv:]), torch.from_numpy(y[-nv:])), batch_size=32)
    model = LSTMForecaster(input_size=X.shape[2], hidden_size=HIDDEN, num_layers=2, dropout=0.2).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)
    crit = nn.MSELoss()
    bv, bs, wt_ = float("inf"), None, 0
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
            wt_ = 0
        else:
            wt_ += 1
            if wt_ >= 10:
                break
    model.load_state_dict(bs)
    model.eval()
    print(f"  Model trained (val_loss={bv:.6f})\n")

    # Predict all combinations
    tidx = fc.index("monthly_sales")
    all_results = []

    for dc in sorted(DONG_MAP.keys()):
        for ic in sorted(IND_MAP.keys()):
            dn = DONG_MAP[dc]
            ind = IND_MAP[ic]

            if (dn, ind) in EXCLUDE_COMBOS:
                continue

            grp = ts[(ts["dong_code"].astype(str) == dc) & (ts["industry_code"].astype(str) == ic)]
            grp = grp.sort_values("quarter")

            if len(grp) < WINDOW:
                continue

            # Get closure rate from latest data
            cr = grp["closure_rate"].iloc[-1] if "closure_rate" in grp.columns else 0

            # Predict next 4 quarters
            recent = grp[fc].tail(WINDOW).values.astype(np.float32)
            seq = fs.transform(recent)
            current_seq = torch.from_numpy(seq).unsqueeze(0)

            preds = []
            with torch.no_grad():
                for step in range(N_STEPS):
                    ps = model(current_seq).cpu().numpy()
                    pred_log = tsc.inverse_transform(ps)[0][0]
                    pred_sales = max(0, float(np.expm1(pred_log)))
                    preds.append(pred_sales)
                    ns = current_seq[0, -1, :].clone()
                    ns[tidx] = float(ps[0][0])
                    current_seq = torch.cat([current_seq[:, 1:, :], ns.unsqueeze(0).unsqueeze(0)], dim=1)

            annual_sales = sum(preds)
            monthly_avg = annual_sales / 12
            closure_rate_val, risk_level = calc_closure(cr)
            bep = calc_bep(monthly_avg, ind)

            confidence = "low" if (dn, ind) in LOW_CONFIDENCE_COMBOS else "high"

            all_results.append(
                {
                    "dong": dn,
                    "ind": ind,
                    "Q1": round(preds[0]),
                    "Q2": round(preds[1]),
                    "Q3": round(preds[2]),
                    "Q4": round(preds[3]),
                    "annual": round(annual_sales),
                    "monthly_avg": round(monthly_avg),
                    "closure": closure_rate_val,
                    "risk": risk_level,
                    "bep_quarters": bep["bep_quarters"],
                    "quarterly_profit": bep["quarterly_profit"],
                    "annual_roi": bep["annual_roi"],
                    "initial_invest": bep["initial"],
                    "confidence": confidence,
                }
            )

    df = pd.DataFrame(all_results)

    # === Print results ===

    # 1. Sales by dong
    print("=" * 100)
    print("  [1] 동별 예상 연매출 (2025)")
    print("=" * 100)
    dong_summary = (
        df.groupby("dong")
        .agg(
            annual_total=("annual", "sum"),
            monthly_avg=("monthly_avg", "mean"),
            avg_closure=("closure", "mean"),
            avg_bep=("bep_quarters", lambda x: x[x < 999].mean() if (x < 999).any() else 999),
        )
        .sort_values("annual_total", ascending=False)
    )

    print(f"  {'dong':<8} {'annual_total':>16} {'monthly_avg':>14} {'closure':>10} {'avg_bep':>10}")
    print("  " + "-" * 62)
    for dong, row in dong_summary.iterrows():
        print(
            f"  {dong:<8} {row['annual_total']:>15,.0f} {row['monthly_avg']:>13,.0f} {row['avg_closure']:>9.1%} {row['avg_bep']:>9.1f}"
        )

    # 2. Sales by industry
    print(f"\n{'=' * 100}")
    print("  [2] 업종별 예상 연매출 (2025)")
    print("=" * 100)
    ind_summary = (
        df.groupby("ind")
        .agg(
            annual_total=("annual", "sum"),
            monthly_avg=("monthly_avg", "mean"),
            avg_closure=("closure", "mean"),
            avg_bep=("bep_quarters", lambda x: x[x < 999].mean() if (x < 999).any() else 999),
            avg_roi=("annual_roi", lambda x: x[x > -100].mean() if (x > -100).any() else -100),
        )
        .sort_values("annual_total", ascending=False)
    )

    print(f"  {'ind':<10} {'annual_total':>16} {'monthly_avg':>14} {'closure':>10} {'avg_bep':>10} {'ROI':>8}")
    print("  " + "-" * 72)
    for ind, row in ind_summary.iterrows():
        print(
            f"  {ind:<10} {row['annual_total']:>15,.0f} {row['monthly_avg']:>13,.0f} {row['avg_closure']:>9.1%} {row['avg_bep']:>9.1f} {row['avg_roi']:>7.1f}%"
        )

    # 3. Full matrix - quarterly sales
    print(f"\n{'=' * 100}")
    print("  [3] 동 x 업종 분기별 예상매출")
    print("=" * 100)
    ind_order = ["한식", "중식", "일식", "양식", "제과", "패스트푸드", "치킨", "분식", "호프", "커피"]
    dong_order = sorted(DONG_MAP.values())

    for ind in ind_order:
        sub = df[df["ind"] == ind].sort_values("annual", ascending=False)
        if len(sub) == 0:
            continue
        print(f"\n  [{ind}]")
        print(
            f"  {'dong':<8} {'Q1':>12} {'Q2':>12} {'Q3':>12} {'Q4':>12} {'annual':>14} {'BEP':>6} {'closure':>10} {'risk':>8}"
        )
        print("  " + "-" * 100)
        for _, r in sub.iterrows():
            print(
                f"  {r['dong']:<8} {r['Q1']:>11,.0f} {r['Q2']:>11,.0f} {r['Q3']:>11,.0f} {r['Q4']:>11,.0f} {r['annual']:>13,.0f} {r['bep_quarters']:>5.1f} {r['closure']:>9.1%} {r['risk']:>8}"
            )

    # 4. Top/Bottom combinations
    print(f"\n{'=' * 100}")
    print("  [4] 매출 상위 10 / 하위 10 조합")
    print("=" * 100)
    df_sorted = df.sort_values("annual", ascending=False)

    print("\n  [상위 10 - 가장 높은 매출]")
    print(f"  {'dong':<8} {'ind':<10} {'annual':>14} {'monthly':>12} {'BEP':>6} {'ROI':>8} {'risk':>8}")
    print("  " + "-" * 72)
    for _, r in df_sorted.head(10).iterrows():
        print(
            f"  {r['dong']:<8} {r['ind']:<10} {r['annual']:>13,.0f} {r['monthly_avg']:>11,.0f} {r['bep_quarters']:>5.1f} {r['annual_roi']:>7.1f}% {r['risk']:>8}"
        )

    print("\n  [하위 10 - 가장 낮은 매출]")
    print(f"  {'dong':<8} {'ind':<10} {'annual':>14} {'monthly':>12} {'BEP':>6} {'ROI':>8} {'risk':>8}")
    print("  " + "-" * 72)
    for _, r in df_sorted.tail(10).iterrows():
        print(
            f"  {r['dong']:<8} {r['ind']:<10} {r['annual']:>13,.0f} {r['monthly_avg']:>11,.0f} {r['bep_quarters']:>5.1f} {r['annual_roi']:>7.1f}% {r['risk']:>8}"
        )

    # 5. BEP analysis
    print(f"\n{'=' * 100}")
    print("  [5] BEP 분석")
    print("=" * 100)
    profitable = df[df["bep_quarters"] < 999]
    unprofitable = df[df["bep_quarters"] >= 999]
    print(f"  흑자 조합: {len(profitable)}개 ({len(profitable) / len(df) * 100:.0f}%)")
    print(f"  적자 조합: {len(unprofitable)}개 ({len(unprofitable) / len(df) * 100:.0f}%)")

    if len(profitable) > 0:
        print("\n  BEP 구간별 분포:")
        for lo, hi, label in [
            (0, 2, "2분기 이내"),
            (2, 4, "2~4분기"),
            (4, 8, "1~2년"),
            (8, 12, "2~3년"),
            (12, 999, "3년 이상"),
        ]:
            cnt = len(profitable[(profitable["bep_quarters"] >= lo) & (profitable["bep_quarters"] < hi)])
            print(f"    {label:<12} {cnt:>3}개")

    # 6. Risk summary
    print(f"\n{'=' * 100}")
    print("  [6] 리스크 등급 분포")
    print("=" * 100)
    for level in ["safe", "caution", "warning", "danger"]:
        cnt = len(df[df["risk"] == level])
        print(f"  {level:<10} {cnt:>3}개 ({cnt / len(df) * 100:.0f}%)")

    # 7. Confidence summary
    print(f"\n{'=' * 100}")
    print("  [7] 예측 신뢰도")
    print("=" * 100)
    high_conf = df[df["confidence"] == "high"]
    low_conf = df[df["confidence"] == "low"]
    print(f"  high (신뢰): {len(high_conf)}개 ({len(high_conf) / len(df) * 100:.0f}%)")
    print(f"  low  (주의): {len(low_conf)}개 ({len(low_conf) / len(df) * 100:.0f}%)")
    if len(low_conf) > 0:
        print("\n  [신뢰도 낮은 조합]")
        print(f"  {'dong':<8} {'ind':<10} {'annual':>14} {'risk':>8} {'사유'}")
        print("  " + "-" * 70)
        reasons = {
            ("신수동", "치킨"): "매출 63% 폭락, 배달수요 감소",
            ("성산1동", "양식"): "V자 반등, 트렌드 반전",
            ("신수동", "패스트푸드"): "매출 41% 하락, 소규모",
            ("도화동", "양식"): "6분기 결측 + 매출 스파이크",
            ("대흥동", "치킨"): "개별 점포 대박 (CV=102%)",
        }
        for _, r in low_conf.iterrows():
            reason = reasons.get((r["dong"], r["ind"]), "")
            print(f"  {r['dong']:<8} {r['ind']:<10} {r['annual']:>13,.0f} {r['risk']:>8}  {reason}")

    # Save to CSV
    csv_path = Path(__file__).parent / "full_prediction_results.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"\n  Results saved to: {csv_path}")
    print(f"  Total combinations: {len(df)}")


if __name__ == "__main__":
    main()
