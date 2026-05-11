"""
TCN DMS 고도화 핵심 동작 단위 테스트

검증 항목:
  1. prepare_sequences output_size=4 → y shape (N, 4)
  2. prepare_sequences 최소 그룹 길이 조건 — window_size+output_size 미만 제외
  3. prepare_dataloaders val_quarter 기반 시간 분할
  4. TCNForecaster output_size=4 → forward (batch, 4)
  5. predict() DMS — autoregressive 루프 없이 4개 분기 반환
  6. predict() 패딩 — 8분기 미만 그룹도 추론 가능

담당: B2 — 수지니
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import torch


# ---------------------------------------------------------------------------
# 공통 픽스처
# ---------------------------------------------------------------------------

def _make_ts(n_groups: int = 5, n_quarters: int = 24) -> pd.DataFrame:
    """테스트용 미니 시계열 DataFrame 생성 (DB 불필요)."""
    rng = np.random.default_rng(42)
    rows = []
    quarters = []
    for y in range(2019, 2025):
        for q in range(1, 5):
            quarters.append(y * 10 + q)
    quarters = quarters[:n_quarters]

    for g in range(n_groups):
        dong_code = f"1144000{g}"
        industry_code = "CS100001"
        for q in quarters:
            rows.append({
                "dong_code": dong_code,
                "industry_code": industry_code,
                "quarter": q,
                "monthly_sales": float(rng.integers(1_000_000, 50_000_000)),
                "monthly_count": float(rng.integers(100, 5000)),
                "sample_weight": 1.0,
            })
    df = pd.DataFrame(rows)
    return df


# ---------------------------------------------------------------------------
# Task 2-A: prepare_sequences DMS
# ---------------------------------------------------------------------------

def test_prepare_sequences_dms_y_shape():
    """output_size=4 이면 y shape이 (N, 4)이어야 한다."""
    from models.lstm_forecast.data_prep import prepare_sequences

    ts = _make_ts(n_groups=3, n_quarters=20)
    feature_cols = ["monthly_sales", "monthly_count"]

    X, y, _, _, _, _ = prepare_sequences(
        ts,
        window_size=8,
        output_size=4,
        target_col="monthly_sales",
        feature_cols=feature_cols,
    )
    assert y.ndim == 2
    assert y.shape[1] == 4, f"y.shape expected (N,4), got {y.shape}"


def test_prepare_sequences_output_size_1_backward_compat():
    """output_size=1 (기본값) 이면 기존처럼 y shape (N, 1)이어야 한다."""
    from models.lstm_forecast.data_prep import prepare_sequences

    ts = _make_ts(n_groups=3, n_quarters=20)
    feature_cols = ["monthly_sales", "monthly_count"]

    result = prepare_sequences(
        ts,
        window_size=4,
        output_size=1,
        target_col="monthly_sales",
        feature_cols=feature_cols,
    )
    X, y = result[0], result[1]
    assert y.shape[1] == 1, f"backward compat: y.shape expected (N,1), got {y.shape}"


def test_prepare_sequences_min_group_len():
    """window_size=8, output_size=4 → 12분기 미만 그룹은 제외되어야 한다."""
    from models.lstm_forecast.data_prep import prepare_sequences

    # 정상 그룹: 24분기, 부족 그룹: 11분기 (12 미만)
    ts_ok = _make_ts(n_groups=3, n_quarters=24)
    ts_short = _make_ts(n_groups=1, n_quarters=11)
    # short 그룹 dong_code를 다르게 설정
    ts_short["dong_code"] = "11440999"
    ts = pd.concat([ts_ok, ts_short], ignore_index=True)

    feature_cols = ["monthly_sales", "monthly_count"]
    X_all, _, _, _, _, _ = prepare_sequences(
        ts, window_size=8, output_size=4, target_col="monthly_sales", feature_cols=feature_cols
    )
    X_ok, _, _, _, _, _ = prepare_sequences(
        ts_ok, window_size=8, output_size=4, target_col="monthly_sales", feature_cols=feature_cols
    )
    # short 그룹이 제외되었으므로 시퀀스 수가 동일해야 함
    assert X_all.shape[0] == X_ok.shape[0], (
        f"11분기 그룹이 제외되지 않음: {X_all.shape[0]} != {X_ok.shape[0]}"
    )


def test_prepare_sequences_returns_first_pred_quarters():
    """6번째 반환값 first_pred_quarters가 올바른 분기값을 담아야 한다."""
    from models.lstm_forecast.data_prep import prepare_sequences

    ts = _make_ts(n_groups=2, n_quarters=20)
    feature_cols = ["monthly_sales", "monthly_count"]
    _, _, _, _, _, fpq = prepare_sequences(
        ts, window_size=8, output_size=4, target_col="monthly_sales", feature_cols=feature_cols
    )
    assert fpq.ndim == 1
    # 모든 값이 valid YYYYQ 형식 (20191 ~ 20244)
    assert fpq.min() >= 20191
    assert fpq.max() <= 20244


# ---------------------------------------------------------------------------
# Task 2-B: prepare_dataloaders 시간 기반 val 분할
# ---------------------------------------------------------------------------

def test_prepare_dataloaders_val_quarter_split(tmp_path, monkeypatch):
    """val_quarter=20241 이면 first_pred_quarter >= 20241 시퀀스가 val에 들어가야 한다."""
    from torch.utils.data import DataLoader

    from models.lstm_forecast import data_prep as dp

    ts = _make_ts(n_groups=10, n_quarters=24)  # 충분한 데이터

    # build_timeseries, load_sales_data, load_store_data 모두 monkeypatch
    monkeypatch.setattr(dp, "load_sales_data", lambda **kw: ts)
    monkeypatch.setattr(dp, "load_store_data", lambda **kw: pd.DataFrame())
    monkeypatch.setattr(dp, "build_timeseries", lambda s, st, fc=None: ts)

    cfg = {
        "db_url": "postgresql://invalid/nonexistent",
        "dong_prefix": "11440",
        "window_size": 8,
        "output_size": 4,
        "batch_size": 16,
        "val_ratio": 0.2,
        "val_quarter": 20241,
        "target_col": "monthly_sales",
        "feature_cols": ["monthly_sales", "monthly_count"],
    }
    train_loader, val_loader, _, _, _ = dp.prepare_dataloaders(cfg)

    assert isinstance(train_loader, DataLoader)
    assert isinstance(val_loader, DataLoader)
    assert len(train_loader) > 0
    assert len(val_loader) > 0


# ---------------------------------------------------------------------------
# Task 3: TCNForecaster output_size=4
# ---------------------------------------------------------------------------

def test_tcnforecaster_output_size_4():
    """output_size=4 로 초기화하면 forward 결과가 (batch, 4) 이어야 한다."""
    from models.tcn_forecast.model import TCNForecaster

    batch, seq_len, input_size = 8, 8, 10
    model = TCNForecaster(
        input_size=input_size,
        n_channels=32,
        kernel_size=2,
        dilations=[1, 2, 4],
        dropout=0.0,
        output_size=4,
    )
    model.eval()
    x = torch.randn(batch, seq_len, input_size)
    with torch.no_grad():
        out = model(x)
    assert out.shape == (batch, 4), f"expected (8,4), got {out.shape}"


def test_tcnforecaster_default_output_size():
    """dilations 기본값이 [1,2,4]이고 output_size 기본값이 4이어야 한다."""
    from models.tcn_forecast.model import TCNForecaster

    model = TCNForecaster(input_size=10)
    assert model.dilations == [1, 2, 4], f"dilations default: {model.dilations}"
    # FC 마지막 레이어 출력 차원 확인
    last_linear = list(model.fc.children())[-1]
    assert last_linear.out_features == 4, f"FC out_features: {last_linear.out_features}"


# ---------------------------------------------------------------------------
# Task 5: predict() DMS + padding
# ---------------------------------------------------------------------------

def test_predict_returns_4_quarters(tmp_path, monkeypatch):
    """predict()가 항상 4개 dict를 반환해야 한다."""
    import pickle

    import numpy as np
    from sklearn.preprocessing import MinMaxScaler

    from models.tcn_forecast import predict as tcn_predict_module
    from models.tcn_forecast.model import TCNForecaster

    # 미니 모델 가중치 저장
    model = TCNForecaster(input_size=2, n_channels=8, dilations=[1, 2, 4], output_size=4)
    weights_path = tmp_path / "finetuned_mapo_tcn_v2.pt"
    model.save_weights(weights_path)

    # 미니 스케일러 저장
    feat_scaler = MinMaxScaler().fit(np.random.rand(20, 2))
    tgt_scaler = MinMaxScaler().fit(np.random.rand(20, 1))
    scalers_path = tmp_path / "finetune_tcn_scalers_v2.pkl"
    with open(scalers_path, "wb") as f:
        pickle.dump({"feature_scaler": feat_scaler, "target_scaler": tgt_scaler}, f)

    # residual_std 저장
    residual_std_path = tmp_path / "finetune_tcn_residual_std_v2.pkl"
    with open(residual_std_path, "wb") as f:
        pickle.dump([500000.0, 600000.0, 700000.0, 800000.0], f)

    # 24분기 그룹 데이터 monkeypatch
    ts = _make_ts(n_groups=1, n_quarters=24)
    ts["dong_code"] = "11440555"
    ts["industry_code"] = "CS100001"
    import models.lstm_forecast.data_prep as dp_mod
    monkeypatch.setattr(dp_mod, "load_sales_data", lambda **kw: ts)
    monkeypatch.setattr(dp_mod, "load_store_data", lambda **kw: pd.DataFrame())
    monkeypatch.setattr(dp_mod, "build_timeseries", lambda s, st: ts)

    cfg = {
        "weights_path": str(weights_path),
        "scalers_path": str(scalers_path),
        "residual_std_path": str(residual_std_path),
        "window_size": 8,
        "n_channels": 8,
        "dilations": [1, 2, 4],
        "dropout": 0.0,
        "feature_cols": ["monthly_sales", "monthly_count"],
    }
    results = tcn_predict_module.predict("11440555", "CS100001", config=cfg)
    assert len(results) == 4
    for i, r in enumerate(results):
        assert r["quarter_offset"] == i + 1
        assert "predicted_sales" in r
        assert "confidence_lower" in r
        assert "confidence_upper" in r


def test_predict_padding_for_short_group(tmp_path, monkeypatch):
    """7분기(< window_size=8) 그룹도 패딩 후 정상 추론되어야 한다."""
    import pickle

    import numpy as np
    from sklearn.preprocessing import MinMaxScaler

    from models.tcn_forecast import predict as tcn_predict_module
    from models.tcn_forecast.model import TCNForecaster

    model = TCNForecaster(input_size=2, n_channels=8, dilations=[1, 2, 4], output_size=4)
    weights_path = tmp_path / "w.pt"
    model.save_weights(weights_path)

    feat_scaler = MinMaxScaler().fit(np.random.rand(20, 2))
    tgt_scaler = MinMaxScaler().fit(np.random.rand(20, 1))
    scalers_path = tmp_path / "s.pkl"
    with open(scalers_path, "wb") as f:
        pickle.dump({"feature_scaler": feat_scaler, "target_scaler": tgt_scaler}, f)

    residual_std_path = tmp_path / "r.pkl"
    with open(residual_std_path, "wb") as f:
        pickle.dump([1.0, 1.0, 1.0, 1.0], f)

    # 7분기 그룹 (window_size=8 미만)
    ts_short = _make_ts(n_groups=1, n_quarters=7)
    ts_short["dong_code"] = "11440555"
    ts_short["industry_code"] = "CS100001"
    import models.lstm_forecast.data_prep as dp_mod
    monkeypatch.setattr(dp_mod, "load_sales_data", lambda **kw: ts_short)
    monkeypatch.setattr(dp_mod, "load_store_data", lambda **kw: pd.DataFrame())
    monkeypatch.setattr(dp_mod, "build_timeseries", lambda s, st: ts_short)

    cfg = {
        "weights_path": str(weights_path),
        "scalers_path": str(scalers_path),
        "residual_std_path": str(residual_std_path),
        "window_size": 8,
        "n_channels": 8,
        "dilations": [1, 2, 4],
        "dropout": 0.0,
        "feature_cols": ["monthly_sales", "monthly_count"],
    }
    # ValueError 없이 정상 실행되어야 함
    results = tcn_predict_module.predict("11440555", "CS100001", config=cfg)
    assert len(results) == 4
