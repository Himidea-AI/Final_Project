"""v9: v6b 기반 + Scheduled Sampling + Multi-step Loss → 자기회귀 오차 누적 개선.

변경점 (v6b → v9):
- 파인튜닝 시 Scheduled Sampling 적용: 학습 중 예측값을 입력에 넣는 비율을 점진적으로 높임
- Multi-step Loss: 4스텝(1년) 자기회귀 예측의 전체 오차를 줄이도록 학습
- 백테스팅: 1스텝 + 4스텝(자기회귀) 두 가지 모두 측정
"""

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
from validation.accuracy_metrics import mae, mape, r_squared

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

WINDOW = 6
N_STEPS = 4  # 4분기(1년) 자기회귀 예측


# ---------------------------------------------------------------------------
# 학습 루프 (기존 v6b 동일)
# ---------------------------------------------------------------------------


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
        with torch.no_grad():
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


# ---------------------------------------------------------------------------
# Multi-step 자기회귀 학습 루프 (Scheduled Sampling)
# ---------------------------------------------------------------------------


def multistep_train_loop(
    model,
    timeseries_df,
    feat_cols,
    feat_scaler,
    tgt_scaler,
    optimizer,
    epochs,
    patience,
    teacher_forcing_start=1.0,
    teacher_forcing_end=0.3,
):
    """N_STEPS 자기회귀 예측을 학습하는 루프.

    Scheduled Sampling: teacher_forcing 비율을 epoch마다 선형으로 줄임.
    - teacher_forcing=1.0: 항상 실제값 입력 (기존 방식)
    - teacher_forcing=0.0: 항상 예측값 입력 (실전과 동일)
    """
    # 그룹별 시퀀스 준비 (동×업종별)
    groups = []
    for (dc, ic), grp in timeseries_df.groupby(["dong_code", "industry_code"]):
        grp = grp.sort_values("quarter")
        if len(grp) < WINDOW + N_STEPS:
            continue
        feat_vals = feat_scaler.transform(grp[feat_cols].values.astype(np.float32))
        tgt_vals = tgt_scaler.transform(grp[["monthly_sales"]].values.astype(np.float32))
        target_idx = feat_cols.index("monthly_sales") if "monthly_sales" in feat_cols else 0
        groups.append((feat_vals, tgt_vals, target_idx))

    if not groups:
        print("  [multistep] 학습 가능한 그룹 없음", flush=True)
        return None, float("inf")

    best_val, best_state, wait = float("inf"), None, 0

    for ep in range(epochs):
        # Scheduled Sampling: 선형 감소
        tf_ratio = teacher_forcing_start - (teacher_forcing_start - teacher_forcing_end) * (ep / max(epochs - 1, 1))

        model.train()
        total_loss = 0.0
        n_samples = 0

        for feat_vals, tgt_vals, target_idx in groups:
            # 슬라이딩 윈도우로 학습 샘플 생성
            for start in range(len(feat_vals) - WINDOW - N_STEPS + 1):
                seq = torch.from_numpy(feat_vals[start : start + WINDOW]).unsqueeze(0).to(device)
                targets = torch.from_numpy(tgt_vals[start + WINDOW : start + WINDOW + N_STEPS]).to(device)

                # N_STEPS 자기회귀 예측
                optimizer.zero_grad()
                preds = []
                current_seq = seq.clone()

                for step in range(N_STEPS):
                    pred = model(current_seq)  # (1, 1)
                    preds.append(pred)

                    # 다음 입력 구성
                    new_step = current_seq[0, -1, :].clone()

                    # Scheduled Sampling: 확률적으로 실제값 or 예측값 사용
                    if step < N_STEPS - 1:
                        if np.random.random() < tf_ratio:
                            # Teacher Forcing: 실제값 사용
                            new_step[target_idx] = float(tgt_vals[start + WINDOW + step][0])
                        else:
                            # Free Running: 예측값 사용
                            new_step[target_idx] = pred.detach().squeeze()

                    new_step = new_step.unsqueeze(0).unsqueeze(0)
                    current_seq = torch.cat([current_seq[:, 1:, :], new_step], dim=1)

                # Multi-step Loss: 뒤쪽 스텝에 가중치를 더 줌 (오차 누적 방지)
                preds_tensor = torch.cat(preds, dim=0)  # (N_STEPS, 1)
                step_weights = torch.tensor([1.0, 1.2, 1.5, 2.0], device=device).unsqueeze(1)
                loss = (step_weights * (preds_tensor - targets) ** 2).mean()

                loss.backward()
                optimizer.step()

                total_loss += loss.item()
                n_samples += 1

        avg_loss = total_loss / max(n_samples, 1)

        if (ep + 1) % 5 == 0:
            print(f"  [multistep] Epoch {ep + 1}/{epochs} loss={avg_loss:.6f} tf={tf_ratio:.2f}", flush=True)

        if avg_loss < best_val:
            best_val, best_state, wait = avg_loss, {k: v.cpu().clone() for k, v in model.state_dict().items()}, 0
        else:
            wait += 1
            if wait >= patience:
                break

    return best_state, best_val


# ---------------------------------------------------------------------------
# 백테스팅 (1스텝 + 4스텝 자기회귀)
# ---------------------------------------------------------------------------


def run_backtest(model, ts_m, feat_cols_m, fs_m, ts_m_scaler):
    model.eval()
    target_idx = feat_cols_m.index("monthly_sales") if "monthly_sales" in feat_cols_m else 0

    results_1step = []
    results_4step = []

    for (dc, ic), group in ts_m.groupby(["dong_code", "industry_code"]):
        group = group.sort_values("quarter")
        if len(group) < WINDOW + N_STEPS:
            continue

        dong_name = group.iloc[-1].get("dong_name", DONG_MAP.get(dc, dc))
        ind_name = IND_MAP.get(ic, ic)

        # --- 1스텝 백테스팅 (기존 방식) ---
        for tq in [q for q in group["quarter"].values if q >= 20241]:
            idx = group[group["quarter"] == tq].index[0]
            pos = group.index.get_loc(idx)
            if pos < WINDOW:
                continue
            wd = group.iloc[pos - WINDOW : pos]
            fv = fs_m.transform(wd[feat_cols_m].values.astype(np.float32))
            X = torch.from_numpy(fv).unsqueeze(0).to(device)
            with torch.no_grad():
                ps = model(X).cpu().numpy()
            pred_log = ts_m_scaler.inverse_transform(ps)[0][0]
            actual_log = group.iloc[pos]["monthly_sales"]
            results_1step.append(
                {
                    "dong": dong_name,
                    "ind": ind_name,
                    "actual": np.expm1(actual_log),
                    "predicted": max(0, np.expm1(pred_log)),
                }
            )

        # --- 4스텝 자기회귀 백테스팅 (실전 방식) ---
        q2024 = [q for q in group["quarter"].values if q >= 20241]
        if len(q2024) < N_STEPS:
            continue

        first_idx = group[group["quarter"] == q2024[0]].index[0]
        first_pos = group.index.get_loc(first_idx)
        if first_pos < WINDOW:
            continue

        wd = group.iloc[first_pos - WINDOW : first_pos]
        fv = fs_m.transform(wd[feat_cols_m].values.astype(np.float32))
        current_seq = torch.from_numpy(fv).unsqueeze(0).to(device)

        for step, tq in enumerate(q2024[:N_STEPS]):
            with torch.no_grad():
                ps = model(current_seq).cpu().numpy()
            pred_log = ts_m_scaler.inverse_transform(ps)[0][0]
            actual_log = group.iloc[first_pos + step]["monthly_sales"]

            results_4step.append(
                {
                    "dong": dong_name,
                    "ind": ind_name,
                    "step": step + 1,
                    "actual": np.expm1(actual_log),
                    "predicted": max(0, np.expm1(pred_log)),
                }
            )

            # 자기회귀: 예측값을 다음 입력에 사용
            new_step = current_seq[0, -1, :].clone()
            new_step[target_idx] = float(ps[0][0])
            new_step = new_step.unsqueeze(0).unsqueeze(0)
            current_seq = torch.cat([current_seq[:, 1:, :], new_step], dim=1)

    return results_1step, results_4step


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------


def main():
    t0 = time.time()

    # === 1. 사전학습 (v6b 동일) ===
    MAPO_ONLY_FEATURES = {"trend_score", "resident_pop"}
    print(f"=== 사전학습 ({len(ALL_FEATURES) - len(MAPO_ONLY_FEATURES)}피처, 서울 전체) ===", flush=True)
    sales_s = load_sales_data(dong_prefix=None)
    stores_s = load_store_data(dong_prefix=None)
    feat_no_trend = [f for f in ALL_FEATURES if f not in MAPO_ONLY_FEATURES]
    ts_s = build_timeseries(sales_s, stores_s, feat_no_trend)
    feat_cols_s = [c for c in feat_no_trend if c in ts_s.columns]
    print(f"사전학습 피처: {len(feat_cols_s)}개, 데이터: {ts_s.shape}", flush=True)

    X_s, y_s, fs_s, ts_s_scaler, w_s = prepare_sequences(ts_s, window_size=WINDOW, feature_cols=feat_cols_s)
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
    print(f"사전학습 완료: val_loss={best_val:.6f} ({time.time() - t0:.0f}s)", flush=True)

    # === 2. 파인튜닝 Phase 1: 기존 방식 (FC만 학습) ===
    print("\n=== 파인튜닝 Phase 1 (FC만, 마포구) ===", flush=True)
    sales_m = load_sales_data(dong_prefix="11440")
    stores_m = load_store_data(dong_prefix="11440")
    ts_m = build_timeseries(sales_m, stores_m)
    feat_cols_m = [c for c in ALL_FEATURES if c in ts_m.columns]
    print(f"파인튜닝 피처: {len(feat_cols_m)}개, 데이터: {ts_m.shape}", flush=True)

    X_m, y_m, fs_m, ts_m_scaler, w_m = prepare_sequences(ts_m, window_size=WINDOW, feature_cols=feat_cols_m)
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

    model2.freeze_lstm()
    opt_fc = torch.optim.Adam(filter(lambda p: p.requires_grad, model2.parameters()), lr=5e-4)
    train_loop(model2, train_m, val_m, opt_fc, 10, 10, "ft-fc")

    # === 3. 파인튜닝 Phase 2: 전체 unfreeze (기존) ===
    print("\n=== 파인튜닝 Phase 2 (전체, 기존 방식) ===", flush=True)
    model2.unfreeze_lstm()
    opt_all = torch.optim.Adam(model2.parameters(), lr=1e-4)
    best_state2, best_val2 = train_loop(model2, train_m, val_m, opt_all, 50, 10, "ft-all")
    model2.load_state_dict(best_state2)
    print(f"Phase 2 완료: val_loss={best_val2:.6f}", flush=True)

    # === 4. 파인튜닝 Phase 3: Multi-step + Scheduled Sampling ===
    print("\n=== 파인튜닝 Phase 3 (Multi-step + Scheduled Sampling) ===", flush=True)
    opt_ms = torch.optim.Adam(model2.parameters(), lr=5e-5, weight_decay=1e-5)
    best_state3, best_val3 = multistep_train_loop(
        model2,
        ts_m,
        feat_cols_m,
        fs_m,
        ts_m_scaler,
        optimizer=opt_ms,
        epochs=30,
        patience=8,
        teacher_forcing_start=0.8,
        teacher_forcing_end=0.2,
    )
    if best_state3 is not None:
        model2.load_state_dict(best_state3)
    print(f"Phase 3 완료: loss={best_val3:.6f} ({time.time() - t0:.0f}s)", flush=True)

    # 가중치 저장
    model2.save_weights(WEIGHTS_DIR / "finetuned_mapo_v9.pt")
    with open(WEIGHTS_DIR / "finetune_v9_scalers.pkl", "wb") as f:
        pickle.dump({"feature_scaler": fs_m, "target_scaler": ts_m_scaler}, f)

    # === 5. 백테스팅 ===
    print("\n=== 백테스팅 ===", flush=True)
    results_1step, results_4step = run_backtest(model2, ts_m, feat_cols_m, fs_m, ts_m_scaler)

    # 1스텝 결과
    df1 = pd.DataFrame(results_1step)
    a1, p1 = df1["actual"].values, df1["predicted"].values
    print("\n=== 1스텝 (직전 실데이터 기반) ===")
    print(f"샘플: {len(df1)} | MAPE: {mape(a1, p1):.1f}% | MAE: {mae(a1, p1):,.0f}원 | R²: {r_squared(a1, p1):.4f}")

    # 4스텝 자기회귀 결과
    df4 = pd.DataFrame(results_4step)
    a4, p4 = df4["actual"].values, df4["predicted"].values
    print("\n=== 4스텝 자기회귀 (실전 방식) ===")
    print(f"샘플: {len(df4)} | MAPE: {mape(a4, p4):.1f}% | MAE: {mae(a4, p4):,.0f}원 | R²: {r_squared(a4, p4):.4f}")

    # 스텝별 MAPE
    print("\n스텝별 MAPE:")
    for step in range(1, N_STEPS + 1):
        ds = df4[df4["step"] == step]
        if len(ds) > 0:
            print(f"  Q{step}: {mape(ds['actual'].values, ds['predicted'].values):.1f}%")

    # 업종별 (4스텝)
    print("\n업종별 MAPE (4스텝):")
    for ind, grp in sorted(df4.groupby("ind"), key=lambda x: mape(x[1]["actual"].values, x[1]["predicted"].values)):
        print(f"  {ind}: {mape(grp['actual'].values, grp['predicted'].values):.1f}%")

    # 동별 (4스텝)
    print("\n동별 MAPE (4스텝):")
    for dong, grp in sorted(df4.groupby("dong"), key=lambda x: mape(x[1]["actual"].values, x[1]["predicted"].values)):
        print(f"  {dong}: {mape(grp['actual'].values, grp['predicted'].values):.1f}%")


if __name__ == "__main__":
    main()
