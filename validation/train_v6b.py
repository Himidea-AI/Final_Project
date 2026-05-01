"""v6b: 사전학습(24피처) → 파인튜닝(25피처+트렌드, 부분복사) → 백테스팅."""

import logging
import pickle
import sys
import time

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from models.lstm_forecast.data_prep import (
    ALL_FEATURES,
    build_timeseries,
    load_sales_data,
    load_store_data,
    prepare_sequences,
)
from models.lstm_forecast.model import WEIGHTS_DIR, LSTMForecaster
from validation.accuracy_metrics import mae, mape, r_squared, rmse

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
criterion = nn.MSELoss()

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


def train_loop(model, train_loader, val_loader, optimizer, epochs, patience, label):
    best_val, best_state, wait = float("inf"), None, 0
    for ep in range(epochs):
        model.train()
        for batch in train_loader:
            if len(batch) == 3:
                xb, yb, wb = batch[0].to(device), batch[1].to(device), batch[2].to(device)
                optimizer.zero_grad()
                loss = (wb.unsqueeze(1) * (model(xb) - yb) ** 2).mean()
            else:
                xb, yb = batch[0].to(device), batch[1].to(device)
                optimizer.zero_grad()
                loss = criterion(model(xb), yb)
            loss.backward()
            optimizer.step()
        model.eval()
        vl = sum(criterion(model(xb.to(device)), yb.to(device)).item() for xb, yb in val_loader) / len(val_loader)
        if (ep + 1) % 10 == 0:
            print(f"  [{label}] Epoch {ep + 1}/{epochs} val_loss={vl:.6f}", flush=True)
        if vl < best_val:
            best_val, best_state, wait = vl, {k: v.cpu().clone() for k, v in model.state_dict().items()}, 0
        else:
            wait += 1
            if wait >= patience:
                break
    return best_state, best_val


def main():
    t0 = time.time()

    # === 1. 사전학습 (마포구 전용 피처 제외) ===
    # trend_score: 마포구만 의미있는 트렌드 → 파인튜닝 전용
    # resident_pop: 마포구만 보유 → 파인튜닝 전용
    MAPO_ONLY_FEATURES = {"trend_score", "resident_pop"}
    print(f"=== 사전학습 ({len(ALL_FEATURES) - len(MAPO_ONLY_FEATURES)}피처, 서울 전체) ===", flush=True)
    sales_s = load_sales_data(dong_prefix=None)
    stores_s = load_store_data(dong_prefix=None)
    feat_no_trend = [f for f in ALL_FEATURES if f not in MAPO_ONLY_FEATURES]
    ts_s = build_timeseries(sales_s, stores_s, feat_no_trend)
    feat_cols_s = [c for c in feat_no_trend if c in ts_s.columns]
    print(f"사전학습 피처: {len(feat_cols_s)}개, 데이터: {ts_s.shape}", flush=True)

    X_s, y_s, fs_s, ts_s_scaler, w_s, _ = prepare_sequences(ts_s, window_size=6, feature_cols=feat_cols_s)
    n_val = max(1, int(len(X_s) * 0.2))
    train_s = DataLoader(
        TensorDataset(torch.from_numpy(X_s[:-n_val]), torch.from_numpy(y_s[:-n_val]), torch.from_numpy(w_s[:-n_val])),
        batch_size=128,
        shuffle=True,
    )
    val_s = DataLoader(TensorDataset(torch.from_numpy(X_s[-n_val:]), torch.from_numpy(y_s[-n_val:])), batch_size=128)

    model = LSTMForecaster(input_size=len(feat_cols_s), hidden_size=256, num_layers=2, dropout=0.2).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=0.001, weight_decay=1e-5)
    best_state, best_val = train_loop(model, train_s, val_s, opt, 50, 10, "pretrain")
    model.load_state_dict(best_state)
    pretrain_path = WEIGHTS_DIR / "pretrained_24feat.pt"
    model.save_weights(pretrain_path)
    print(f"사전학습 완료: val_loss={best_val:.6f}, input={len(feat_cols_s)} ({time.time() - t0:.0f}s)", flush=True)

    # === 2. 파인튜닝 (25피처, 트렌드 포함) ===
    print("\n=== 파인튜닝 (25피처, 마포구 + 트렌드) ===", flush=True)
    sales_m = load_sales_data(dong_prefix="11440")
    stores_m = load_store_data(dong_prefix="11440")
    ts_m = build_timeseries(sales_m, stores_m)
    feat_cols_m = [c for c in ALL_FEATURES if c in ts_m.columns]
    print(f"파인튜닝 피처: {len(feat_cols_m)}개, 데이터: {ts_m.shape}", flush=True)

    X_m, y_m, fs_m, ts_m_scaler, w_m, _ = prepare_sequences(ts_m, window_size=6, feature_cols=feat_cols_m)
    n_val_m = max(1, int(len(X_m) * 0.2))
    train_m = DataLoader(
        TensorDataset(
            torch.from_numpy(X_m[:-n_val_m]), torch.from_numpy(y_m[:-n_val_m]), torch.from_numpy(w_m[:-n_val_m])
        ),
        batch_size=32,
        shuffle=True,
    )
    val_m = DataLoader(TensorDataset(torch.from_numpy(X_m[-n_val_m:]), torch.from_numpy(y_m[-n_val_m:])), batch_size=32)

    model2 = LSTMForecaster(input_size=len(feat_cols_m), hidden_size=256, num_layers=2, dropout=0.2).to(device)
    model2.load_weights_partial(pretrain_path)
    print("사전학습 가중치 부분 복사 완료", flush=True)

    # Phase 1: freeze
    model2.freeze_lstm()
    opt_fc = torch.optim.Adam(filter(lambda p: p.requires_grad, model2.parameters()), lr=5e-4)
    train_loop(model2, train_m, val_m, opt_fc, 10, 10, "ft-fc")

    # Phase 2: unfreeze
    model2.unfreeze_lstm()
    opt_all = torch.optim.Adam(model2.parameters(), lr=1e-4)
    best_state2, best_val2 = train_loop(model2, train_m, val_m, opt_all, 50, 10, "ft-all")
    model2.load_state_dict(best_state2)
    model2.save_weights(WEIGHTS_DIR / "finetuned_mapo_v6b.pt")
    print(f"파인튜닝 완료: val_loss={best_val2:.6f} ({time.time() - t0:.0f}s)", flush=True)

    with open(WEIGHTS_DIR / "finetune_v6b_scalers.pkl", "wb") as f:
        pickle.dump({"feature_scaler": fs_m, "target_scaler": ts_m_scaler}, f)

    # === 3. 백테스팅 ===
    print("\n=== 백테스팅 ===", flush=True)
    model2.eval()
    WINDOW = 6
    results = []
    for (dc, ic), group in ts_m.groupby(["dong_code", "industry_code"]):
        group = group.sort_values("quarter")
        if len(group) < WINDOW + 1:
            continue
        for tq in [q for q in group["quarter"].values if q >= 20241]:
            idx = group[group["quarter"] == tq].index[0]
            pos = group.index.get_loc(idx)
            if pos < WINDOW:
                continue
            wd = group.iloc[pos - WINDOW : pos]
            fv = fs_m.transform(wd[feat_cols_m].values.astype(np.float32))
            X = torch.from_numpy(fv).unsqueeze(0).to(device)
            with torch.no_grad():
                ps = model2(X).cpu().numpy()
            pred_log = ts_m_scaler.inverse_transform(ps)[0][0]
            actual_log = group.iloc[pos]["monthly_sales"]
            # dong_name을 데이터에서 직접 가져옴 (DONG_MAP 하드코딩 방지)
            dong_name = group.iloc[pos].get("dong_name", DONG_MAP.get(dc, dc))
            results.append(
                {
                    "dong": dong_name,
                    "ind": IND_MAP.get(ic, ic),
                    "actual": np.expm1(actual_log),
                    "predicted": max(0, np.expm1(pred_log)),
                }
            )

    df = pd.DataFrame(results)
    a, p = df["actual"].values, df["predicted"].values

    print("\n=== v6b: 사전학습24 + 파인튜닝25(트렌드) ===")
    print(
        f"샘플: {len(df)} | MAPE: {mape(a, p):.1f}% | MAE: {mae(a, p):,.0f}원 | RMSE: {rmse(a, p):,.0f}원 | R²: {r_squared(a, p):.4f}"
    )

    print("\n업종별:")
    for ind, grp in sorted(df.groupby("ind"), key=lambda x: mape(x[1]["actual"].values, x[1]["predicted"].values)):
        print(f"  {ind}: {mape(grp['actual'].values, grp['predicted'].values):.1f}%")

    print("\n동별:")
    for dong, grp in sorted(df.groupby("dong"), key=lambda x: mape(x[1]["actual"].values, x[1]["predicted"].values)):
        print(f"  {dong}: {mape(grp['actual'].values, grp['predicted'].values):.1f}%")


if __name__ == "__main__":
    main()
