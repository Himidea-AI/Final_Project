"""dow_hour task 의 residual learning 학습.

기존 train.py 의 _train_loop, _train_one_epoch, _evaluate 재사용 (DRY).
가중치: living_pop_tcn_v6_dow_hour_residual.pt

데이터: data/processed/living_pop_dow_hour_quarterly.csv
시퀀스 단위: (dong_code, day_of_week, time_zone) sliding window
타깃: Δy = y[t] - y[t-1] (잔차 학습) — naive lag1 자동 보장

⚠️ v4_residual 가중치 절대 덮어쓰지 X — version="v6_dow_hour_residual" 명시 + save_path 자동 분리.
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

from .data_prep_dow_hour import (
    DOW_HOUR_FEATURES,
    DOW_HOUR_TARGET_COL,
    build_dow_hour_features,
    load_dow_hour_cache,
    prepare_sequences_dow_hour,
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
    "version": "v6_dow_hour_residual",
    "mode": "residual",
    "window_size": 8,
    "batch_size": 64,
    "n_channels": 64,
    "kernel_size": 2,
    "dilations": [1, 2, 4],
    "dropout": 0.2,
    "epochs": 100,
    "lr": 1e-3,
    "weight_decay": 1e-5,
    "patience": 15,
    "seed": 2026,
    "train_ratio": 0.70,
    "val_ratio": 0.15,
    "test_ratio": 0.15,
    "target_col": DOW_HOUR_TARGET_COL,
    "feature_cols": None,  # None → DOW_HOUR_FEATURES (25 차원)
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
    """version + save_suffix → 가중치/스케일러/메타 경로 (v4 와 분리 보장)."""
    suffix = cfg.get("save_suffix") or ""
    suf = f"_{suffix}" if suffix else ""
    ver = cfg.get("version", "v6_dow_hour_residual")
    save_path = cfg.get("save_path") or str(WEIGHTS_DIR / f"living_pop_tcn_{ver}{suf}.pt")
    scalers_path = cfg.get("scalers_path") or str(WEIGHTS_DIR / f"living_pop_scalers_{ver}{suf}.pkl")
    metadata_path = cfg.get("metadata_path") or str(WEIGHTS_DIR / f"living_pop_metadata_{ver}{suf}.json")
    return {
        "save_path": Path(save_path),
        "scalers_path": Path(scalers_path),
        "metadata_path": Path(metadata_path),
    }


def _build_dow_hour_loaders(cfg: dict) -> dict:
    """캐시 로드 → 피처 추가 → 시퀀스 → 시간순 70/15/15 split → DataLoader."""
    window_size = int(cfg.get("window_size", 8))
    batch_size = int(cfg.get("batch_size", 64))
    target_col = cfg.get("target_col", DOW_HOUR_TARGET_COL)
    feature_cols = cfg.get("feature_cols") or list(DOW_HOUR_FEATURES)
    mode = cfg.get("mode", "residual")

    train_ratio = float(cfg.get("train_ratio", 0.70))
    val_ratio = float(cfg.get("val_ratio", 0.15))
    test_ratio = float(cfg.get("test_ratio", 0.15))
    total_ratio = train_ratio + val_ratio + test_ratio
    if abs(total_ratio - 1.0) > 1e-6:
        raise ValueError(f"train+val+test == 1.0 이어야 합니다. (현재 합={total_ratio})")

    df = load_dow_hour_cache()
    df = build_dow_hour_features(df)
    logger.info("dow_hour 피처 빌드 완료: shape=%s", df.shape)

    X, y, feat_scaler, tgt_scaler = prepare_sequences_dow_hour(
        df,
        window_size=window_size,
        target_col=target_col,
        mode=mode,
        feature_cols=feature_cols,
    )
    logger.info("시퀀스 생성 완료: X=%s, y=%s, mode=%s", X.shape, y.shape, mode)

    n = len(X)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)
    n_test = n - n_train - n_val
    if n_train <= 0 or n_val <= 0 or n_test <= 0:
        raise ValueError(f"분할 실패: n={n}, train={n_train}, val={n_val}, test={n_test}")

    X_train = X[:n_train]
    X_val = X[n_train : n_train + n_val]
    X_test = X[n_train + n_val :]
    y_train = y[:n_train]
    y_val = y[n_train : n_train + n_val]
    y_test = y[n_train + n_val :]

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
        "sizes": {"train": int(n_train), "val": int(n_val), "test": int(n_test)},
        "mode": mode,
    }


def train_dow_hour_residual(config: dict | None = None) -> dict:
    """dow_hour residual learning 학습 진입점.

    Returns
    -------
    dict
        keys: train_loss, val_loss, test_loss, epochs, save_path, metadata_path,
              scalers_path, input_size, sizes, mode, task.
    """
    cfg = {**DEFAULT_CFG, **(config or {})}
    _set_seed(cfg.get("seed"))

    device = _get_device()
    logger.info(
        "dow_hour TCN %s 학습 시작 (device=%s, mode=%s, suffix=%r)",
        cfg["version"],
        device,
        cfg["mode"],
        cfg.get("save_suffix") or "",
    )

    bundle = _build_dow_hour_loaders(cfg)
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
        "mode": cfg.get("mode", "residual"),
        "task": "dow_hour",
        "input_size": int(input_size),
        "feature_columns": list(feature_columns),
        "n_dong": 16,
        "n_dow": 7,
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
        "target_col": cfg.get("target_col", DOW_HOUR_TARGET_COL),
        "save_path": str(save_path),
        "scalers_path": str(scalers_path),
        "train_time_seconds": float(train_elapsed),
        "trained_at": datetime.now().isoformat(),
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
        "mode": cfg.get("mode", "residual"),
        "task": "dow_hour",
        "train_time_seconds": float(train_elapsed),
    }


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="dow_hour residual learning 학습 (v6_dow_hour_residual)")
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

    result = train_dow_hour_residual(overrides if overrides else None)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


__all__ = [
    "DEFAULT_CFG",
    "WEIGHTS_DIR",
    "train_dow_hour_residual",
]


# numpy 미사용 경고 회피 — _set_seed 내부에서 import 됨
_ = np


if __name__ == "__main__":
    main()
