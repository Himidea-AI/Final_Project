"""
폐업위험도 모델 학습 — LightGBM + TCNClassifier 앙상블

학습 순서:
    1. LightGBM: lag 피처 기반 이진 분류 학습
    2. TCNClassifier: 매출 예측 pretrain 가중치 전이 후 fine-tune
    3. 검증셋 AUC 기반 앙상블 가중치 결정 → weights/ 저장

Usage:
    python -m models.closure_risk.train

담당: B2 — 수지니
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score
from torch.utils.data import DataLoader, TensorDataset

from models.closure_risk.data_prep import _time_based_split, build_closure_risk_dataset
from models.closure_risk.evaluate import evaluate_model, save_metrics_and_plot  # noqa: F401  (Task 5에서 사용)
from models.closure_risk.model import WEIGHTS_DIR, TCNClassifier
from models.lstm_forecast.data_prep import ALL_FEATURES, DB_URL
from models.tcn_forecast.model import WEIGHTS_DIR as TCN_WEIGHTS_DIR

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

DEFAULT_CONFIG: dict = {
    "db_url": DB_URL,
    "dong_prefix": "11440",
    "window_size": 4,
    # split 전략 — "time" (default, 학술 표준) | "random" (legacy, 분기 부족 시 fallback)
    "split_strategy": "time",
    "train_ratio": 0.70,
    "val_ratio": 0.15,
    # test_ratio = 1 - train_ratio - val_ratio = 0.15
    "random_state": 42,
    # TCN fine-tune
    "tcn_epochs": 50,
    "tcn_lr": 5e-4,
    "tcn_batch_size": 32,
    "tcn_patience": 7,
    "input_size": 34,
    "n_channels": 128,
    "kernel_size": 2,
    "dilations": [1, 2],
    "dropout": 0.2,
    # LightGBM
    "lgbm_num_leaves": 31,
    "lgbm_n_estimators": 200,
    "lgbm_learning_rate": 0.05,
    # 저장 경로
    "tcn_weights_path": str(WEIGHTS_DIR / "closure_risk_tcn.pt"),
    "tcn_scaler_path": str(WEIGHTS_DIR / "closure_risk_tcn_scaler.pkl"),
    "lgbm_model_path": str(WEIGHTS_DIR / "closure_risk_lgbm.pkl"),
    "ensemble_weights_path": str(WEIGHTS_DIR / "ensemble_weights.pkl"),
    "metrics_path": str(WEIGHTS_DIR / "metrics.json"),
    "calibration_plot_path": str(WEIGHTS_DIR / "calibration_curve.png"),
}


# ---------------------------------------------------------------------------
# LightGBM 학습
# ---------------------------------------------------------------------------


def train_lgbm(X_train: np.ndarray, y_train: np.ndarray, config: dict) -> object:
    """LightGBM 이진 분류 학습."""
    import lightgbm as lgb

    pos_count = y_train.sum()
    neg_count = len(y_train) - pos_count
    scale_pos_weight = neg_count / max(pos_count, 1)

    model = lgb.LGBMClassifier(
        num_leaves=config["lgbm_num_leaves"],
        n_estimators=config["lgbm_n_estimators"],
        learning_rate=config["lgbm_learning_rate"],
        scale_pos_weight=scale_pos_weight,  # 클래스 불균형 처리
        random_state=config["random_state"],
        verbose=-1,
    )
    model.fit(X_train, y_train)
    logger.info("LightGBM 학습 완료 (scale_pos_weight=%.2f)", scale_pos_weight)
    return model


# ---------------------------------------------------------------------------
# TCN 시퀀스 생성
# ---------------------------------------------------------------------------


def _build_tcn_sequences(
    df_full: pd.DataFrame,
    y: pd.Series,
    window_size: int,
    feature_cols: list[str],
    val_ratio: float,
) -> tuple:
    """(dong_code, industry_code) 그룹별 sliding window 시퀀스 생성."""
    from sklearn.preprocessing import MinMaxScaler

    feat_scaler = MinMaxScaler()
    # 누락 피처는 0으로 패딩 — pretrained 모델 input_size(len(ALL_FEATURES))와 일치 보장
    df_full = df_full.copy()
    for col in feature_cols:
        if col not in df_full.columns:
            df_full[col] = 0.0

    all_feats = df_full[feature_cols].values.astype(np.float32)
    feat_scaler.fit(all_feats)

    X_list, y_list = [], []
    gk = ["dong_code", "industry_code"]

    for _, group in df_full.groupby(gk):
        if len(group) <= window_size:
            continue
        feat_vals = feat_scaler.transform(group[feature_cols].values.astype(np.float32))
        labels = y.loc[group.index].values

        for i in range(len(group) - window_size):
            X_list.append(feat_vals[i : i + window_size])
            y_list.append(labels[i + window_size])

    if not X_list:
        raise ValueError("TCN 시퀀스 생성 실패 — 데이터 부족")

    X = np.array(X_list, dtype=np.float32)
    y_arr = np.array(y_list, dtype=np.float32)

    n_val = max(1, int(len(X) * val_ratio))
    return X[:-n_val], X[-n_val:], y_arr[:-n_val], y_arr[-n_val:], feat_scaler


# ---------------------------------------------------------------------------
# TCN 학습
# ---------------------------------------------------------------------------


def train_tcn(
    df_full,
    y: pd.Series,
    config: dict,
    pretrained_path: Path,
) -> tuple[TCNClassifier, float, object]:
    """TCNClassifier fine-tune. 검증 AUC 및 feat_scaler 반환."""

    # pretrained 모델과 input_size 일치를 위해 ALL_FEATURES 전체 사용
    # 누락 피처는 _build_tcn_sequences 내부에서 0으로 패딩
    feature_cols = list(ALL_FEATURES)
    input_size = len(feature_cols)

    X_tr, X_val, y_tr, y_val, feat_scaler = _build_tcn_sequences(
        df_full, y, config["window_size"], feature_cols, config["val_ratio"]
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = TCNClassifier(
        input_size=input_size,
        n_channels=config["n_channels"],
        kernel_size=config["kernel_size"],
        dilations=config["dilations"],
        dropout=config["dropout"],
    )
    model.load_pretrained_tcn(pretrained_path)
    model.to(device)

    criterion = nn.BCEWithLogitsLoss()

    optimizer = torch.optim.Adam(model.parameters(), lr=config["tcn_lr"])

    ds_tr = TensorDataset(torch.from_numpy(X_tr), torch.from_numpy(y_tr))
    loader = DataLoader(ds_tr, batch_size=config["tcn_batch_size"], shuffle=True)

    best_auc, patience_cnt = 0.0, 0
    best_state = None

    for epoch in range(1, config["tcn_epochs"] + 1):
        model.train()
        for xb, yb in loader:
            xb, yb = xb.to(device), yb.to(device).unsqueeze(1)
            optimizer.zero_grad()
            pred = model(xb)
            loss = criterion(pred, yb)
            loss.backward()
            optimizer.step()

        # 검증
        model.eval()
        with torch.no_grad():
            xv = torch.from_numpy(X_val).to(device)
            pv = model(xv).cpu().numpy().flatten()
        try:
            auc = roc_auc_score(y_val, pv)
        except ValueError:
            auc = 0.5

        if auc > best_auc:
            best_auc = auc
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            patience_cnt = 0
        else:
            patience_cnt += 1

        if epoch % 5 == 0:
            logger.info("[TCN] Epoch %2d/%d  val_AUC=%.4f  best=%.4f", epoch, config["tcn_epochs"], auc, best_auc)

        if patience_cnt >= config["tcn_patience"]:
            logger.info("[TCN] 조기종료 (epoch=%d, best_AUC=%.4f)", epoch, best_auc)
            break

    if best_state:
        model.load_state_dict(best_state)

    logger.info("TCNClassifier 학습 완료 (best_val_AUC=%.4f)", best_auc)
    return model, best_auc, feat_scaler


# ---------------------------------------------------------------------------
# 메인 학습 파이프라인
# ---------------------------------------------------------------------------


def train(config: dict | None = None) -> None:

    cfg = {**DEFAULT_CONFIG, **(config or {})}
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 데이터 준비
    df_full, X_lgbm, y = build_closure_risk_dataset(db_url=cfg["db_url"], dong_prefix=cfg["dong_prefix"])
    logger.info("데이터셋: %d 샘플, 고위험 비율=%.1f%%", len(y), y.mean() * 100)

    # df_full 에 X_lgbm + y 컬럼이 함께 있어야 split 가능 → align
    df_full_aligned = df_full.loc[X_lgbm.index].copy()
    # index 기준 align — build_closure_risk_dataset 의 X_lgbm/y/df_full 행 순서 일치 보장 X
    df_full_aligned["__y__"] = y.loc[df_full_aligned.index]
    X_lgbm_aligned = X_lgbm.loc[df_full_aligned.index]
    df_full_aligned[X_lgbm_aligned.columns] = X_lgbm_aligned

    # split
    if cfg["split_strategy"] == "time":
        train_df, val_df, test_df = _time_based_split(df_full_aligned, cfg["train_ratio"], cfg["val_ratio"])
        logger.info(
            "time-based split: train=%d (<=%s), val=%d (<=%s), test=%d (>%s)",
            len(train_df),
            train_df["quarter"].max(),
            len(val_df),
            val_df["quarter"].max(),
            len(test_df),
            val_df["quarter"].max(),
        )
    elif cfg["split_strategy"] == "random":
        logger.warning("random split — temporal leakage 위험 (deprecated). split_strategy='time' 권장")
        from sklearn.model_selection import train_test_split

        test_ratio = 1 - cfg["train_ratio"] - cfg["val_ratio"]
        train_df, temp_df = train_test_split(
            df_full_aligned,
            test_size=(cfg["val_ratio"] + test_ratio),
            random_state=cfg["random_state"],
        )
        val_df, test_df = train_test_split(
            temp_df,
            test_size=test_ratio / (cfg["val_ratio"] + test_ratio),
            random_state=cfg["random_state"] + 1,
        )
    else:
        raise ValueError(f"unknown split_strategy: {cfg['split_strategy']}")

    # 빈 split 방어 — train_test_split 의 부동소수점 오차 또는 _time_based_split 의 비율 misconfiguration 시
    if len(train_df) == 0 or len(val_df) == 0 or len(test_df) == 0:
        raise ValueError(
            f"split 결과 비어있는 set 존재 — "
            f"train={len(train_df)}, val={len(val_df)}, test={len(test_df)}. "
            f"train_ratio({cfg['train_ratio']}) + val_ratio({cfg['val_ratio']}) 조정 필요."
        )

    # LightGBM 입력 추출 (인덱스 기준)
    X_lgbm_tr = train_df[X_lgbm.columns].values
    X_lgbm_val = val_df[X_lgbm.columns].values
    X_lgbm_test = test_df[X_lgbm.columns].values
    y_tr_arr = train_df["__y__"].values
    y_val_arr = val_df["__y__"].values
    y_test_arr = test_df["__y__"].values  # noqa: F841  (Task 5 evaluate 입력)

    # 2. LightGBM 학습
    lgbm_model = train_lgbm(X_lgbm_tr, y_tr_arr, cfg)
    lgbm_val_proba = lgbm_model.predict_proba(X_lgbm_val)[:, 1]
    lgbm_test_proba = lgbm_model.predict_proba(X_lgbm_test)[:, 1]  # noqa: F841  (Task 5 evaluate 입력)
    lgbm_val_auc = roc_auc_score(y_val_arr, lgbm_val_proba) if len(np.unique(y_val_arr)) > 1 else 0.5
    logger.info("LightGBM val_AUC=%.4f", lgbm_val_auc)

    # 3. TCN 학습 (전이학습)
    pretrained_path = TCN_WEIGHTS_DIR / "finetuned_mapo_tcn_34f.pt"
    tcn_model, tcn_auc, tcn_scaler = train_tcn(df_full, y, cfg, pretrained_path)

    # 4. 앙상블 가중치 결정 (AUC 비례)
    total = lgbm_val_auc + tcn_auc
    w_lgbm = lgbm_val_auc / total if total > 0 else 0.5
    w_tcn = tcn_auc / total if total > 0 else 0.5
    logger.info("앙상블 가중치 — LightGBM=%.3f, TCN=%.3f", w_lgbm, w_tcn)

    # train_tcn은 ALL_FEATURES 전체(34개)로 학습 — predict.py와 일치 보장
    actual_input_size = len(ALL_FEATURES)

    # 5. 저장
    with open(cfg["lgbm_model_path"], "wb") as f:
        pickle.dump(lgbm_model, f)
    logger.info("LightGBM 저장: %s", cfg["lgbm_model_path"])

    tcn_model.save_weights(cfg["tcn_weights_path"])

    with open(cfg["tcn_scaler_path"], "wb") as f:
        pickle.dump(tcn_scaler, f)
    logger.info("TCN 스케일러 저장: %s", cfg["tcn_scaler_path"])

    ensemble_weights = {
        "w_lgbm": w_lgbm,
        "w_tcn": w_tcn,
        "lgbm_auc": lgbm_val_auc,
        "tcn_auc": tcn_auc,
        "input_size": actual_input_size,
    }
    with open(cfg["ensemble_weights_path"], "wb") as f:
        pickle.dump(ensemble_weights, f)
    logger.info("앙상블 가중치 저장: %s", cfg["ensemble_weights_path"])
    logger.info("학습 완료 — 예상 앙상블 AUC: %.4f", max(lgbm_val_auc, tcn_auc))


if __name__ == "__main__":
    import pandas as pd  # noqa: F401 (train_tcn 내부에서 사용)

    train()
