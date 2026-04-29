"""
생활인구 유동인구 TCN 모델 학습 스크립트 (v2)

living_population → 동×시간대 분기 집계 → TCNForecaster 학습

16개 동 × 24시간대 = 384 그룹 × ~20 시퀀스 = ~7,680 시퀀스
단일 학습 (마포구 단일 지역 — pretrain/finetune 불필요)

window_size=8, dilations=[1,2,4] → RF = 1 + 1×(1+2+4) = 8

v2 변경점 (Plan: docs/superpowers/plans/2026-04-28-living-pop-forecast-normalization.md):
- dong_one_hot 16-dim 입력 (5 → 21차원)
- Train/Val/Test 70/15/15 시간순 분할
- metadata json 저장 (test_loss, feature_columns, hyperparameters 등)
- LODO 인자 (`exclude_dongs`, `save_suffix`) 지원
- 반환값: dict (train_loss, val_loss, test_loss, epochs, save_path)

Usage:
    python -m models.living_pop_forecast.train
    python -m models.living_pop_forecast.train --epochs 50 --seed 42

담당: B2 — 수지니
참조: models/tcn_forecast/train.py (구조 동일)
"""

from __future__ import annotations

import argparse
import copy
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

from .data_prep import (
    ALL_FEATURES,
    DB_URL,
    TARGET_COL,
    _add_dong_one_hot,
    build_timeseries,
    load_living_population,
    prepare_dataloaders,
    prepare_sequences,
)

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
    # v2: Train/Val/Test 70/15/15 시간순 분할
    "train_ratio": 0.70,
    "val_ratio": 0.15,
    "test_ratio": 0.15,
    "target_col": TARGET_COL,
    "feature_cols": None,  # None = ALL_FEATURES (21개)
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
    "seed": None,
    # LODO 지원
    "exclude_dongs": None,  # list[str] | None — 학습/검증/테스트에서 모두 제외
    "save_suffix": "",  # "" | "lodo_<dong>" 등
    # 출력 (v2)
    "save_path": None,  # None이면 자동 생성: living_pop_tcn_v2[_<suffix>].pt
    "scalers_path": None,  # None이면 자동 생성: living_pop_scalers_v2[_<suffix>].pkl
    "metadata_path": None,  # None이면 자동 생성: living_pop_metadata_v2[_<suffix>].json
    "version": "v2",
}


# ---------------------------------------------------------------------------
# 학습 유틸 (tcn_forecast/train.py와 동일한 구조)
# ---------------------------------------------------------------------------


def _get_device() -> torch.device:
    return torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")


def _set_seed(seed: int | None) -> None:
    if seed is None:
        return
    import random

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def _train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
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
def _evaluate(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> float:
    """val/test 공용 평가 — 가중치 없이 순수 MSE."""
    model.eval()
    total_loss = 0.0
    n_batches = 0

    for batch in loader:
        # weight 가 있어도 평가에는 사용하지 않음 (공정한 비교)
        if len(batch) == 3:
            X_batch, y_batch, _ = batch
        else:
            X_batch, y_batch = batch
        X_batch = X_batch.to(device)
        y_batch = y_batch.to(device)
        pred = model(X_batch)
        loss = criterion(pred, y_batch)
        total_loss += loss.item()
        n_batches += 1

    return total_loss / max(n_batches, 1)


# 호환 alias (tcn_forecast 와 동일 시그니처 유지)
_validate = _evaluate


def _train_loop(
    model: TCNForecaster,
    train_loader: DataLoader,
    val_loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    criterion: nn.Module,
    device: torch.device,
    epochs: int,
    patience: int,
) -> dict:
    best_val_loss = float("inf")
    best_train_loss = float("inf")
    best_state = copy.deepcopy(model.state_dict())
    wait = 0
    epochs_trained = 0

    for epoch in range(1, epochs + 1):
        t0 = time.time()
        train_loss = _train_one_epoch(model, train_loader, criterion, optimizer, device)
        val_loss = _evaluate(model, val_loader, criterion, device)
        elapsed = time.time() - t0
        epochs_trained = epoch

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
            best_train_loss = train_loss
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

    return {
        "best_state": best_state,
        "best_val_loss": best_val_loss,
        "best_train_loss": best_train_loss,
        "epochs_trained": epochs_trained,
    }


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
# v2 데이터 파이프라인 (Train/Val/Test 70/15/15 시간순 분할 + LODO)
# ---------------------------------------------------------------------------


def _build_v2_loaders(cfg: dict) -> dict:
    """v2 파이프라인: 21차원 입력 + 시간순 70/15/15 분할 + exclude_dongs 필터.

    Returns
    -------
    dict
        keys: train_loader, val_loader, test_loader, feat_scaler, tgt_scaler,
              input_size, feature_columns, sizes={train,val,test}
    """
    db_url = cfg.get("db_url", DB_URL)
    csv_path = cfg.get("csv_path", None)
    window_size = cfg.get("window_size", 8)
    batch_size = cfg.get("batch_size", 64)
    target_col = cfg.get("target_col", TARGET_COL)
    feature_cols = cfg.get("feature_cols") or ALL_FEATURES
    exclude_dongs = cfg.get("exclude_dongs") or []

    train_ratio = cfg.get("train_ratio", 0.70)
    val_ratio = cfg.get("val_ratio", 0.15)
    test_ratio = cfg.get("test_ratio", 0.15)
    total_ratio = train_ratio + val_ratio + test_ratio
    if abs(total_ratio - 1.0) > 1e-6:
        raise ValueError(f"train_ratio + val_ratio + test_ratio == 1.0 이어야 합니다. (현재 합={total_ratio})")

    mode = cfg.get("mode", "absolute")  # "absolute" | "residual"
    add_group_features = bool(cfg.get("add_group_features", False))

    df = load_living_population(db_url=db_url, csv_path=csv_path)

    # group features 활성화 시: train_end_quarter 자동 계산 (또는 cfg 에서 override).
    # quarter 정렬된 unique 분기 리스트의 train_ratio 위치를 cutoff 로 사용 →
    # build_timeseries 가 그 분기 이하 row 만으로 group_mean 계산 (data leakage 방지).
    train_end_quarter: int | None = cfg.get("train_end_quarter")
    if add_group_features and train_end_quarter is None:
        unique_q = sorted(df["quarter"].unique().tolist())
        if not unique_q:
            raise ValueError("quarter 컬럼이 비어있습니다.")
        cutoff_idx = max(0, int(len(unique_q) * train_ratio) - 1)
        train_end_quarter = int(unique_q[cutoff_idx])
        logger.info(
            "group features: train_end_quarter 자동 계산 = %d (train_ratio=%.2f, %d quarters)",
            train_end_quarter,
            train_ratio,
            len(unique_q),
        )

    df = build_timeseries(df, add_group_features=add_group_features, train_end_quarter=train_end_quarter)

    # LODO: exclude_dongs 제거 (시퀀스 생성 전 필터)
    if exclude_dongs:
        before = len(df)
        df = df[~df["dong_code"].isin(list(exclude_dongs))].reset_index(drop=True)
        logger.info(
            "LODO: exclude_dongs=%s 적용 (rows %d → %d)",
            list(exclude_dongs),
            before,
            len(df),
        )

    # dong_one_hot — 항상 마포구 16동 기준 (LODO 제외 동도 0 컬럼만 채워지므로 문제없음)
    df = _add_dong_one_hot(df)
    logger.info("dong_one_hot 16-dim 추가 완료: %s", df.shape)

    X, y, feat_scaler, tgt_scaler, w = prepare_sequences(
        df, window_size=window_size, target_col=target_col, feature_cols=feature_cols, mode=mode
    )
    logger.info("시퀀스 생성 완료: X=%s, y=%s, mode=%s", X.shape, y.shape, mode)

    # 시간순 70/15/15 — prepare_sequences가 (dong_code, time_zone) 그룹별 sliding이라
    # 인덱스 단순 분할은 동×시간대 연속 블록을 끊는다. 여기서는 단순 인덱스 분할로 통일
    # (legacy 80/20 val_ratio도 인덱스 분할이었으므로 동일 패턴 유지).
    n = len(X)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)
    n_test = n - n_train - n_val
    if n_train <= 0 or n_val <= 0 or n_test <= 0:
        raise ValueError(f"분할 실패: n={n}, train={n_train}, val={n_val}, test={n_test}. 데이터 양이 너무 적습니다.")

    X_train = X[:n_train]
    X_val = X[n_train : n_train + n_val]
    X_test = X[n_train + n_val :]
    y_train = y[:n_train]
    y_val = y[n_train : n_train + n_val]
    y_test = y[n_train + n_val :]
    w_train = w[:n_train]

    train_ds = TensorDataset(torch.from_numpy(X_train), torch.from_numpy(y_train), torch.from_numpy(w_train))
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
        "input_size": X.shape[2],
        "feature_columns": list(feature_cols),
        "sizes": {"train": int(n_train), "val": int(n_val), "test": int(n_test)},
        "mode": mode,
        "add_group_features": add_group_features,
        "train_end_quarter": train_end_quarter,
    }


# ---------------------------------------------------------------------------
# 출력 경로 빌더
# ---------------------------------------------------------------------------


def _resolve_output_paths(cfg: dict) -> dict:
    """version + save_suffix 기반으로 가중치/스케일러/메타 경로 결정 (legacy v1과 분리)."""
    suffix = cfg.get("save_suffix") or ""
    suf = f"_{suffix}" if suffix else ""
    ver = cfg.get("version", "v2")

    save_path = cfg.get("save_path") or str(WEIGHTS_DIR / f"living_pop_tcn_{ver}{suf}.pt")
    scalers_path = cfg.get("scalers_path") or str(WEIGHTS_DIR / f"living_pop_scalers_{ver}{suf}.pkl")
    metadata_path = cfg.get("metadata_path") or str(WEIGHTS_DIR / f"living_pop_metadata_{ver}{suf}.json")
    return {
        "save_path": Path(save_path),
        "scalers_path": Path(scalers_path),
        "metadata_path": Path(metadata_path),
    }


# ---------------------------------------------------------------------------
# 학습 진입점 (v2)
# ---------------------------------------------------------------------------


def train(config: dict | None = None) -> dict:
    """마포구 생활인구 데이터로 TCN 유동인구 예측 모델을 학습한다 (v2).

    Parameters
    ----------
    config : dict, optional
        하이퍼파라미터 오버라이드. LODO 사용 시 다음 키 필요:
        - ``exclude_dongs`` (list[str]): 학습에서 제외할 동들
        - ``save_suffix`` (str): 가중치/메타 파일명 suffix
        - ``epochs``, ``patience``, ``seed``: 학습 설정

    Returns
    -------
    dict
        keys: ``train_loss``, ``val_loss``, ``test_loss``, ``epochs``,
              ``save_path``, ``metadata_path``, ``scalers_path``,
              ``input_size``, ``sizes``.
    """
    cfg = {**DEFAULT_TRAIN_CONFIG, **(config or {})}
    _set_seed(cfg.get("seed"))

    device = _get_device()
    logger.info(
        "생활인구 TCN v2 학습 시작 (device=%s, suffix=%r, exclude=%s)",
        device,
        cfg.get("save_suffix") or "",
        cfg.get("exclude_dongs") or [],
    )

    bundle = _build_v2_loaders(cfg)
    train_loader = bundle["train_loader"]
    val_loader = bundle["val_loader"]
    test_loader = bundle["test_loader"]
    feat_scaler = bundle["feat_scaler"]
    tgt_scaler = bundle["tgt_scaler"]
    input_size = bundle["input_size"]
    feature_columns = bundle["feature_columns"]
    sizes = bundle["sizes"]

    logger.info(
        "DataLoader 준비: input_size=%d, train=%d, val=%d, test=%d batches",
        input_size,
        len(train_loader),
        len(val_loader),
        len(test_loader),
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

    # best_state 로드 후 test 평가
    model.load_state_dict(result["best_state"])
    test_loss = _evaluate(model, test_loader, criterion, device)
    logger.info("Test 평가: test_loss=%.6f (best_val=%.6f)", test_loss, result["best_val_loss"])

    # 출력 경로 (v2 — legacy living_pop_tcn.pt 보존)
    paths = _resolve_output_paths(cfg)
    save_path = paths["save_path"]
    scalers_path = paths["scalers_path"]
    metadata_path = paths["metadata_path"]

    save_path.parent.mkdir(parents=True, exist_ok=True)
    model.save_weights(save_path)
    logger.info("가중치 저장: %s (best_val=%.6f)", save_path, result["best_val_loss"])
    _save_scalers(feat_scaler, tgt_scaler, scalers_path)

    # metadata json 저장
    metadata = {
        "version": cfg.get("version", "v2"),
        "mode": cfg.get("mode", "absolute"),
        "input_size": int(input_size),
        "feature_columns": list(feature_columns),
        "n_dong": 16,
        "exclude_dongs": list(cfg.get("exclude_dongs") or []),
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
        "save_path": str(save_path),
        "scalers_path": str(scalers_path),
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
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="생활인구 유동인구 TCN 학습 (v2)")
    parser.add_argument("--db-url", type=str, default=None)
    parser.add_argument("--csv-path", type=str, default=None, help="living_pop_quarterly.csv 경로")
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--lr", type=float, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--patience", type=int, default=None)
    parser.add_argument("--window-size", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--exclude-dongs",
        type=str,
        default=None,
        help="LODO: 제외할 dong_code 콤마 구분 (예: 11440555,11440565)",
    )
    parser.add_argument("--save-suffix", type=str, default=None)
    parser.add_argument("--version", type=str, default=None, help="가중치 버전 태그 (예: v2, v3)")
    args = parser.parse_args()

    overrides: dict = {}
    if args.db_url:
        overrides["db_url"] = args.db_url
    if args.csv_path:
        overrides["csv_path"] = args.csv_path
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
    if args.exclude_dongs:
        overrides["exclude_dongs"] = [d.strip() for d in args.exclude_dongs.split(",") if d.strip()]
    if args.save_suffix:
        overrides["save_suffix"] = args.save_suffix
    if args.version:
        overrides["version"] = args.version

    result = train(overrides if overrides else None)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


# `prepare_dataloaders` re-export (legacy 호환 — 외부에서 from .train import 시)
__all__ = [
    "DEFAULT_TRAIN_CONFIG",
    "WEIGHTS_DIR",
    "load_scalers",
    "prepare_dataloaders",
    "train",
]


if __name__ == "__main__":
    main()
