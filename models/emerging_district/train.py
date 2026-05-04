"""
신흥 상권 조기 감지 모델 학습

학습 순서:
    1. district_sales + store_quarterly 로드
    2. sliding window (8분기) 생성
    3. LSTM Autoencoder 학습 (정상 패턴 재구성)
    4. train 전체 reconstruction error 분포 → 95th percentile = threshold
    5. 가중치(autoencoder.pt) + 메타(autoencoder_meta.pkl) 저장

Usage:
    python -m models.emerging_district.train

담당: B2 — 수지니
"""

from __future__ import annotations

import logging
import pickle

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from models.emerging_district.data_prep import DB_URL, EMERGING_FEATURES, build_windows, load_emerging_data
from models.emerging_district.model import WEIGHTS_DIR, LSTMAutoencoder

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

DEFAULT_CONFIG: dict = {
    "db_url": DB_URL,
    "dong_prefix": "11440",
    "window_size": 8,
    "val_ratio": 0.2,
    "epochs": 50,
    "lr": 1e-3,
    "batch_size": 32,
    "patience": 10,
    "hidden_size": 64,
    "num_layers": 2,
    "dropout": 0.2,
    "threshold_percentile": 95,
    "weights_path": str(WEIGHTS_DIR / "autoencoder.pt"),
    "meta_path": str(WEIGHTS_DIR / "autoencoder_meta.pkl"),
}


def train(config: dict | None = None) -> None:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 데이터 준비
    logger.info("데이터 로드 중...")
    df = load_emerging_data(db_url=cfg["db_url"], dong_prefix=cfg["dong_prefix"])
    X, meta_rows, _ = build_windows(df, window_size=cfg["window_size"])
    logger.info("윈도우 생성: %d 샘플, shape=%s", len(X), X.shape)

    # 2. train/val split (시간순 유지)
    n_val = max(1, int(len(X) * cfg["val_ratio"]))
    X_tr, X_val = X[:-n_val], X[-n_val:]
    logger.info("train=%d, val=%d", len(X_tr), len(X_val))

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("학습 디바이스: %s", device)

    # 3. 모델 초기화
    input_size = len(EMERGING_FEATURES)
    model = LSTMAutoencoder(
        input_size=input_size,
        hidden_size=cfg["hidden_size"],
        num_layers=cfg["num_layers"],
        dropout=cfg["dropout"],
    ).to(device)

    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=cfg["lr"])

    ds_tr = TensorDataset(torch.from_numpy(X_tr))
    loader = DataLoader(ds_tr, batch_size=cfg["batch_size"], shuffle=True)
    X_val_t = torch.from_numpy(X_val).to(device)

    # 4. 학습
    best_val_loss = float("inf")
    patience_cnt = 0
    best_state = None

    for epoch in range(1, cfg["epochs"] + 1):
        model.train()
        train_loss = 0.0
        for (xb,) in loader:
            xb = xb.to(device)
            optimizer.zero_grad()
            recon = model(xb)
            loss = criterion(recon, xb)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * len(xb)
        train_loss /= len(X_tr)

        # 검증
        model.eval()
        with torch.no_grad():
            recon_val = model(X_val_t)
            val_loss = criterion(recon_val, X_val_t).item()

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            patience_cnt = 0
        else:
            patience_cnt += 1

        if epoch % 10 == 0:
            logger.info(
                "[AE] Epoch %2d/%d  train=%.6f  val=%.6f  best=%.6f",
                epoch,
                cfg["epochs"],
                train_loss,
                val_loss,
                best_val_loss,
            )

        if patience_cnt >= cfg["patience"]:
            logger.info("[AE] 조기종료 (epoch=%d, best_val_loss=%.6f)", epoch, best_val_loss)
            break

    if best_state:
        model.load_state_dict(best_state)

    # 5. threshold 계산 (train reconstruction error 분포의 95th percentile)
    model.eval()
    X_tr_t = torch.from_numpy(X_tr).to(device)
    errs: list[np.ndarray] = []
    with torch.no_grad():
        for i in range(0, len(X_tr_t), 128):
            batch = X_tr_t[i : i + 128]
            recon_b = model(batch)
            err = ((recon_b - batch) ** 2).mean(dim=(1, 2)).cpu().numpy()
            errs.append(err)

    train_errors = np.concatenate(errs)
    threshold = float(np.percentile(train_errors, cfg["threshold_percentile"]))
    logger.info(
        "threshold (p%d) = %.6f  (mean=%.6f, std=%.6f)",
        cfg["threshold_percentile"],
        threshold,
        train_errors.mean(),
        train_errors.std(),
    )

    # per-quarter (last timestep) MSE 분포 — consecutive 메트릭 분기 단위 임계
    qerrs: list[np.ndarray] = []
    with torch.no_grad():
        for i in range(0, len(X_tr_t), 128):
            batch = X_tr_t[i : i + 128]
            recon_b = model(batch)
            qerr = ((recon_b[:, -1, :] - batch[:, -1, :]) ** 2).mean(dim=-1).cpu().numpy()
            qerrs.append(qerr)
    quarter_errors = np.concatenate(qerrs)
    quarter_threshold = float(np.percentile(quarter_errors, cfg["threshold_percentile"]))
    logger.info(
        "quarter_threshold (p%d) = %.6f  (mean=%.6f, std=%.6f)",
        cfg["threshold_percentile"],
        quarter_threshold,
        quarter_errors.mean(),
        quarter_errors.std(),
    )

    # 6. 저장
    model.save_weights(cfg["weights_path"])

    meta = {
        "input_size": input_size,
        "hidden_size": cfg["hidden_size"],
        "num_layers": cfg["num_layers"],
        "window_size": cfg["window_size"],
        "threshold": threshold,
        "quarter_threshold": quarter_threshold,
        "threshold_percentile": cfg["threshold_percentile"],
        "feature_names": list(EMERGING_FEATURES),
        "best_val_loss": best_val_loss,
    }
    with open(cfg["meta_path"], "wb") as f:
        pickle.dump(meta, f)
    logger.info("메타 저장: %s", cfg["meta_path"])
    logger.info("학습 완료 — best_val_loss=%.6f, threshold=%.6f", best_val_loss, threshold)


if __name__ == "__main__":
    train()
