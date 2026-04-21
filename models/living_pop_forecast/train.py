"""
생활인구 유동인구 TCN 모델 학습 스크립트

living_population → 동×시간대 분기 집계 → TCNForecaster 학습

16개 동 × 24시간대 = 384 그룹 × ~20 시퀀스 = ~7,680 시퀀스
단일 학습 (마포구 단일 지역 — pretrain/finetune 불필요)

window_size=8, dilations=[1,2,4] → RF = 1 + 1×(1+2+4) = 8

Usage:
    python -m models.living_pop_forecast.train
    python -m models.living_pop_forecast.train --epochs 50 --seed 42

담당: B2 — 수지니
참조: models/tcn_forecast/train.py (구조 동일)
"""

from __future__ import annotations

import argparse
import copy
import logging
import pickle
import time
from pathlib import Path

import torch
import torch.nn as nn

from models.tcn_forecast.model import TCNForecaster

from .data_prep import DB_URL, TARGET_COL, prepare_dataloaders

logger = logging.getLogger(__name__)

WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"

# ---------------------------------------------------------------------------
# 기본 하이퍼파라미터
# ---------------------------------------------------------------------------

DEFAULT_TRAIN_CONFIG: dict = {
    "db_url": DB_URL,
    "csv_path": None,
    "window_size": 8,  # 8분기 = 2년 — RF=8과 일치
    "batch_size": 64,
    "val_ratio": 0.2,
    "target_col": TARGET_COL,
    "feature_cols": None,  # None = POP_FEATURES (5개)
    # 모델
    "n_channels": 64,
    "kernel_size": 2,
    "dilations": [1, 2, 4],  # RF = 1 + 1*(1+2+4) = 8
    "dropout": 0.2,
    # 학습
    "epochs": 100,
    "lr": 1e-3,
    "weight_decay": 1e-5,
    "patience": 15,
    # 출력
    "save_path": str(WEIGHTS_DIR / "living_pop_tcn.pt"),
    "scalers_path": str(WEIGHTS_DIR / "living_pop_scalers.pkl"),
}


# ---------------------------------------------------------------------------
# 학습 유틸 (tcn_forecast/train.py와 동일한 구조)
# ---------------------------------------------------------------------------


def _get_device() -> torch.device:
    return torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")


def _train_one_epoch(
    model: nn.Module,
    loader: torch.utils.data.DataLoader,
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer,
    device: torch.device,
) -> float:
    model.train()
    total_loss = 0.0
    n_batches = 0

    for batch in loader:
        if len(batch) == 3:
            X_batch, y_batch, w_batch = batch
            w_batch = w_batch.to(device)
        else:
            X_batch, y_batch = batch
            w_batch = None

        X_batch = X_batch.to(device)
        y_batch = y_batch.to(device)

        optimizer.zero_grad()
        pred = model(X_batch)

        if w_batch is not None:
            loss = (w_batch.unsqueeze(1) * (pred - y_batch) ** 2).mean()
        else:
            loss = criterion(pred, y_batch)

        loss.backward()
        optimizer.step()
        total_loss += loss.item()
        n_batches += 1

    return total_loss / max(n_batches, 1)


@torch.no_grad()
def _validate(
    model: nn.Module,
    loader: torch.utils.data.DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> float:
    model.eval()
    total_loss = 0.0
    n_batches = 0

    for X_batch, y_batch in loader:
        X_batch = X_batch.to(device)
        y_batch = y_batch.to(device)
        pred = model(X_batch)
        loss = criterion(pred, y_batch)
        total_loss += loss.item()
        n_batches += 1

    return total_loss / max(n_batches, 1)


def _train_loop(
    model: TCNForecaster,
    train_loader: torch.utils.data.DataLoader,
    val_loader: torch.utils.data.DataLoader,
    optimizer: torch.optim.Optimizer,
    criterion: nn.Module,
    device: torch.device,
    epochs: int,
    patience: int,
) -> dict:
    best_val_loss = float("inf")
    best_state = copy.deepcopy(model.state_dict())
    wait = 0

    for epoch in range(1, epochs + 1):
        t0 = time.time()
        train_loss = _train_one_epoch(model, train_loader, criterion, optimizer, device)
        val_loss = _validate(model, val_loader, criterion, device)
        elapsed = time.time() - t0

        logger.info(
            "Epoch %3d/%d  train=%.6f  val=%.6f  (%.1fs)",
            epoch,
            epochs,
            train_loss,
            val_loss,
            elapsed,
        )

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = copy.deepcopy(model.state_dict())
            wait = 0
        else:
            wait += 1
            if wait >= patience:
                logger.info(
                    "조기 종료: %d 에폭 동안 개선 없음 (best_val=%.6f)",
                    patience,
                    best_val_loss,
                )
                break

    return {"best_state": best_state, "best_val_loss": best_val_loss}


# ---------------------------------------------------------------------------
# 스케일러 저장/로드
# ---------------------------------------------------------------------------


def _save_scalers(feat_scaler: object, tgt_scaler: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump({"feature_scaler": feat_scaler, "target_scaler": tgt_scaler}, f)
    logger.info("스케일러 저장: %s", path)


def load_scalers(path: str | Path) -> tuple:
    with open(path, "rb") as f:
        data = pickle.load(f)  # noqa: S301
    return data["feature_scaler"], data["target_scaler"]


# ---------------------------------------------------------------------------
# 학습 진입점
# ---------------------------------------------------------------------------


def train(config: dict | None = None) -> Path:
    """마포구 생활인구 데이터로 TCN 유동인구 예측 모델을 학습한다.

    Parameters
    ----------
    config : dict, optional
        하이퍼파라미터 오버라이드.

    Returns
    -------
    Path
        저장된 가중치 파일 경로.
    """
    cfg = {**DEFAULT_TRAIN_CONFIG, **(config or {})}
    device = _get_device()
    logger.info("생활인구 TCN 학습 시작 (device=%s)", device)

    train_loader, val_loader, feat_scaler, tgt_scaler, input_size = prepare_dataloaders(cfg)
    logger.info(
        "DataLoader 준비: input_size=%d, train=%d, val=%d batches", input_size, len(train_loader), len(val_loader)
    )

    model = TCNForecaster(
        input_size=input_size,
        n_channels=cfg["n_channels"],
        kernel_size=cfg["kernel_size"],
        dilations=cfg["dilations"],
        dropout=cfg["dropout"],
    ).to(device)

    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=cfg["lr"], weight_decay=cfg["weight_decay"])

    result = _train_loop(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        optimizer=optimizer,
        criterion=criterion,
        device=device,
        epochs=cfg["epochs"],
        patience=cfg["patience"],
    )

    model.load_state_dict(result["best_state"])

    save_path = Path(cfg["save_path"])
    save_path.parent.mkdir(parents=True, exist_ok=True)
    model.save_weights(save_path)
    logger.info("가중치 저장: %s (best_val=%.6f)", save_path, result["best_val_loss"])

    _save_scalers(feat_scaler, tgt_scaler, Path(cfg["scalers_path"]))
    return save_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="생활인구 유동인구 TCN 학습")
    parser.add_argument("--db-url", type=str, default=None)
    parser.add_argument("--csv-path", type=str, default=None, help="living_pop_quarterly.csv 경로")
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--lr", type=float, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--patience", type=int, default=None)
    parser.add_argument("--window-size", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    if args.seed is not None:
        import random

        import numpy as np

        random.seed(args.seed)
        np.random.seed(args.seed)
        torch.manual_seed(args.seed)
        torch.cuda.manual_seed_all(args.seed)

    overrides: dict = {}
    if args.db_url:
        overrides["db_url"] = args.db_url
    if args.csv_path:
        overrides["csv_path"] = args.csv_path
    if args.epochs:
        overrides["epochs"] = args.epochs
    if args.lr:
        overrides["lr"] = args.lr
    if args.batch_size:
        overrides["batch_size"] = args.batch_size
    if args.patience:
        overrides["patience"] = args.patience
    if args.window_size:
        overrides["window_size"] = args.window_size

    train(overrides if overrides else None)


if __name__ == "__main__":
    main()
