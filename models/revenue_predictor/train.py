"""
폐업률 예측 모델 학습 스크립트

전략: 서울 전체 사전학습 → 마포구 파인튜닝 (transfer learning)
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from models.revenue_predictor.data_prep import prepare_training_data
from models.revenue_predictor.model import build_model

logger = logging.getLogger(__name__)

WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"
WEIGHTS_DIR.mkdir(exist_ok=True)

# 학습 하이퍼파라미터
PRETRAIN_EPOCHS = 50
FINETUNE_EPOCHS = 30
BATCH_SIZE = 64
LEARNING_RATE = 1e-3
FINETUNE_LR = 3e-4
EARLY_STOP_PATIENCE = 8
WINDOW_SIZE = 6


# ---------------------------------------------------------------------------
# 유틸리티
# ---------------------------------------------------------------------------


def _make_loader(X: np.ndarray, y: np.ndarray, batch_size: int, shuffle: bool = True) -> DataLoader:
    """numpy 배열을 PyTorch DataLoader로 변환."""
    dataset = TensorDataset(torch.tensor(X, dtype=torch.float32), torch.tensor(y, dtype=torch.float32))
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle)


def _train_loop(
    model: nn.Module,
    train_loader: DataLoader,
    val_loader: DataLoader,
    *,
    epochs: int,
    lr: float,
    device: torch.device,
    patience: int = EARLY_STOP_PATIENCE,
) -> dict:
    """
    공통 학습 루프 (early stopping 포함).

    Returns:
        dict: best_val_loss, train_losses, val_losses
    """
    model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=3, factor=0.5)
    criterion = nn.MSELoss()

    best_val_loss = float("inf")
    best_state = None
    no_improve = 0
    train_losses: list[float] = []
    val_losses: list[float] = []

    for epoch in range(1, epochs + 1):
        # --- Train ---
        model.train()
        epoch_loss = 0.0
        for X_batch, y_batch in train_loader:
            X_batch, y_batch = X_batch.to(device), y_batch.to(device)
            optimizer.zero_grad()
            pred = model(X_batch)
            loss = criterion(pred, y_batch)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            epoch_loss += loss.item() * X_batch.size(0)
        train_loss = epoch_loss / len(train_loader.dataset)
        train_losses.append(train_loss)

        # --- Validation ---
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for X_batch, y_batch in val_loader:
                X_batch, y_batch = X_batch.to(device), y_batch.to(device)
                pred = model(X_batch)
                val_loss += criterion(pred, y_batch).item() * X_batch.size(0)
        val_loss /= len(val_loader.dataset)
        val_losses.append(val_loss)

        scheduler.step(val_loss)

        if epoch % 5 == 0 or epoch == 1:
            logger.info("Epoch %3d | train_loss=%.6f | val_loss=%.6f", epoch, train_loss, val_loss)

        # Early stopping
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= patience:
                logger.info("Early stopping at epoch %d", epoch)
                break

    # 최적 가중치 복원
    if best_state is not None:
        model.load_state_dict(best_state)

    return {"best_val_loss": best_val_loss, "train_losses": train_losses, "val_losses": val_losses}


# ---------------------------------------------------------------------------
# 사전학습 (서울 전체)
# ---------------------------------------------------------------------------


def pretrain(device: torch.device | None = None) -> nn.Module:
    """서울 전체 데이터로 사전학습."""
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    logger.info("=== 사전학습 (서울 전체) 시작 ===")

    try:
        data = prepare_training_data(seoul=True, window_size=WINDOW_SIZE)
    except (FileNotFoundError, ValueError) as exc:
        logger.warning("서울 전체 데이터 로드 실패, 마포구 데이터로 대체: %s", exc)
        data = prepare_training_data(seoul=False, window_size=WINDOW_SIZE)

    n_features = data["X_train"].shape[2]
    model = build_model(input_size=n_features)

    train_loader = _make_loader(data["X_train"], data["y_train"], BATCH_SIZE)
    val_loader = _make_loader(data["X_val"], data["y_val"], BATCH_SIZE, shuffle=False)

    result = _train_loop(
        model,
        train_loader,
        val_loader,
        epochs=PRETRAIN_EPOCHS,
        lr=LEARNING_RATE,
        device=device,
    )
    logger.info("사전학습 완료 — best_val_loss=%.6f", result["best_val_loss"])

    # 사전학습 가중치 저장
    torch.save(model.state_dict(), WEIGHTS_DIR / "pretrained.pt")
    logger.info("사전학습 가중치 저장: %s", WEIGHTS_DIR / "pretrained.pt")

    return model


# ---------------------------------------------------------------------------
# 파인튜닝 (마포구)
# ---------------------------------------------------------------------------


def finetune(model: nn.Module | None = None, device: torch.device | None = None) -> nn.Module:
    """마포구 데이터로 파인튜닝."""
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    logger.info("=== 파인튜닝 (마포구) 시작 ===")

    data = prepare_training_data(seoul=False, window_size=WINDOW_SIZE)
    n_features = data["X_train"].shape[2]

    if model is None:
        model = build_model(input_size=n_features)
        pretrained_path = WEIGHTS_DIR / "pretrained.pt"
        if pretrained_path.exists():
            model.load_state_dict(torch.load(pretrained_path, map_location="cpu", weights_only=True))
            logger.info("사전학습 가중치 로드 완료")

    train_loader = _make_loader(data["X_train"], data["y_train"], BATCH_SIZE)
    val_loader = _make_loader(data["X_val"], data["y_val"], BATCH_SIZE, shuffle=False)

    result = _train_loop(
        model,
        train_loader,
        val_loader,
        epochs=FINETUNE_EPOCHS,
        lr=FINETUNE_LR,
        device=device,
    )
    logger.info("파인튜닝 완료 — best_val_loss=%.6f", result["best_val_loss"])

    # 최종 가중치 저장
    torch.save(model.state_dict(), WEIGHTS_DIR / "closure_model.pt")

    # scaler도 함께 저장 (추론 시 필요)
    import joblib

    joblib.dump(data["scaler"], WEIGHTS_DIR / "scaler.pkl")
    logger.info("최종 모델 및 scaler 저장 완료: %s", WEIGHTS_DIR)

    return model


# ---------------------------------------------------------------------------
# 전체 학습 파이프라인
# ---------------------------------------------------------------------------


def train() -> nn.Module:
    """서울 사전학습 → 마포구 파인튜닝 전체 파이프라인."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("학습 디바이스: %s", device)

    model = pretrain(device=device)
    model = finetune(model=model, device=device)

    logger.info("=== 학습 완료 ===")
    return model


if __name__ == "__main__":
    train()
