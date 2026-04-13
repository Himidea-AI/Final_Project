"""검증 전략 + 결측치 처리 방식 비교 실험

3가지 조합 비교:
  A. Fixed Origin (2019~2023 학습 → 2024 테스트) + fillna(0) -기존 방식
  B. Expanding Window + Hot Deck Imputation
  C. TimeSeriesSplit + Hot Deck Imputation

각 조합에서 MAPE, MAE, R² 측정하여 표로 비교.
"""

import logging
import pickle
import sys
import time
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
from validation.accuracy_metrics import mae, mape, r_squared, rmse

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
criterion = nn.MSELoss()

WINDOW = 6
N_STEPS = 4
HIDDEN_SIZE = 256
NUM_LAYERS = 2
DROPOUT = 0.2

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

# 명시적 페어링 (도메인 지식)
DONG_PAIR = {"망원2동": "망원1동", "성산2동": "성산1동"}


# ===========================================================================
# 1. Hot Deck Imputation (명시적 페어링 + KNN)
# ===========================================================================


def hot_deck_impute(df: pd.DataFrame, target_col: str, donor_features: list[str],
                    density_scale: bool = False) -> pd.DataFrame:
    """분기별로 유사 동에서 결측값을 차용 (명시적 페어링 우선 + KNN 폴백).

    Parameters
    ----------
    density_scale : bool
        True면 밀도 기반 보정 적용: (donor 매출 / donor 점포수) * recipient 점포수
    """
    result_df = df.copy()

    dong_name_col = "dong_name" if "dong_name" in df.columns else None
    if dong_name_col is None:
        return result_df

    has_store = "store_count" in df.columns and density_scale

    for q, qdf in result_df.groupby("quarter"):
        missing_mask = qdf[target_col].isna() | (qdf[target_col] == 0)
        if not missing_mask.any():
            continue

        donors = qdf[~missing_mask]
        recipients = qdf[missing_mask]

        if donors.empty:
            continue

        for idx, row in recipients.iterrows():
            current_dong = row[dong_name_col]
            donor_val = None
            donor_store = None

            # (A) 명시적 페어링 시도
            if current_dong in DONG_PAIR:
                donor_dong = DONG_PAIR[current_dong]
                donor_rows = donors[donors[dong_name_col] == donor_dong]
                if not donor_rows.empty:
                    donor_val = donor_rows[target_col].values[0]
                    if has_store:
                        donor_store = donor_rows["store_count"].values[0]

            # (B) KNN Hot Deck (페어링 실패 시)
            if donor_val is None:
                avail_feats = [f for f in donor_features if f in donors.columns]
                if not avail_feats:
                    continue
                donor_vals_arr = donors[avail_feats].fillna(0).values
                recip_vals = row[avail_feats].fillna(0).values.reshape(1, -1)
                nn_model = NearestNeighbors(n_neighbors=1)
                nn_model.fit(donor_vals_arr)
                _, d_idx = nn_model.kneighbors(recip_vals.astype(float))
                matched = donors.iloc[d_idx.flatten()[0]]
                donor_val = matched[target_col]
                if has_store:
                    donor_store = matched["store_count"]

            # 밀도 기반 보정: (donor 매출 / donor 점포수) * recipient 점포수
            if has_store and donor_store and donor_store > 0:
                recip_store = row["store_count"]
                if recip_store > 0 and not np.isnan(recip_store):
                    density = donor_val / donor_store
                    donor_val = density * recip_store

            # ±2% 가우시안 노이즈
            noise = np.random.normal(1, 0.02)
            result_df.at[idx, target_col] = donor_val * noise

    return result_df


def apply_fillna_zero(ts_df: pd.DataFrame) -> pd.DataFrame:
    """기존 방식: 전체 fillna(0)."""
    df = ts_df.copy()
    feat_available = [c for c in ALL_FEATURES if c in df.columns]
    df[feat_available] = df[feat_available].fillna(0)
    return df


def apply_feature_guide(ts_df: pd.DataFrame) -> pd.DataFrame:
    """피처별 최적 가이드 적용 (Hot Deck + interpolate + ffill + median)."""
    df = ts_df.copy()
    donor_features = ["total_pop", "store_count"]
    donor_features = [f for f in donor_features if f in df.columns]

    # [1] 매출 관련: Hybrid Hot Deck + 밀도 기반 보정
    for col in SALES_FEATURES:
        if col in df.columns:
            df = hot_deck_impute(df, col, donor_features, density_scale=True)

    # [2] 점포수, 인구: 그룹별 시간 보간 → ffill → bfill (변화 느린 피처)
    ffill_cols = ["store_count", "franchise_count", "open_count", "close_count",
                  "total_pop", "resident_pop", "avg_age", "total_households"]
    for col in ffill_cols:
        if col in df.columns:
            df[col] = df.groupby(["dong_code", "industry_code"])[col].transform(
                lambda x: x.interpolate(method="linear", limit_direction="both")
            )
            df[col] = df.groupby(["dong_code", "industry_code"])[col].transform(
                lambda x: x.ffill().bfill()
            )

    # [3] 폐업률: 그룹별 시간 보간
    if "closure_rate" in df.columns:
        df["closure_rate"] = df.groupby(["dong_code", "industry_code"])["closure_rate"].transform(
            lambda x: x.interpolate(method="linear", limit_direction="both")
        )

    # [4] 임대료: 동별 중앙값 (시간에 따라 다를 수 있으므로 보간 후 중앙값 폴백)
    if "rent_1f" in df.columns:
        df["rent_1f"] = df.groupby("dong_code")["rent_1f"].transform(
            lambda x: x.interpolate(method="linear", limit_direction="both")
        )
        df["rent_1f"] = df.groupby("dong_code")["rent_1f"].transform(
            lambda x: x.fillna(x.median())
        )

    # [5] 공실률: 전체 선형 보간
    if "vacancy_rate" in df.columns:
        df["vacancy_rate"] = df["vacancy_rate"].interpolate(method="linear", limit_direction="both")

    # [6] CPI: Forward Fill (거시지표, 지역 무관)
    if "cpi_index" in df.columns:
        df["cpi_index"] = df["cpi_index"].ffill().bfill()

    # [7] 트렌드: 0 유지 가능 (없음 = 0)
    if "trend_score" in df.columns:
        df["trend_score"] = df["trend_score"].fillna(0)

    # [8] 나머지 잔여 결측 → 0
    feat_available = [c for c in ALL_FEATURES if c in df.columns]
    df[feat_available] = df[feat_available].fillna(0)

    return df


# ===========================================================================
# 2. 시퀀스 생성 (시간 기반 분할 지원)
# ===========================================================================


def make_sequences(ts_df: pd.DataFrame, feat_cols: list[str], max_quarter: int | None = None):
    """시계열 → LSTM 시퀀스. max_quarter 이하 데이터만 사용."""
    df = ts_df.copy()
    if max_quarter is not None:
        df = df[df["quarter"] <= max_quarter]

    feature_scaler = MinMaxScaler()
    target_scaler = MinMaxScaler()

    all_features = df[feat_cols].values.astype(np.float32)
    all_targets = df[["monthly_sales"]].values.astype(np.float32)

    feature_scaler.fit(all_features)
    target_scaler.fit(all_targets)

    X_list, y_list, w_list = [], [], []
    has_weight = "sample_weight" in df.columns

    for _, group in df.groupby(["dong_code", "industry_code"]):
        if len(group) <= WINDOW:
            continue
        feat_vals = feature_scaler.transform(group[feat_cols].values.astype(np.float32))
        tgt_vals = target_scaler.transform(group[["monthly_sales"]].values.astype(np.float32))
        weights = group["sample_weight"].values if has_weight else np.ones(len(group))

        for i in range(len(group) - WINDOW):
            X_list.append(feat_vals[i: i + WINDOW])
            y_list.append(tgt_vals[i + WINDOW])
            w_list.append(float(weights[i + WINDOW]))

    if not X_list:
        return None, None, None, None, None

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.float32)
    w = np.array(w_list, dtype=np.float32)
    return X, y, feature_scaler, target_scaler, w


# ===========================================================================
# 3. 학습 루프
# ===========================================================================


def train_model(X_train, y_train, w_train, X_val, y_val, input_size, epochs=50, patience=10, label="train"):
    """모델 학습 후 best state 반환."""
    train_ds = TensorDataset(
        torch.from_numpy(X_train), torch.from_numpy(y_train), torch.from_numpy(w_train)
    )
    val_ds = TensorDataset(torch.from_numpy(X_val), torch.from_numpy(y_val))
    train_loader = DataLoader(train_ds, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=32)

    model = LSTMForecaster(input_size=input_size, hidden_size=HIDDEN_SIZE,
                           num_layers=NUM_LAYERS, dropout=DROPOUT).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)

    best_val, best_state, wait = float("inf"), None, 0
    for ep in range(epochs):
        model.train()
        for batch in train_loader:
            xb, yb, wb = batch[0].to(device), batch[1].to(device), batch[2].to(device)
            optimizer.zero_grad()
            loss = (wb.unsqueeze(1) * (model(xb) - yb) ** 2).mean()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

        model.eval()
        with torch.no_grad():
            vl = sum(criterion(model(xb.to(device)), yb.to(device)).item()
                     for xb, yb in val_loader) / max(len(val_loader), 1)

        if (ep + 1) % 10 == 0:
            print(f"  [{label}] Epoch {ep + 1}/{epochs} val_loss={vl:.6f}", flush=True)

        if vl < best_val:
            best_val = vl
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            wait = 0
        else:
            wait += 1
            if wait >= patience:
                break

    model.load_state_dict(best_state)
    return model, best_val


# ===========================================================================
# 4. 백테스트 (4스텝 자기회귀)
# ===========================================================================


def backtest_autoregressive(model, ts_df, feat_cols, feat_scaler, tgt_scaler, test_quarters):
    """지정된 테스트 분기에 대해 4스텝 자기회귀 백테스트."""
    model.eval()
    target_idx = feat_cols.index("monthly_sales") if "monthly_sales" in feat_cols else 0
    results = []

    for (dc, ic), group in ts_df.groupby(["dong_code", "industry_code"]):
        group = group.sort_values("quarter")
        test_q = [q for q in group["quarter"].values if q in test_quarters]
        if len(test_q) < N_STEPS:
            continue

        first_idx = group[group["quarter"] == test_q[0]].index[0]
        first_pos = group.index.get_loc(first_idx)
        if first_pos < WINDOW:
            continue

        wd = group.iloc[first_pos - WINDOW: first_pos]
        fv = feat_scaler.transform(wd[feat_cols].values.astype(np.float32))
        current_seq = torch.from_numpy(fv).unsqueeze(0).to(device)

        dong_name = group.iloc[-1].get("dong_name", DONG_MAP.get(dc, dc))
        ind_name = IND_MAP.get(ic, ic)

        for step, tq in enumerate(test_q[:N_STEPS]):
            with torch.no_grad():
                ps = model(current_seq).cpu().numpy()
            pred_log = tgt_scaler.inverse_transform(ps)[0][0]
            actual_log = group.iloc[first_pos + step]["monthly_sales"]

            results.append({
                "dong": dong_name, "ind": ind_name, "step": step + 1,
                "quarter": tq,
                "actual": np.expm1(actual_log),
                "predicted": max(0, np.expm1(pred_log)),
            })

            new_step = current_seq[0, -1, :].clone()
            new_step[target_idx] = float(ps[0][0])
            new_step = new_step.unsqueeze(0).unsqueeze(0)
            current_seq = torch.cat([current_seq[:, 1:, :], new_step], dim=1)

    return pd.DataFrame(results)


# ===========================================================================
# 5. 실험 실행기
# ===========================================================================


def run_experiment_fixed_origin(ts_df, feat_cols, label="Fixed+fillna(0)"):
    """기존 방식: 2024년 이전 학습, 2024년 테스트."""
    print(f"\n{'='*60}")
    print(f"  실험: {label}")
    print(f"{'='*60}")

    # 학습 데이터: 2024년 이전
    train_cutoff = 20241  # 20241 미포함
    X, y, fs, ts_scaler, w = make_sequences(ts_df, feat_cols, max_quarter=20234)
    if X is None:
        print("  시퀀스 생성 실패")
        return None

    n_val = max(1, int(len(X) * 0.2))
    model, val_loss = train_model(
        X[:-n_val], y[:-n_val], w[:-n_val], X[-n_val:], y[-n_val:],
        input_size=X.shape[2], label=label
    )

    # 전체 시계열에 대해 스케일러 재적합 (테스트 데이터 포함)
    test_quarters = [20241, 20242, 20243, 20244]
    df_result = backtest_autoregressive(model, ts_df, feat_cols, fs, ts_scaler, test_quarters)

    return df_result


def run_experiment_expanding_window(ts_df, feat_cols, label="Expanding+HotDeck"):
    """Expanding Window: 점진적으로 학습 데이터 확장."""
    print(f"\n{'='*60}")
    print(f"  실험: {label}")
    print(f"{'='*60}")

    # Fold 정의: test_year별로 확장
    folds = [
        {"train_max": 20214, "test_quarters": [20221, 20222, 20223, 20224], "name": "2022"},
        {"train_max": 20224, "test_quarters": [20231, 20232, 20233, 20234], "name": "2023"},
        {"train_max": 20234, "test_quarters": [20241, 20242, 20243, 20244], "name": "2024"},
    ]

    all_results = []
    fold_metrics = []

    for fold in folds:
        print(f"\n  --- Fold: ~{fold['name']} ---")
        X, y, fs, ts_scaler, w = make_sequences(ts_df, feat_cols, max_quarter=fold["train_max"])
        if X is None:
            print(f"  Fold {fold['name']} 시퀀스 생성 실패")
            continue

        n_val = max(1, int(len(X) * 0.2))
        model, val_loss = train_model(
            X[:-n_val], y[:-n_val], w[:-n_val], X[-n_val:], y[-n_val:],
            input_size=X.shape[2], label=f"EW-{fold['name']}"
        )

        df_result = backtest_autoregressive(
            model, ts_df, feat_cols, fs, ts_scaler, fold["test_quarters"]
        )
        if len(df_result) > 0:
            a, p = df_result["actual"].values, df_result["predicted"].values
            fold_metrics.append({
                "fold": fold["name"],
                "mape": mape(a, p), "mae": mae(a, p),
                "r2": r_squared(a, p), "n": len(df_result),
            })
            all_results.append(df_result)

    if fold_metrics:
        print("\n  [Fold별 결과]")
        for fm in fold_metrics:
            print(f"    {fm['fold']}: MAPE={fm['mape']:.1f}% MAE={fm['mae']:,.0f} R²={fm['r2']:.4f} (n={fm['n']})")

    return pd.concat(all_results, ignore_index=True) if all_results else None, fold_metrics


def run_experiment_tssplit(ts_df, feat_cols, label="TSsplit+HotDeck"):
    """TimeSeriesSplit: 시간순 K-Fold."""
    print(f"\n{'='*60}")
    print(f"  실험: {label}")
    print(f"{'='*60}")

    # 분기 목록
    all_quarters = sorted(ts_df["quarter"].unique())
    n_quarters = len(all_quarters)

    # 3-Fold TimeSeriesSplit (최소 학습 8분기, 테스트 4분기)
    n_test = 4  # 4분기(1년)씩 테스트
    folds = []
    for i in range(3):
        test_start_idx = n_quarters - (3 - i) * n_test
        if test_start_idx < 8:  # 최소 8분기 학습
            continue
        train_quarters = all_quarters[:test_start_idx]
        test_quarters = all_quarters[test_start_idx:test_start_idx + n_test]
        folds.append({
            "train_max": train_quarters[-1],
            "test_quarters": test_quarters,
            "name": f"Fold{i + 1}({test_quarters[0]}~{test_quarters[-1]})",
        })

    all_results = []
    fold_metrics = []

    for fold in folds:
        print(f"\n  --- {fold['name']} ---")
        X, y, fs, ts_scaler, w = make_sequences(ts_df, feat_cols, max_quarter=fold["train_max"])
        if X is None:
            print(f"  {fold['name']} 시퀀스 생성 실패")
            continue

        n_val = max(1, int(len(X) * 0.2))
        model, val_loss = train_model(
            X[:-n_val], y[:-n_val], w[:-n_val], X[-n_val:], y[-n_val:],
            input_size=X.shape[2], label=fold["name"]
        )

        df_result = backtest_autoregressive(
            model, ts_df, feat_cols, fs, ts_scaler, fold["test_quarters"]
        )
        if len(df_result) > 0:
            a, p = df_result["actual"].values, df_result["predicted"].values
            fold_metrics.append({
                "fold": fold["name"],
                "mape": mape(a, p), "mae": mae(a, p),
                "r2": r_squared(a, p), "n": len(df_result),
            })
            all_results.append(df_result)

    if fold_metrics:
        print("\n  [Fold별 결과]")
        for fm in fold_metrics:
            print(f"    {fm['fold']}: MAPE={fm['mape']:.1f}% MAE={fm['mae']:,.0f} R²={fm['r2']:.4f} (n={fm['n']})")

    return pd.concat(all_results, ignore_index=True) if all_results else None, fold_metrics


# ===========================================================================
# 메인
# ===========================================================================


def run_all_for_imputation(ts_df, feat_cols, imp_name):
    """하나의 결측치 처리 방식에 대해 3가지 검증 방법 모두 실행."""
    results = {}

    # Fixed Origin
    r = run_experiment_fixed_origin(ts_df, feat_cols, f"{imp_name} + Fixed Origin")
    results["fixed"] = r

    # Expanding Window
    r, m = run_experiment_expanding_window(ts_df, feat_cols, f"{imp_name} + Expanding")
    results["expanding"] = (r, m)

    # TimeSeriesSplit
    r, m = run_experiment_tssplit(ts_df, feat_cols, f"{imp_name} + TSSplit")
    results["tssplit"] = (r, m)

    return results


def summarize_result(label, result_df, fold_metrics=None):
    """결과를 요약 dict로 변환."""
    if result_df is None or len(result_df) == 0:
        return None

    if fold_metrics:
        avg_mape = np.mean([m["mape"] for m in fold_metrics])
        avg_mae = np.mean([m["mae"] for m in fold_metrics])
        avg_r2 = np.mean([m["r2"] for m in fold_metrics])
        # 2024 Fold만 따로 추출
        fold_2024 = [m for m in fold_metrics if "2024" in str(m["fold"])]
        mape_2024 = fold_2024[0]["mape"] if fold_2024 else "-"
        total_n = sum(m["n"] for m in fold_metrics)
        a, p = result_df["actual"].values, result_df["predicted"].values
        return {
            "방식": label,
            "MAPE_avg": f"{avg_mape:.1f}",
            "MAPE_2024": f"{mape_2024:.1f}" if isinstance(mape_2024, float) else mape_2024,
            "MAE_avg": f"{avg_mae:,.0f}",
            "R²_avg": f"{avg_r2:.4f}",
            "RMSE": f"{rmse(a, p):,.0f}",
            "샘플": total_n,
        }
    else:
        a, p = result_df["actual"].values, result_df["predicted"].values
        m_val = mape(a, p)
        return {
            "방식": label,
            "MAPE_avg": f"{m_val:.1f}",
            "MAPE_2024": f"{m_val:.1f}",
            "MAE_avg": f"{mae(a, p):,.0f}",
            "R²_avg": f"{r_squared(a, p):.4f}",
            "RMSE": f"{rmse(a, p):,.0f}",
            "샘플": len(result_df),
        }


def main():
    t0 = time.time()
    np.random.seed(42)
    torch.manual_seed(42)

    print("=" * 70)
    print("  결측치 처리 3종 × 검증 전략 3종  비교 실험")
    print("=" * 70)

    # --- 데이터 로드 ---
    print("\n[데이터 로드]")
    sales_m = load_sales_data(dong_prefix="11440")
    stores_m = load_store_data(dong_prefix="11440")
    ts_raw = build_timeseries(sales_m, stores_m)
    feat_cols = [c for c in ALL_FEATURES if c in ts_raw.columns]
    print(f"  피처: {len(feat_cols)}개, 데이터: {ts_raw.shape}")

    # --- 3가지 결측치 처리 방식 준비 ---
    print("\n[결측치 처리 방식 준비]")

    # (1) 기존: fillna(0)
    ts_zero = apply_fillna_zero(ts_raw.copy())
    zero_nulls = ts_zero[feat_cols].isna().sum().sum()
    zero_zeros = (ts_zero[feat_cols] == 0).sum().sum()
    print(f"  [1] fillna(0)     -NaN: {zero_nulls}, Zero: {zero_zeros}")

    # (2) 피처별 가이드 (Hot Deck + interpolate + ffill + median)
    ts_guide = apply_feature_guide(ts_raw.copy())
    guide_nulls = ts_guide[feat_cols].isna().sum().sum()
    guide_zeros = (ts_guide[feat_cols] == 0).sum().sum()
    print(f"  [2] 피처별 가이드  -NaN: {guide_nulls}, Zero: {guide_zeros}")
    print(f"      Zero 감소: {zero_zeros - guide_zeros}개 ({(zero_zeros - guide_zeros) / max(zero_zeros, 1) * 100:.1f}%)")

    # ===================================================================
    # 실험 실행
    # ===================================================================
    all_summaries = []

    # --- [1] fillna(0) × 3가지 검증 ---
    print(f"\n{'#'*70}")
    print("  [1/2] fillna(0) 결측치 처리")
    print(f"{'#'*70}")
    res_zero = run_all_for_imputation(ts_zero, feat_cols, "fillna(0)")

    s = summarize_result("fillna(0) + Fixed", res_zero["fixed"])
    if s: all_summaries.append(s)
    s = summarize_result("fillna(0) + Expanding", *res_zero["expanding"])
    if s: all_summaries.append(s)
    s = summarize_result("fillna(0) + TSSplit", *res_zero["tssplit"])
    if s: all_summaries.append(s)

    # --- [2] 피처별 가이드 × 3가지 검증 ---
    print(f"\n{'#'*70}")
    print("  [2/2] 피처별 가이드 결측치 처리")
    print(f"{'#'*70}")
    res_guide = run_all_for_imputation(ts_guide, feat_cols, "피처별가이드")

    s = summarize_result("피처별가이드 + Fixed", res_guide["fixed"])
    if s: all_summaries.append(s)
    s = summarize_result("피처별가이드 + Expanding", *res_guide["expanding"])
    if s: all_summaries.append(s)
    s = summarize_result("피처별가이드 + TSSplit", *res_guide["tssplit"])
    if s: all_summaries.append(s)

    # ===================================================================
    # 최종 비교 표
    # ===================================================================
    print(f"\n{'='*70}")
    print("  최종 비교 결과")
    print(f"{'='*70}")

    if all_summaries:
        df_summary = pd.DataFrame(all_summaries)
        print("\n" + df_summary.to_string(index=False))
    else:
        print("\n  결과 없음")

    # 2024년 기준 스텝별 MAPE 비교
    print(f"\n{'='*70}")
    print("  2024년 스텝별 MAPE (자기회귀 오차 누적)")
    print(f"{'='*70}")

    # Fixed Origin 결과만 비교 (2024년 동일 조건)
    fixed_results = {
        "fillna(0)": res_zero["fixed"],
        "피처별가이드": res_guide["fixed"],
    }

    header = f"{'스텝':<6}"
    for name in fixed_results:
        header += f" {name:>14}"
    print(header)
    print("-" * (6 + 15 * len(fixed_results)))

    for step in range(1, N_STEPS + 1):
        line = f"Q{step:<5}"
        for name, rdf in fixed_results.items():
            if rdf is not None and len(rdf) > 0:
                ds = rdf[rdf["step"] == step]
                if len(ds) > 0:
                    line += f" {mape(ds['actual'].values, ds['predicted'].values):>13.1f}%"
                else:
                    line += f" {'-':>14}"
            else:
                line += f" {'-':>14}"
        print(line)

    elapsed = time.time() - t0
    print(f"\n총 소요시간: {elapsed:.0f}초 ({elapsed / 60:.1f}분)")


if __name__ == "__main__":
    main()
