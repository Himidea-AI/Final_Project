"""
타겟 고객 매출 기여 예측 MLP 학습 스크립트

Usage:
    python -m models.customer_revenue.train

출력:
    models/customer_revenue/weights/customer_mlp.pt
    models/customer_revenue/weights/segment_mappings.pkl

담당: B2 — 수지니
"""

from __future__ import annotations

import logging

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from models.customer_revenue.data_prep import DB_URL, prepare_training_data, save_mappings
from models.customer_revenue.model import WEIGHTS_DIR, build_model

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# 하이퍼파라미터
EPOCHS = 200
BATCH_SIZE = 64
LR = 1e-3
PATIENCE = 20
VAL_RATIO = 0.2
DROPOUT = 0.3


def _make_loader(
    dong_idx: np.ndarray,
    industry_idx: np.ndarray,
    quarter_enc: np.ndarray,
    y: np.ndarray,
    batch_size: int,
    shuffle: bool = True,
) -> DataLoader:
    ds = TensorDataset(
        torch.tensor(dong_idx, dtype=torch.long),
        torch.tensor(industry_idx, dtype=torch.long),
        torch.tensor(quarter_enc, dtype=torch.float32),
        torch.tensor(y, dtype=torch.float32),
    )
    return DataLoader(ds, batch_size=batch_size, shuffle=shuffle)


def train(db_url: str = DB_URL) -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("학습 디바이스: %s", device)

    # 데이터 준비
    dong_idx, industry_idx, quarter_enc, y, identified_ratios, year_max = prepare_training_data(db_url=db_url)

    # 시간순 train/val 분리 (셔플 없이 앞→뒤)
    n = len(dong_idx)
    n_val = max(1, int(n * VAL_RATIO))
    n_train = n - n_val
    if n_train <= 0:
        raise ValueError(f"학습 데이터 부족: 전체 {n}행, val {n_val}행 — district_sales를 확인하세요.")

    train_loader = _make_loader(
        dong_idx[:n_train],
        industry_idx[:n_train],
        quarter_enc[:n_train],
        y[:n_train],
        batch_size=BATCH_SIZE,
        shuffle=True,
    )
    val_loader = _make_loader(
        dong_idx[n_train:],
        industry_idx[n_train:],
        quarter_enc[n_train:],
        y[n_train:],
        batch_size=BATCH_SIZE,
        shuffle=False,
    )

    # 모델 생성
    model = build_model(dropout=DROPOUT)
    model.to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=7, factor=0.5, verbose=False)
    criterion = nn.MSELoss()

    best_val_loss = float("inf")
    best_state: dict | None = None
    no_improve = 0

    for epoch in range(1, EPOCHS + 1):
        # --- 학습 ---
        model.train()
        train_loss = 0.0
        for d_idx, i_idx, q_enc, y_batch in train_loader:
            d_idx, i_idx, q_enc, y_batch = d_idx.to(device), i_idx.to(device), q_enc.to(device), y_batch.to(device)
            optimizer.zero_grad()
            pred = model(d_idx, i_idx, q_enc)
            loss = criterion(pred, y_batch)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * len(d_idx)
        train_loss /= n_train

        # --- 검증 ---
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for d_idx, i_idx, q_enc, y_batch in val_loader:
                d_idx, i_idx, q_enc, y_batch = d_idx.to(device), i_idx.to(device), q_enc.to(device), y_batch.to(device)
                pred = model(d_idx, i_idx, q_enc)
                val_loss += criterion(pred, y_batch).item() * len(d_idx)
        val_loss /= n_val

        scheduler.step(val_loss)

        if epoch % 20 == 0 or epoch == 1:
            logger.info("Epoch %3d | train_loss=%.6f | val_loss=%.6f", epoch, train_loss, val_loss)

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= PATIENCE:
                logger.info("Early stopping at epoch %d (best val_loss=%.6f)", epoch, best_val_loss)
                break

    # 최적 가중치 저장
    if best_state:
        model.load_state_dict(best_state)

    weights_path = WEIGHTS_DIR / "customer_mlp.pt"
    model.save_weights(weights_path)
    logger.info("가중치 저장 완료: %s", weights_path)

    # 매핑 저장 (identified_ratios 딕셔너리 + year_max 함께)
    save_mappings(identified_ratios=identified_ratios, year_max=year_max)
    logger.info("학습 완료 — best val_loss: %.6f", best_val_loss)


if __name__ == "__main__":
    train()
