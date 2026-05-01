"""일별 task TCN residual learning 학습.

target: y[t] - y[t-7] (1주 전과의 차이) — naive_lag7 baseline 능가가 목표.
가중치: living_pop_tcn_v7_daily_residual.pt

데이터: data/processed/living_pop_daily.parquet (16동 × 24시간 × 2,521일)
시퀀스 단위: (dong_code, time_zone) 그룹별 sliding window=14
타깃: Δy_lag7 = y[t] - y[t-7] (잔차 학습) — naive_lag7 자동 보장

⚠️ 기존 v2 / v4_residual / v6_dow_hour_residual 가중치 절대 덮어쓰기 X
   — version="v7_daily_residual" 명시 + save_path 자동 분리.

DRY: train.py 의 _train_loop / _train_one_epoch / _evaluate / _set_seed 재사용.
"""

from __future__ import annotations

import argparse
import json
import logging
import pickle
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from models.tcn_forecast.model import TCNForecaster

from .data_prep_daily import (
    DAILY_FEATURES,
    DAILY_TARGET_COL,
    build_daily_features,
    load_living_pop_daily,
    prepare_sequences_daily,
)
from .train import (
    WEIGHTS_DIR,
    _evaluate,
    _get_device,
    _set_seed,
    _train_loop,
)

logger = logging.getLogger(__name__)


DEFAULT_CFG: dict = {
    "version": "v7_daily_residual",
    "mode": "residual_lag7",
    "window_size": 14,  # 2주 — lag=7 + lag=14 패턴 둘 다 봄
    "batch_size": 256,  # 968K rows 라 큰 배치
    "n_channels": 64,
    "kernel_size": 2,
    "dilations": [1, 2, 4, 8],  # RF=15, window=14 보다 약간 큼
    "dropout": 0.2,
    "epochs": 30,  # 30 epoch * ~960K rows / 256 batch ≈ 적정
    "lr": 1e-3,
    "weight_decay": 1e-5,
    "patience": 5,
    "seed": 2026,
    "train_ratio": 0.70,
    "val_ratio": 0.15,
    "test_ratio": 0.15,
    "target_col": DAILY_TARGET_COL,
    "feature_cols": None,  # None → DAILY_FEATURES (25 차원)
    "save_suffix": "",
    "save_path": None,
    "scalers_path": None,
    "metadata_path": None,
}


def _save_scalers(feat_scaler: object, tgt_scaler: object, path: Path) -> None:
    """v4_residual 호환 — pickle dict {feature_scaler, target_scaler}."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump({"feature_scaler": feat_scaler, "target_scaler": tgt_scaler}, f)
    logger.info("스케일러 저장: %s", path)


def _resolve_paths(cfg: dict) -> dict:
    """version + save_suffix → 가중치/스케일러/메타 경로 (다른 v 와 분리 보장)."""
    suffix = cfg.get("save_suffix") or ""
    suf = f"_{suffix}" if suffix else ""
    ver = cfg.get("version", "v7_daily_residual")
    save_path = cfg.get("save_path") or str(WEIGHTS_DIR / f"living_pop_tcn_{ver}{suf}.pt")
    scalers_path = cfg.get("scalers_path") or str(WEIGHTS_DIR / f"living_pop_scalers_{ver}{suf}.pkl")
    metadata_path = cfg.get("metadata_path") or str(WEIGHTS_DIR / f"living_pop_metadata_{ver}{suf}.json")
    return {
        "save_path": Path(save_path),
        "scalers_path": Path(scalers_path),
        "metadata_path": Path(metadata_path),
    }


def _build_daily_loaders(cfg: dict) -> dict:
    """캐시 로드 → 피처 추가 → 시퀀스 → 시간순 70/15/15 split → DataLoader.

    그룹별 시간순 split 보장: prepare_sequences_daily 가 (dong, hour) 그룹별
    sliding 이라 단순 인덱스 분할이면 그룹 내에서 순서가 끊긴다. 여기서는
    각 그룹의 시퀀스 인덱스 prefix-sum 으로 train/val/test 영역을 정확히 매핑한다.
    """
    window_size = int(cfg.get("window_size", 14))
    batch_size = int(cfg.get("batch_size", 256))
    target_col = cfg.get("target_col", DAILY_TARGET_COL)
    feature_cols = cfg.get("feature_cols") or list(DAILY_FEATURES)
    mode = cfg.get("mode", "residual_lag7")

    train_ratio = float(cfg.get("train_ratio", 0.70))
    val_ratio = float(cfg.get("val_ratio", 0.15))
    test_ratio = float(cfg.get("test_ratio", 0.15))
    total_ratio = train_ratio + val_ratio + test_ratio
    if abs(total_ratio - 1.0) > 1e-6:
        raise ValueError(f"train+val+test == 1.0 이어야 합니다. (현재 합={total_ratio})")

    df = load_living_pop_daily()
    df = build_daily_features(df)
    logger.info("daily 피처 빌드 완료: shape=%s", df.shape)

    X, y, last_value_raw, feat_scaler, tgt_scaler = prepare_sequences_daily(
        df,
        window_size=window_size,
        target_col=target_col,
        mode=mode,
        feature_cols=feature_cols,
    )
    logger.info(
        "시퀀스 생성 완료: X=%s, y=%s, last_value=%s, mode=%s",
        X.shape,
        y.shape,
        last_value_raw.shape,
        mode,
    )

    # 그룹별 시간순 split — 각 그룹의 시퀀스 [n*tr, n*(tr+vr)) 가 val.
    # 그룹 길이 = 2521 - 14 = 2507 시퀀스. 16*24=384 그룹 → 384*2507 = 962,688.
    train_idx_pieces: list[np.ndarray] = []
    val_idx_pieces: list[np.ndarray] = []
    test_idx_pieces: list[np.ndarray] = []
    consumed = 0
    for (_d, _h), group in df.groupby(["dong_code", "time_zone"], sort=True):
        if len(group) <= window_size:
            continue
        n_seq = len(group) - window_size
        n_train = max(1, int(n_seq * train_ratio))
        n_val = max(1, int(n_seq * val_ratio))
        n_train = min(n_train, n_seq - 2)
        n_val = min(n_val, n_seq - n_train - 1)
        g_start = consumed
        train_idx_pieces.append(np.arange(g_start, g_start + n_train, dtype=np.int64))
        val_idx_pieces.append(np.arange(g_start + n_train, g_start + n_train + n_val, dtype=np.int64))
        test_idx_pieces.append(np.arange(g_start + n_train + n_val, g_start + n_seq, dtype=np.int64))
        consumed += n_seq

    if consumed != len(X):
        raise ValueError(f"split 인덱스 불일치: consumed={consumed}, len(X)={len(X)}")

    train_idx = np.concatenate(train_idx_pieces) if train_idx_pieces else np.empty(0, dtype=np.int64)
    val_idx = np.concatenate(val_idx_pieces) if val_idx_pieces else np.empty(0, dtype=np.int64)
    test_idx = np.concatenate(test_idx_pieces) if test_idx_pieces else np.empty(0, dtype=np.int64)
    if train_idx.size == 0 or val_idx.size == 0 or test_idx.size == 0:
        raise ValueError(f"분할 실패: n={len(X)}, train={train_idx.size}, val={val_idx.size}, test={test_idx.size}")

    X_train = X[train_idx]
    X_val = X[val_idx]
    X_test = X[test_idx]
    y_train = y[train_idx]
    y_val = y[val_idx]
    y_test = y[test_idx]
    last_value_test = last_value_raw[test_idx]

    train_ds = TensorDataset(torch.from_numpy(X_train), torch.from_numpy(y_train))
    val_ds = TensorDataset(torch.from_numpy(X_val), torch.from_numpy(y_val))
    test_ds = TensorDataset(torch.from_numpy(X_test), torch.from_numpy(y_test))
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)

    return {
        "train_loader": train_loader,
        "val_loader": val_loader,
        "test_loader": test_loader,
        "feat_scaler": feat_scaler,
        "tgt_scaler": tgt_scaler,
        "input_size": int(X.shape[2]),
        "feature_columns": list(feature_cols),
        "sizes": {"train": int(train_idx.size), "val": int(val_idx.size), "test": int(test_idx.size)},
        "mode": mode,
        # inline 평가용
        "X_test": X_test,
        "y_test": y_test,
        "last_value_test": last_value_test,
        "df_full": df,
        "train_idx": train_idx,
        "test_idx": test_idx,
        "window_size": window_size,
        "target_col": target_col,
    }


def _compute_inline_metrics(
    model: TCNForecaster,
    bundle: dict,
    device: torch.device,
) -> dict:
    """학습 후 inline 학술 metric 측정.

    test split 의 y_pred = last_value_lag7 + delta_actual 을 raw 단위로 복원 후
    MAE / RMSE / MAPE / sMAPE / R² / MASE_lag7 / MASE_in_sample 산출.
    """
    from validation.metrics.forecast_metrics import evaluate_all as compute_metrics

    X_test = bundle["X_test"]
    last_value_test = bundle["last_value_test"]
    tgt_scaler = bundle["tgt_scaler"]

    model.eval()
    preds: list[np.ndarray] = []
    batch_size = 512
    with torch.no_grad():
        for start in range(0, len(X_test), batch_size):
            chunk = torch.from_numpy(X_test[start : start + batch_size]).to(device)
            out = model(chunk).cpu().numpy().reshape(-1)
            preds.append(out)
    pred_norm = np.concatenate(preds, axis=0).astype(np.float32)
    delta_actual = tgt_scaler.inverse_transform(pred_norm.reshape(-1, 1)).reshape(-1).astype(np.float32)
    y_pred = np.maximum(last_value_test + delta_actual, 0.0)

    # y_true: test 시퀀스의 t 시점 raw target — last_value + true_delta 로 복원.
    y_test_norm = bundle["y_test"].astype(np.float32).reshape(-1, 1)
    true_delta = tgt_scaler.inverse_transform(y_test_norm).reshape(-1).astype(np.float32)
    y_true = (last_value_test + true_delta).astype(np.float32)

    # naive_lag7 baseline 자체 = last_value_test
    y_naive = last_value_test.astype(np.float32)

    # train 시계열 (1d concat) — Hyndman in-sample MASE 분모용.
    df_full = bundle["df_full"]
    window_size = bundle["window_size"]
    target_col = bundle["target_col"]
    train_ratio = 0.70
    val_ratio = 0.15
    train_pieces: list[np.ndarray] = []
    for (_d, _h), group in df_full.groupby(["dong_code", "time_zone"], sort=True):
        if len(group) <= window_size:
            continue
        n_seq = len(group) - window_size
        n_train = max(1, int(n_seq * train_ratio))
        n_val = max(1, int(n_seq * val_ratio))
        n_train = min(n_train, n_seq - 2)
        n_val = min(n_val, n_seq - n_train - 1)
        gs = group.sort_values("date").reset_index(drop=True)
        # 시퀀스 i 는 raw_targets[i+W] 시점 target — train 시퀀스 [0, n_train) 사용 시
        # 사용된 target time = [W, W+n_train). 분모는 lag-1 변동성 → t=W-1 까지 포함.
        end_t = window_size + n_train
        segment = gs[target_col].values[:end_t].astype(np.float32)
        train_pieces.append(segment)
    y_train_actuals = np.concatenate(train_pieces, axis=0) if train_pieces else np.asarray([], dtype=np.float32)

    metrics = compute_metrics(
        y_true,
        y_pred,
        y_naive=y_naive,
        y_train=y_train_actuals if y_train_actuals.size > 0 else None,
    )
    return {
        "MAE": float(metrics["MAE"]),
        "RMSE": float(metrics["RMSE"]),
        "NRMSE_pct": float(metrics["NRMSE_pct"]),
        "MAPE_pct": float(metrics["MAPE_pct"]),
        "sMAPE_pct": float(metrics["sMAPE_pct"]),
        "R2": float(metrics["R2"]),
        "MASE_lag7": float(metrics.get("MASE", float("nan"))),
        "MASE_in_sample": float(metrics.get("MASE_in_sample", float("nan"))),
        "n_test": int(len(y_true)),
    }


def train_daily_residual(config: dict | None = None) -> dict:
    """일별 task residual_lag7 learning 학습 진입점.

    Returns
    -------
    dict
        keys: train_loss, val_loss, test_loss, epochs, save_path, metadata_path,
              scalers_path, input_size, sizes, mode, task, train_time_seconds,
              metrics (inline 학술 metric).
    """
    cfg = {**DEFAULT_CFG, **(config or {})}
    _set_seed(cfg.get("seed"))

    device = _get_device()
    logger.info(
        "daily TCN %s 학습 시작 (device=%s, mode=%s, suffix=%r)",
        cfg["version"],
        device,
        cfg["mode"],
        cfg.get("save_suffix") or "",
    )

    bundle = _build_daily_loaders(cfg)
    train_loader = bundle["train_loader"]
    val_loader = bundle["val_loader"]
    test_loader = bundle["test_loader"]
    feat_scaler = bundle["feat_scaler"]
    tgt_scaler = bundle["tgt_scaler"]
    input_size = bundle["input_size"]
    feature_columns = bundle["feature_columns"]
    sizes = bundle["sizes"]

    logger.info(
        "DataLoader 준비: input_size=%d, mode=%s, train=%d, val=%d, test=%d batches",
        input_size,
        bundle["mode"],
        len(train_loader),
        len(val_loader),
        len(test_loader),
    )

    model = TCNForecaster(
        input_size=input_size,
        n_channels=int(cfg["n_channels"]),
        kernel_size=int(cfg["kernel_size"]),
        dilations=list(cfg["dilations"]),
        dropout=float(cfg["dropout"]),
    ).to(device)

    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=float(cfg["lr"]),
        weight_decay=float(cfg["weight_decay"]),
    )

    t0 = time.time()
    result = _train_loop(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        optimizer=optimizer,
        criterion=criterion,
        device=device,
        epochs=int(cfg["epochs"]),
        patience=int(cfg["patience"]),
    )
    train_elapsed = time.time() - t0

    model.load_state_dict(result["best_state"])
    test_loss = _evaluate(model, test_loader, criterion, device)
    logger.info(
        "Test 평가: test_loss=%.6f (best_val=%.6f, train_time=%.1fs)",
        test_loss,
        result["best_val_loss"],
        train_elapsed,
    )

    # inline 학술 metric (raw 단위)
    metrics = _compute_inline_metrics(model, bundle, device)
    logger.info(
        "inline metrics: MAE=%.2f, RMSE=%.2f, MAPE=%.3f%%, R2=%.4f, MASE_lag7=%.4f, MASE_in_sample=%.4f",
        metrics["MAE"],
        metrics["RMSE"],
        metrics["MAPE_pct"],
        metrics["R2"],
        metrics["MASE_lag7"],
        metrics["MASE_in_sample"],
    )

    paths = _resolve_paths(cfg)
    save_path = paths["save_path"]
    scalers_path = paths["scalers_path"]
    metadata_path = paths["metadata_path"]

    save_path.parent.mkdir(parents=True, exist_ok=True)
    model.save_weights(save_path)
    logger.info("가중치 저장: %s (best_val=%.6f)", save_path, result["best_val_loss"])
    _save_scalers(feat_scaler, tgt_scaler, scalers_path)

    metadata = {
        "version": cfg.get("version"),
        "mode": cfg.get("mode", "residual_lag7"),
        "task": "daily",
        "input_size": int(input_size),
        "feature_columns": list(feature_columns),
        "n_dong": 16,
        "n_hours": 24,
        "save_suffix": cfg.get("save_suffix") or "",
        "best_val_loss": float(result["best_val_loss"]),
        "test_loss": float(test_loss),
        "train_size": int(sizes["train"]),
        "val_size": int(sizes["val"]),
        "test_size": int(sizes["test"]),
        "epochs_trained": int(result["epochs_trained"]),
        "n_channels": int(cfg["n_channels"]),
        "kernel_size": int(cfg["kernel_size"]),
        "dilations": list(cfg["dilations"]),
        "window_size": int(cfg["window_size"]),
        "batch_size": int(cfg["batch_size"]),
        "lr": float(cfg["lr"]),
        "weight_decay": float(cfg["weight_decay"]),
        "patience": int(cfg["patience"]),
        "dropout": float(cfg["dropout"]),
        "seed": cfg.get("seed"),
        "target_col": cfg.get("target_col", DAILY_TARGET_COL),
        "save_path": str(save_path),
        "scalers_path": str(scalers_path),
        "train_time_seconds": float(train_elapsed),
        "trained_at": datetime.now().isoformat(),
        "metrics": metrics,
    }
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("metadata 저장: %s", metadata_path)

    return {
        "train_loss": float(result["best_train_loss"]),
        "val_loss": float(result["best_val_loss"]),
        "test_loss": float(test_loss),
        "epochs": int(result["epochs_trained"]),
        "save_path": str(save_path),
        "metadata_path": str(metadata_path),
        "scalers_path": str(scalers_path),
        "input_size": int(input_size),
        "sizes": sizes,
        "mode": cfg.get("mode", "residual_lag7"),
        "task": "daily",
        "train_time_seconds": float(train_elapsed),
        "metrics": metrics,
    }


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="daily residual learning 학습 (v7_daily_residual)")
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--lr", type=float, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--patience", type=int, default=None)
    parser.add_argument("--window-size", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--save-suffix", type=str, default=None)
    parser.add_argument("--version", type=str, default=None)
    parser.add_argument("--n-channels", type=int, default=None)
    parser.add_argument("--dropout", type=float, default=None)
    parser.add_argument("--mode", type=str, default=None, help="residual_lag7 | residual_lag1 | absolute")
    args = parser.parse_args()

    overrides: dict = {}
    if args.epochs is not None:
        overrides["epochs"] = args.epochs
    if args.lr is not None:
        overrides["lr"] = args.lr
    if args.batch_size is not None:
        overrides["batch_size"] = args.batch_size
    if args.patience is not None:
        overrides["patience"] = args.patience
    if args.window_size is not None:
        overrides["window_size"] = args.window_size
    if args.seed is not None:
        overrides["seed"] = args.seed
    if args.save_suffix:
        overrides["save_suffix"] = args.save_suffix
    if args.version:
        overrides["version"] = args.version
    if args.n_channels is not None:
        overrides["n_channels"] = args.n_channels
    if args.dropout is not None:
        overrides["dropout"] = args.dropout
    if args.mode:
        overrides["mode"] = args.mode

    result = train_daily_residual(overrides if overrides else None)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


__all__ = [
    "DEFAULT_CFG",
    "WEIGHTS_DIR",
    "train_daily_residual",
]


# numpy 미사용 경고 회피 — _set_seed 내부에서 import 됨
_ = np


if __name__ == "__main__":
    main()
