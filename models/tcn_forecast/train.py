"""
TCN 모델 학습 스크립트 — 사전학습(서울 전체) + 파인튜닝(마포구)

GRU train.py 대비 변경점:
- GRUForecaster → TCNForecaster import
- freeze_gru() → freeze_tcn(), unfreeze_gru() → unfreeze_tcn()
- 가중치 저장 경로: tcn_forecast/weights/ (pretrained_tcn.pt, finetuned_mapo_tcn.pt)
- data_prep은 lstm_forecast에서 직접 import하여 재사용 (GRU와 동일)
- 학습 루프, 조기종료, sample_weight 처리 GRU/LSTM과 완전 동일

Usage:
    python -m models.tcn_forecast.train --mode pretrain
    python -m models.tcn_forecast.train --mode finetune

담당: B2 — 수지니
참조: models/gru_forecast/train.py (구조 동일)
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

import torch
import torch.nn as nn

# data_prep은 lstm_forecast에서 재사용 — GRU와 동일한 이유
# (guide-density Hot Deck, 31개 피처, EXCLUDE_COMBOS, 코로나 가중치 자동 적용)
from models.lstm_forecast.data_prep import DB_URL, prepare_dataloaders

from .model import WEIGHTS_DIR, TCNForecaster

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 기본 하이퍼파라미터
# ---------------------------------------------------------------------------

DEFAULT_PRETRAIN_CONFIG: dict = {
    "db_url": DB_URL,
    "dong_prefix": None,  # 서울 전체 데이터로 사전학습
    "csv_path": None,
    "window_size": 4,  # 4분기(1년) 입력 — receptive field=4와 일치
    "batch_size": 64,
    "val_ratio": 0.2,
    "target_col": "monthly_sales",
    "feature_cols": None,  # None = ALL_FEATURES (33개)
    # 모델 하이퍼파라미터
    "n_channels": 128,  # GRU의 hidden_size=128과 동일 조건
    "kernel_size": 2,  # receptive field 최적 커널 크기
    "dilations": [1, 2],  # receptive field = 1 + 1×(1+2) = 4 (window_size=4 커버)
    "dropout": 0.2,
    # 학습 하이퍼파라미터
    "epochs": 100,
    "lr": 1e-3,
    "weight_decay": 1e-5,
    "patience": 10,  # 조기종료: 10에폭 동안 개선 없으면 종료
    # 출력 경로 — tcn_forecast/weights/ 사용
    "save_path": str(WEIGHTS_DIR / "pretrained_tcn.pt"),
}

DEFAULT_FINETUNE_CONFIG: dict = {
    "db_url": DB_URL,
    "dong_prefix": "11440",  # 마포구만 파인튜닝
    "csv_path": None,
    "window_size": 4,  # 4분기(1년) 입력 — pretrain과 동일 조건
    "batch_size": 32,  # 파인튜닝은 배치 작게 (데이터 적음)
    "val_ratio": 0.2,
    "target_col": "monthly_sales",
    "feature_cols": None,
    # 모델 하이퍼파라미터
    "n_channels": 128,
    "kernel_size": 2,
    "dilations": [1, 2],  # receptive field = 4 (pretrain과 동일)
    "dropout": 0.2,
    # 파인튜닝 하이퍼파라미터
    "pretrained_path": str(WEIGHTS_DIR / "pretrained_tcn.pt"),
    "freeze_epochs": 10,  # 1단계: TCN 고정, FC만 학습
    "freeze_lr": 5e-4,
    "unfreeze_epochs": 50,  # 2단계: 전체 파라미터 낮은 학습률로 학습
    "unfreeze_lr": 1e-4,
    "weight_decay": 1e-5,
    "patience": 10,
    # 출력 경로
    "save_path": str(WEIGHTS_DIR / "finetuned_mapo_tcn.pt"),
}


# ---------------------------------------------------------------------------
# 학습 유틸리티
# ---------------------------------------------------------------------------


def _get_device() -> torch.device:
    """사용 가능한 디바이스를 반환한다. GPU 없으면 CPU 사용."""
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def _train_one_epoch(
    model: nn.Module,
    loader: torch.utils.data.DataLoader,
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer,
    device: torch.device,
) -> float:
    """1 에폭 학습을 수행하고 평균 loss를 반환한다.

    sample_weight 처리:
    - DataLoader에서 (X, y, w) 3-튜플이 오면 가중치 적용 MSE 사용
    - 코로나 시기(2020~2021) 데이터에 sample_weight=0.5 적용됨 (data_prep에서 설정)
    - w가 없으면 일반 MSELoss 사용
    GRU/LSTM train.py와 완전 동일한 로직 — 공정한 비교를 위해.
    """
    model.train()
    total_loss = 0.0
    n_batches = 0

    for batch in loader:
        # sample_weight 있는 경우 (3-튜플) 처리
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

        # 가중치 적용 손실 계산
        if w_batch is not None:
            # 코로나 시기 가중치 반영: (w * (pred - y)^2).mean()
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
    """검증 loss를 계산하여 반환한다. 역전파 없이 순전파만 수행."""
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
    label: str = "train",
) -> dict:
    """공통 학습 루프 (조기종료 포함).

    patience 에폭 동안 val_loss가 개선되지 않으면 종료.
    최적 state_dict를 메모리에 보존 후 반환.
    GRU/LSTM train.py와 완전 동일한 구조.

    Returns
    -------
    dict
        best_state, best_val_loss, train_losses, val_losses
    """
    best_val_loss = float("inf")
    best_state = model.get_best_state()
    wait = 0  # 개선 없는 에폭 카운트

    train_losses: list[float] = []
    val_losses: list[float] = []

    for epoch in range(1, epochs + 1):
        t0 = time.time()
        train_loss = _train_one_epoch(model, train_loader, criterion, optimizer, device)
        val_loss = _validate(model, val_loader, criterion, device)
        elapsed = time.time() - t0

        train_losses.append(train_loss)
        val_losses.append(val_loss)

        logger.info(
            "[%s] Epoch %3d/%d  train_loss=%.6f  val_loss=%.6f  (%.1fs)",
            label,
            epoch,
            epochs,
            train_loss,
            val_loss,
            elapsed,
        )

        # 조기종료 로직: val_loss 개선 시 best 상태 저장
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = model.get_best_state()
            wait = 0
        else:
            wait += 1
            if wait >= patience:
                logger.info(
                    "[%s] 조기 종료: val_loss가 %d 에폭 동안 개선되지 않음 (best=%.6f)",
                    label,
                    patience,
                    best_val_loss,
                )
                break

    return {
        "best_state": best_state,
        "best_val_loss": best_val_loss,
        "train_losses": train_losses,
        "val_losses": val_losses,
    }


# ---------------------------------------------------------------------------
# 사전학습 (서울 전체)
# ---------------------------------------------------------------------------


def pretrain(config: dict | None = None) -> Path:
    """서울 전체 데이터로 TCN 사전학습을 수행한다.

    학습 데이터: RDS의 seoul_district_sales + seoul_district_stores
    저장 파일: weights/pretrained_tcn.pt + pretrain_tcn_scalers.pkl

    Parameters
    ----------
    config : dict, optional
        하이퍼파라미터 오버라이드. None이면 DEFAULT_PRETRAIN_CONFIG 사용.

    Returns
    -------
    Path
        저장된 가중치 파일 경로.
    """
    cfg = {**DEFAULT_PRETRAIN_CONFIG, **(config or {})}
    device = _get_device()
    logger.info("TCN 사전학습 시작 (device=%s)", device)
    logger.info("Config: %s", {k: v for k, v in cfg.items() if k != "feature_cols"})

    # 데이터 로드 — lstm_forecast의 prepare_dataloaders 재사용
    train_loader, val_loader, feat_scaler, tgt_scaler, input_size = prepare_dataloaders(cfg)
    logger.info(
        "DataLoader 준비 완료: input_size=%d, train=%d, val=%d batches",
        input_size,
        len(train_loader),
        len(val_loader),
    )

    # TCN 모델 초기화
    model = TCNForecaster(
        input_size=input_size,
        n_channels=cfg["n_channels"],
        kernel_size=cfg["kernel_size"],
        dilations=cfg["dilations"],
        dropout=cfg["dropout"],
    ).to(device)

    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=cfg["lr"],
        weight_decay=cfg["weight_decay"],
    )

    # 학습 실행
    result = _train_loop(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        optimizer=optimizer,
        criterion=criterion,
        device=device,
        epochs=cfg["epochs"],
        patience=cfg["patience"],
        label="pretrain-tcn",
    )

    # 최적 가중치 저장
    model.load_state_dict(result["best_state"])
    save_path = Path(cfg["save_path"])
    model.save_weights(save_path)
    logger.info(
        "TCN 사전학습 완료. 가중치 저장: %s (best_val_loss=%.6f)",
        save_path,
        result["best_val_loss"],
    )

    # 스케일러 저장 — 추론 시 역변환에 필요
    # save_path stem에서 suffix 추출 (예: "pretrained_tcn_run2" → "_run2", "pretrained_tcn" → "")
    _pt_suffix = save_path.stem.replace("pretrained_tcn", "")
    _save_scalers(feat_scaler, tgt_scaler, save_path.parent / f"pretrain_tcn_scalers{_pt_suffix}.pkl")

    return save_path


# ---------------------------------------------------------------------------
# 파인튜닝 (마포구)
# ---------------------------------------------------------------------------


def finetune(config: dict | None = None) -> Path:
    """마포구 데이터로 파인튜닝을 수행한다.

    전략 (GRU/LSTM과 동일):
    1단계: TCN freeze, FC만 학습 (freeze_epochs, freeze_lr)
    2단계: 전체 unfreeze, 낮은 학습률로 학습 (unfreeze_epochs, unfreeze_lr)

    학습 데이터: RDS의 district_sales + store_quarterly (dong_prefix='11440')
    저장 파일: weights/finetuned_mapo_tcn.pt + finetune_tcn_scalers.pkl

    Parameters
    ----------
    config : dict, optional
        하이퍼파라미터 오버라이드. None이면 DEFAULT_FINETUNE_CONFIG 사용.

    Returns
    -------
    Path
        저장된 가중치 파일 경로.
    """
    cfg = {**DEFAULT_FINETUNE_CONFIG, **(config or {})}
    device = _get_device()
    logger.info("TCN 파인튜닝 시작 (device=%s)", device)
    logger.info("Config: %s", {k: v for k, v in cfg.items() if k != "feature_cols"})

    # 마포구 데이터 로드
    train_loader, val_loader, feat_scaler, tgt_scaler, input_size = prepare_dataloaders(cfg)
    logger.info("DataLoader 준비 완료: input_size=%d", input_size)

    # TCN 모델 초기화 + 사전학습 가중치 로드
    model = TCNForecaster(
        input_size=input_size,
        n_channels=cfg["n_channels"],
        kernel_size=cfg["kernel_size"],
        dilations=cfg["dilations"],
        dropout=cfg["dropout"],
    ).to(device)

    pretrained_path = Path(cfg["pretrained_path"])
    if not pretrained_path.exists():
        raise FileNotFoundError(
            f"TCN 사전학습 가중치를 찾을 수 없습니다: {pretrained_path}\n"
            "먼저 --mode pretrain 으로 사전학습을 실행하세요."
        )

    # 피처 수 차이가 있을 경우 부분 복사로 로드
    # (서울 전체 피처 수 != 마포구 피처 수일 가능성 대비)
    try:
        model.load_weights(pretrained_path, strict=True)
        logger.info("사전학습 가중치 로드 완료 (strict): %s", pretrained_path)
    except RuntimeError:
        # 피처 수 불일치 시 부분 복사
        model.load_weights_partial(pretrained_path)
        logger.info("사전학습 가중치 부분 복사 로드 완료: %s", pretrained_path)

    criterion = nn.MSELoss()

    # ----- 1단계: TCN freeze, FC만 학습 -----
    logger.info("=== TCN 파인튜닝 1단계: TCN freeze, FC만 학습 ===")
    model.freeze_tcn()
    optimizer_fc = torch.optim.Adam(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=cfg["freeze_lr"],
        weight_decay=cfg["weight_decay"],
    )

    result_fc = _train_loop(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        optimizer=optimizer_fc,
        criterion=criterion,
        device=device,
        epochs=cfg["freeze_epochs"],
        patience=cfg["patience"],
        label="finetune-tcn-fc",
    )
    model.load_state_dict(result_fc["best_state"])

    # ----- 2단계: 전체 unfreeze, 낮은 학습률 -----
    logger.info("=== TCN 파인튜닝 2단계: 전체 unfreeze, lr=%.1e ===", cfg["unfreeze_lr"])
    model.unfreeze_tcn()
    optimizer_all = torch.optim.Adam(
        model.parameters(),
        lr=cfg["unfreeze_lr"],
        weight_decay=cfg["weight_decay"],
    )

    result_all = _train_loop(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        optimizer=optimizer_all,
        criterion=criterion,
        device=device,
        epochs=cfg["unfreeze_epochs"],
        patience=cfg["patience"],
        label="finetune-tcn-all",
    )

    # 최적 가중치 저장
    model.load_state_dict(result_all["best_state"])
    save_path = Path(cfg["save_path"])
    model.save_weights(save_path)
    logger.info(
        "TCN 파인튜닝 완료. 가중치 저장: %s (best_val_loss=%.6f)",
        save_path,
        result_all["best_val_loss"],
    )

    # 스케일러 저장
    # save_path stem에서 suffix 추출 (예: "finetuned_mapo_tcn_run2" → "_run2", "finetuned_mapo_tcn" → "")
    _ft_suffix = save_path.stem.replace("finetuned_mapo_tcn", "")
    _save_scalers(feat_scaler, tgt_scaler, save_path.parent / f"finetune_tcn_scalers{_ft_suffix}.pkl")

    return save_path


# ---------------------------------------------------------------------------
# 스케일러 저장/로드 유틸
# ---------------------------------------------------------------------------


def _save_scalers(
    feature_scaler: object,
    target_scaler: object,
    path: Path,
) -> None:
    """스케일러 객체를 pickle로 저장한다.

    추론 시 역변환(inverse_transform)에 필요하므로 반드시 저장.
    GRU/LSTM과 동일한 저장 포맷 사용.
    """
    import pickle

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump({"feature_scaler": feature_scaler, "target_scaler": target_scaler}, f)
    logger.info("스케일러 저장: %s", path)


def load_scalers(path: str | Path) -> tuple:
    """저장된 스케일러를 로드한다.

    Returns
    -------
    feature_scaler, target_scaler
    """
    import pickle

    with open(path, "rb") as f:
        data = pickle.load(f)  # noqa: S301
    return data["feature_scaler"], data["target_scaler"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI 엔트리포인트: --mode pretrain / finetune"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="TCN 매출 예측 모델 학습")
    parser.add_argument(
        "--mode",
        choices=["pretrain", "finetune"],
        required=True,
        help="학습 모드: pretrain(서울 전체) 또는 finetune(마포구)",
    )
    parser.add_argument("--db-url", type=str, default=None, help="PostgreSQL 접속 URL")
    parser.add_argument("--csv-path", type=str, default=None, help="CSV 파일 경로 (DB fallback)")
    parser.add_argument("--epochs", type=int, default=None, help="최대 에폭 수")
    parser.add_argument("--lr", type=float, default=None, help="학습률")
    parser.add_argument("--batch-size", type=int, default=None, help="배치 크기")
    parser.add_argument("--patience", type=int, default=None, help="조기 종료 patience")
    parser.add_argument("--window-size", type=int, default=None, help="입력 시퀀스 길이")
    parser.add_argument(
        "--save-suffix",
        type=str,
        default=None,
        help="가중치/스케일러 파일명 suffix (예: run2 → pretrained_tcn_run2.pt, pretrain_tcn_scalers_run2.pkl)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="재현성을 위한 랜덤 시드 (미설정 시 비결정적 학습)",
    )
    args = parser.parse_args()

    # 시드 설정 (재현성) — --seed 지정 시에만 실행, 미지정 시 기존과 동일하게 동작
    if args.seed is not None:
        import random

        import numpy as np

        random.seed(args.seed)  # Python 표준 random 시드 고정
        np.random.seed(args.seed)  # NumPy 시드 고정
        torch.manual_seed(args.seed)  # PyTorch CPU 시드 고정
        torch.cuda.manual_seed_all(args.seed)  # PyTorch GPU 시드 고정 (CPU 환경에서도 무해)

    # CLI 인자로 config 오버라이드
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

    # --save-suffix 처리: suffix가 있으면 가중치 저장 경로를 suffix 포함 경로로 교체
    # suffix 없으면 overrides에 save_path 미포함 → DEFAULT_*_CONFIG 기본값 그대로 사용
    if args.save_suffix:
        s = args.save_suffix
        if args.mode == "pretrain":
            overrides["save_path"] = str(WEIGHTS_DIR / f"pretrained_tcn_{s}.pt")
        else:
            overrides["save_path"] = str(WEIGHTS_DIR / f"finetuned_mapo_tcn_{s}.pt")
            overrides["pretrained_path"] = str(WEIGHTS_DIR / f"pretrained_tcn_{s}.pt")

    if args.mode == "pretrain":
        pretrain(overrides if overrides else None)
    else:
        finetune(overrides if overrides else None)


if __name__ == "__main__":
    main()
