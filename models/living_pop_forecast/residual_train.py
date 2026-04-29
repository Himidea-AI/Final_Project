"""Residual learning train.

지원 mode:
    - "residual" (기본): target = y[t] - y[t-1]. last_value + Δŷ = ŷ.
    - "group_residual" (option B explicit decomposition):
        target = (y[t] - group_mean) / group_mean. group_mean × (1 + r̂) = ŷ.
        모델은 그룹 평균 대비 편차 비율만 학습 → cross-group variance 가 task 외부로 분리됨.

기대 효과: v2 (MASE 4.54) → v4_residual (MASE ~0.9) → v5_group_residual (MASE ~0.75)
저장: living_pop_tcn_v{4,5}_*.pt + scalers + metadata.json (mode 기록)

Group features 변형 (v5):
    - feature_set="full" (POP_FEATURES_GROUP_RESIDUAL): group_mean + group_relative.
    - feature_set="rel_only" (POP_FEATURES_GROUP_REL_ONLY): group_relative 만.
      (1차 시도 v5_group_residual MASE 1.018 악화 → group_mean 제거 재시도.)
    - feature_set="decomp" (option B): group_relative 만 입력 + mode="group_residual".
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime

import torch
import torch.nn as nn

from models.tcn_forecast.model import TCNForecaster

from .data_prep import (
    DONG_FEATURES,
    POP_FEATURES_GROUP_REL_ONLY,
    POP_FEATURES_GROUP_RESIDUAL,
    TARGET_COL,
)
from .train import (
    DEFAULT_TRAIN_CONFIG,
    WEIGHTS_DIR,
    _build_v2_loaders,
    _evaluate,
    _get_device,
    _resolve_output_paths,
    _save_scalers,
    _set_seed,
    _train_loop,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Group feature-set ↔ (피처 리스트, 기본 version) 매핑.
# CLI ``--group-feature-set`` / config ``group_feature_set`` 키로 선택.
# DRY: 신규 group 변형 추가 시 이 dict 만 갱신.
# ---------------------------------------------------------------------------

GROUP_FEATURE_SETS: dict[str, dict] = {
    "full": {
        "pop_features": list(POP_FEATURES_GROUP_RESIDUAL),
        "default_version": "v5_group_residual",
        "mode": "residual",
    },
    "rel_only": {
        "pop_features": list(POP_FEATURES_GROUP_REL_ONLY),
        "default_version": "v5_group_rel_only",
        "mode": "residual",
    },
    "decomp": {
        # option B: 입력에 group_relative 유지 + 타깃은 (y - group_mean)/group_mean 비율.
        "pop_features": list(POP_FEATURES_GROUP_REL_ONLY),
        "default_version": "v5_group_decomp",
        "mode": "group_residual",
    },
}


def _resolve_group_feature_set(name: str) -> dict:
    """이름 → spec dict 변환 (unknown 시 ValueError 메시지 명시)."""
    if name not in GROUP_FEATURE_SETS:
        raise ValueError(f"알 수 없는 group_feature_set: {name!r}. 허용값: {sorted(GROUP_FEATURE_SETS.keys())}")
    return GROUP_FEATURE_SETS[name]


def train_residual(config: dict | None = None) -> dict:
    """Residual learning 학습 진입점 — train.py.train() 과 동일 시그니처/반환.

    cfg 에 mode="residual" 강제. add_group_features=True 면 v5_group_residual 로 전환.
    학습 utility (_train_one_epoch, _evaluate) 는 train.py 재사용.
    """
    cfg = {**DEFAULT_TRAIN_CONFIG, **(config or {})}
    user_overrides = config or {}
    add_group_features = bool(cfg.get("add_group_features", False))

    # group feature-set 선택 (full / rel_only / decomp / ...). add_group_features True 일 때만 의미.
    group_feature_set: str | None = cfg.get("group_feature_set")
    if add_group_features:
        if group_feature_set is None:
            group_feature_set = "full"  # backward compat (v5_group_residual 기존 동작)
        spec = _resolve_group_feature_set(group_feature_set)
    else:
        spec = None

    # mode: spec.mode > user > 기본 "residual". "group_residual" 은 option B 전용.
    if spec is not None and not user_overrides.get("mode"):
        cfg["mode"] = spec["mode"]
    else:
        cfg.setdefault("mode", "residual")

    # version 자동 결정: user 명시 > spec.default_version > add_group_features 기본 > v4_residual.
    user_version = user_overrides.get("version")
    if user_version:
        cfg["version"] = user_version
    elif spec is not None:
        cfg["version"] = spec["default_version"]
    else:
        cfg["version"] = "v4_residual"

    # add_group_features 시 feature_cols 자동 확장 (spec 의 pop_features + dong_one_hot).
    if add_group_features and not user_overrides.get("feature_cols") and spec is not None:
        cfg["feature_cols"] = list(spec["pop_features"]) + list(DONG_FEATURES)

    # save_path 등 자동 생성 경로도 v2 가 박혀있을 가능성 → strip if not user-provided
    for k in ("save_path", "scalers_path", "metadata_path"):
        if k not in user_overrides:
            cfg[k] = None

    cfg["group_feature_set"] = group_feature_set  # metadata 기록용
    _set_seed(cfg.get("seed"))

    device = _get_device()
    logger.info(
        "생활인구 TCN %s 학습 시작 (device=%s, suffix=%r, group_feature_set=%r)",
        cfg["version"],
        device,
        cfg.get("save_suffix") or "",
        group_feature_set,
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
        "DataLoader 준비: input_size=%d, mode=%s, train=%d, val=%d, test=%d batches",
        input_size,
        bundle["mode"],
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

    # 학습 loop — train.py 의 _train_loop 재사용 (DRY).
    # residual 모드에서도 학습 절차 (early stopping, best_state 추적) 는 동일.
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
    best_state = result["best_state"]
    best_val_loss = result["best_val_loss"]
    best_train_loss = result["best_train_loss"]
    epochs_trained = result["epochs_trained"]

    model.load_state_dict(best_state)
    test_loss = _evaluate(model, test_loader, criterion, device)
    logger.info("Test 평가: test_loss=%.6f (best_val=%.6f)", test_loss, best_val_loss)

    # 출력 경로 (v4_residual)
    paths = _resolve_output_paths(cfg)
    save_path = paths["save_path"]
    scalers_path = paths["scalers_path"]
    metadata_path = paths["metadata_path"]

    save_path.parent.mkdir(parents=True, exist_ok=True)
    model.save_weights(save_path)
    logger.info("가중치 저장: %s (best_val=%.6f)", save_path, best_val_loss)
    _save_scalers(feat_scaler, tgt_scaler, scalers_path)

    metadata = {
        "version": cfg.get("version"),
        "mode": cfg.get("mode", "residual"),
        "add_group_features": bool(cfg.get("add_group_features", False)),
        "group_feature_set": group_feature_set,
        "train_end_quarter": bundle.get("train_end_quarter"),
        "input_size": int(input_size),
        "feature_columns": list(feature_columns),
        "n_dong": 16,
        "exclude_dongs": list(cfg.get("exclude_dongs") or []),
        "save_suffix": cfg.get("save_suffix") or "",
        "best_val_loss": float(best_val_loss),
        "test_loss": float(test_loss),
        "train_size": int(sizes["train"]),
        "val_size": int(sizes["val"]),
        "test_size": int(sizes["test"]),
        "epochs_trained": int(epochs_trained),
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
        "target_col": cfg.get("target_col", TARGET_COL),
        "save_path": str(save_path),
        "scalers_path": str(scalers_path),
        "trained_at": datetime.now().isoformat(),
    }
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("metadata 저장: %s", metadata_path)

    return {
        "train_loss": float(best_train_loss),
        "val_loss": float(best_val_loss),
        "test_loss": float(test_loss),
        "epochs": int(epochs_trained),
        "save_path": str(save_path),
        "metadata_path": str(metadata_path),
        "scalers_path": str(scalers_path),
        "input_size": int(input_size),
        "sizes": sizes,
        "mode": cfg.get("mode", "residual"),
    }


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="생활인구 유동인구 TCN residual learning 학습 (v4_residual)")
    parser.add_argument("--db-url", type=str, default=None)
    parser.add_argument("--csv-path", type=str, default=None)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--lr", type=float, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--patience", type=int, default=None)
    parser.add_argument("--window-size", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--exclude-dongs", type=str, default=None)
    parser.add_argument("--save-suffix", type=str, default=None)
    parser.add_argument("--version", type=str, default=None)
    parser.add_argument(
        "--add-group-features",
        action="store_true",
        help="v5: group features 추가 (Plan Task 3 / Task 3 재시도)",
    )
    parser.add_argument(
        "--group-feature-set",
        type=str,
        default=None,
        choices=sorted(GROUP_FEATURE_SETS.keys()),
        help=(
            "Group features 변형 선택. "
            "'full' = group_mean + group_relative (v5_group_residual, 1차). "
            "'rel_only' = group_relative 만 (v5_group_rel_only, 재시도). "
            "'decomp' = explicit decomposition target (v5_group_decomp, option B)."
        ),
    )
    parser.add_argument(
        "--mode",
        type=str,
        default=None,
        choices=("residual", "group_residual"),
        help=(
            "타깃 인코딩 mode. 'residual' (기본) = Δy. "
            "'group_residual' = (y - group_mean)/group_mean (group_feature_set 'decomp' 와 함께 사용)."
        ),
    )
    parser.add_argument(
        "--train-end-quarter",
        type=int,
        default=None,
        help="group_mean 계산 cutoff (None 이면 train_ratio 로 자동 계산)",
    )
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
    if args.add_group_features:
        overrides["add_group_features"] = True
    if args.group_feature_set:
        overrides["group_feature_set"] = args.group_feature_set
        # group_feature_set 명시 시 add_group_features 자동 활성 (편의)
        overrides.setdefault("add_group_features", True)
    if args.mode:
        overrides["mode"] = args.mode
    if args.train_end_quarter is not None:
        overrides["train_end_quarter"] = args.train_end_quarter

    result = train_residual(overrides if overrides else None)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


__all__ = ["GROUP_FEATURE_SETS", "WEIGHTS_DIR", "train_residual"]


if __name__ == "__main__":
    main()
