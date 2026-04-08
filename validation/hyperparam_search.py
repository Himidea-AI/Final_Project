"""하이퍼파라미터 튜닝 실험 — DB 없이 CSV 직접 로드."""

import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.preprocessing import MinMaxScaler
from torch.utils.data import DataLoader, TensorDataset

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

SALES_FEATURES = [
    "monthly_sales", "monthly_count", "weekday_sales", "weekend_sales",
    "male_sales", "female_sales", "age_10_sales", "age_20_sales",
    "age_30_sales", "age_40_sales", "age_50_sales", "age_60_above_sales",
]
STORE_FEATURES = ["store_count", "franchise_count"]
EXTRA_FEATURES = ["total_pop", "cpi_index"]
ALL_FEATURES = SALES_FEATURES + STORE_FEATURES + EXTRA_FEATURES

SALES_RENAME = {
    "STDR_YYQU_CD": "quarter", "행정동코드": "dong_code", "행정동명": "dong_name",
    "SVC_INDUTY_CD": "industry_code", "SVC_INDUTY_CD_NM": "industry_name",
    "THSMON_SELNG_AMT": "monthly_sales", "THSMON_SELNG_CO": "monthly_count",
    "MDWK_SELNG_AMT": "weekday_sales", "WKEND_SELNG_AMT": "weekend_sales",
    "ML_SELNG_AMT": "male_sales", "FML_SELNG_AMT": "female_sales",
    "AGRDE_10_SELNG_AMT": "age_10_sales", "AGRDE_20_SELNG_AMT": "age_20_sales",
    "AGRDE_30_SELNG_AMT": "age_30_sales", "AGRDE_40_SELNG_AMT": "age_40_sales",
    "AGRDE_50_SELNG_AMT": "age_50_sales", "AGRDE_60_ABOVE_SELNG_AMT": "age_60_above_sales",
}
STORES_RENAME = {
    "STDR_YYQU_CD": "quarter", "행정동코드": "dong_code", "행정동명": "dong_name",
    "SVC_INDUTY_CD": "industry_code", "SVC_INDUTY_CD_NM": "industry_name",
    "STOR_CO": "store_count", "FRC_STOR_CO": "franchise_count",
}


def load_and_build(dong_prefix=None):
    """CSV에서 직접 로드 + 피처 구성 + 로그 변환."""
    # 매출
    if dong_prefix:
        s = pd.read_csv(DATA_DIR / "district_sales.csv", encoding="utf-8-sig", dtype=str)
    else:
        s = pd.read_csv(DATA_DIR / "seoul_district_sales.csv", encoding="utf-8-sig", dtype=str)
    s = s.rename(columns={k: v for k, v in SALES_RENAME.items() if k in s.columns})
    for c in SALES_FEATURES + ["quarter"]:
        if c in s.columns:
            s[c] = pd.to_numeric(s[c], errors="coerce")
    if dong_prefix:
        s = s[s["dong_code"].astype(str).str.startswith(dong_prefix)]

    # 점포
    if dong_prefix:
        st = pd.read_csv(DATA_DIR / "district_stores.csv", encoding="utf-8-sig", dtype=str)
    else:
        st = pd.read_csv(DATA_DIR / "seoul_district_stores.csv", encoding="utf-8-sig", dtype=str)
    st = st.rename(columns={k: v for k, v in STORES_RENAME.items() if k in st.columns})
    for c in STORE_FEATURES + ["quarter"]:
        if c in st.columns:
            st[c] = pd.to_numeric(st[c], errors="coerce")
    if dong_prefix:
        st = st[st["dong_code"].astype(str).str.startswith(dong_prefix)]

    # 병합
    merge_keys = [c for c in ["quarter", "dong_code", "industry_code"] if c in s.columns and c in st.columns]
    store_cols = [c for c in STORE_FEATURES if c in st.columns]
    df = s.merge(st[merge_keys + store_cols], on=merge_keys, how="left") if merge_keys else s

    # 유동인구
    pop = pd.read_csv(DATA_DIR / "seoul_population_quarterly.csv", dtype={"dong_code": str})
    df = df.merge(pop[["quarter", "dong_code", "total_pop"]], on=["quarter", "dong_code"], how="left")

    # CPI
    cpi = pd.read_csv(DATA_DIR / "cpi_dining_quarterly.csv")
    df = df.merge(cpi[["quarter", "cpi_index"]], on="quarter", how="left")

    # 결측
    feat_cols = [c for c in ALL_FEATURES if c in df.columns]
    df[feat_cols] = df[feat_cols].fillna(0)

    # 로그 변환
    for c in [x for x in SALES_FEATURES if x in df.columns]:
        df[c] = np.log1p(df[c].clip(lower=0))

    df = df.sort_values(["dong_code", "industry_code", "quarter"]).reset_index(drop=True)
    return df


def make_sequences(df, window_size, feature_cols, target_col="monthly_sales"):
    """시퀀스 + 스케일러 생성."""
    fs = MinMaxScaler()
    ts = MinMaxScaler()
    all_f = df[feature_cols].values.astype(np.float32)
    all_t = df[[target_col]].values.astype(np.float32)
    fs.fit(all_f)
    ts.fit(all_t)

    X_list, y_list = [], []
    for _, grp in df.groupby(["dong_code", "industry_code"]):
        if len(grp) <= window_size:
            continue
        fv = fs.transform(grp[feature_cols].values.astype(np.float32))
        tv = ts.transform(grp[[target_col]].values.astype(np.float32))
        for i in range(len(grp) - window_size):
            X_list.append(fv[i:i + window_size])
            y_list.append(tv[i + window_size])
    return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.float32), fs, ts


class LSTMModel(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, dropout):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=dropout if num_layers > 1 else 0)
        self.fc = nn.Linear(hidden_size, 1)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])

    def freeze_lstm(self):
        for p in self.lstm.parameters():
            p.requires_grad = False

    def unfreeze_lstm(self):
        for p in self.lstm.parameters():
            p.requires_grad = True


def run_experiment(ts_seoul, ts_mapo, feature_cols, hidden_size, num_layers, window_size, dropout, lr):
    """1회 실험."""
    X_s, y_s, _, _ = make_sequences(ts_seoul, window_size, feature_cols)
    nv = max(1, int(len(X_s) * 0.2))
    tl_s = DataLoader(TensorDataset(torch.from_numpy(X_s[:-nv]), torch.from_numpy(y_s[:-nv])), batch_size=64, shuffle=True)
    vl_s = DataLoader(TensorDataset(torch.from_numpy(X_s[-nv:]), torch.from_numpy(y_s[-nv:])), batch_size=64)

    model = LSTMModel(X_s.shape[2], hidden_size, num_layers, dropout).to(device)
    crit = nn.MSELoss()
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-5)

    # Pretrain
    bv, bs, w = float("inf"), None, 0
    for _ in range(30):
        model.train()
        for xb, yb in tl_s:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad(); crit(model(xb), yb).backward(); opt.step()
        model.eval()
        v = sum(crit(model(xb.to(device)), yb.to(device)).item() for xb, yb in vl_s) / len(vl_s)
        if v < bv: bv, bs, w = v, {k: v.cpu().clone() for k, v in model.state_dict().items()}, 0
        else:
            w += 1
            if w >= 7: break
    model.load_state_dict(bs)

    # Finetune
    X_m, y_m, fs_m, ts_m = make_sequences(ts_mapo, window_size, feature_cols)
    nvm = max(1, int(len(X_m) * 0.2))
    tl_m = DataLoader(TensorDataset(torch.from_numpy(X_m[:-nvm]), torch.from_numpy(y_m[:-nvm])), batch_size=32, shuffle=True)
    vl_m = DataLoader(TensorDataset(torch.from_numpy(X_m[-nvm:]), torch.from_numpy(y_m[-nvm:])), batch_size=32)

    model.freeze_lstm()
    opt2 = torch.optim.Adam(filter(lambda p: p.requires_grad, model.parameters()), lr=lr * 0.5)
    for _ in range(10):
        model.train()
        for xb, yb in tl_m:
            xb, yb = xb.to(device), yb.to(device)
            opt2.zero_grad(); crit(model(xb), yb).backward(); opt2.step()

    model.unfreeze_lstm()
    opt3 = torch.optim.Adam(model.parameters(), lr=lr * 0.1)
    bv2, bs2, w2 = float("inf"), None, 0
    for _ in range(40):
        model.train()
        for xb, yb in tl_m:
            xb, yb = xb.to(device), yb.to(device)
            opt3.zero_grad(); crit(model(xb), yb).backward(); opt3.step()
        model.eval()
        v = sum(crit(model(xb.to(device)), yb.to(device)).item() for xb, yb in vl_m) / len(vl_m)
        if v < bv2: bv2, bs2, w2 = v, {k: v.cpu().clone() for k, v in model.state_dict().items()}, 0
        else:
            w2 += 1
            if w2 >= 7: break
    model.load_state_dict(bs2)
    model.eval()

    # Backtest
    results = []
    for (dc, ic), grp in ts_mapo.groupby(["dong_code", "industry_code"]):
        grp = grp.sort_values("quarter")
        if len(grp) < window_size + 1: continue
        for tq in [q for q in grp["quarter"].values if q >= 20241]:
            idx = grp[grp["quarter"] == tq].index[0]
            pos = grp.index.get_loc(idx)
            if pos < window_size: continue
            wd = grp.iloc[pos - window_size:pos]
            fv = fs_m.transform(wd[feature_cols].values.astype(np.float32))
            X = torch.from_numpy(fv).unsqueeze(0).to(device)
            with torch.no_grad():
                ps = model(X).cpu().numpy()
            pred = np.expm1(ts_m.inverse_transform(ps)[0][0])
            actual = np.expm1(grp.iloc[pos]["monthly_sales"])
            results.append({"actual": actual, "predicted": max(0, pred)})

    if not results: return None
    df = pd.DataFrame(results)
    a, p = df["actual"].values, df["predicted"].values
    from validation.accuracy_metrics import mape, mae, r_squared
    return {"mape": round(mape(a, p), 1), "mae": round(mae(a, p), 0), "r2": round(r_squared(a, p), 4)}


if __name__ == "__main__":
    print(f"Device: {device}")
    print("데이터 로드 중...")
    ts_seoul = load_and_build(dong_prefix=None)
    ts_mapo = load_and_build(dong_prefix="11440")
    feature_cols = [c for c in ALL_FEATURES if c in ts_mapo.columns]
    print(f"피처: {len(feature_cols)}개, 서울: {len(ts_seoul)}행, 마포: {len(ts_mapo)}행\n")

    EXPERIMENTS = [
        (64, 2, 6, 0.2, 0.001),
        (128, 2, 6, 0.2, 0.001),
        (256, 2, 6, 0.2, 0.001),
        (128, 3, 6, 0.2, 0.001),
        (128, 2, 8, 0.2, 0.001),
        (128, 2, 4, 0.2, 0.001),
        (128, 2, 6, 0.1, 0.001),
        (128, 2, 6, 0.3, 0.001),
        (128, 2, 6, 0.2, 0.0005),
        (128, 2, 6, 0.2, 0.002),
        (128, 3, 8, 0.2, 0.0005),
        (256, 2, 8, 0.1, 0.001),
    ]

    print(f"총 {len(EXPERIMENTS)}개 실험 시작\n")
    all_results = []

    for i, (h, l, w, d, lr) in enumerate(EXPERIMENTS):
        t0 = time.time()
        label = f"h={h} l={l} w={w} d={d} lr={lr}"
        try:
            r = run_experiment(ts_seoul, ts_mapo, feature_cols, h, l, w, d, lr)
            el = time.time() - t0
            if r:
                r["config"] = label
                all_results.append(r)
                print(f"[{i+1:2d}/{len(EXPERIMENTS)}] {label} | MAPE={r['mape']}% MAE={r['mae']:,.0f} R2={r['r2']} ({el:.0f}s)")
        except Exception as e:
            print(f"[{i+1:2d}/{len(EXPERIMENTS)}] {label} | ERROR: {e} ({time.time()-t0:.0f}s)")

    print("\n=== 결과 정렬 (MAPE 기준) ===")
    for r in sorted(all_results, key=lambda x: x["mape"]):
        print(f"  MAPE={r['mape']:5.1f}% | MAE={r['mae']:>15,.0f}원 | R2={r['r2']} | {r['config']}")
