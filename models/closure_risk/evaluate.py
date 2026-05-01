"""폐업 위험도 모델 평가 — 5 metric + Calibration plot.

evaluate_model: AUC/PR-AUC/P@K/R@K/Brier + 10 bin reliability diagram 데이터.
save_metrics_and_plot: metrics.json + calibration_curve.png 저장.

학술 근거:
- Niculescu-Mizil & Caruana (2005) — calibration 표준
- Bergmeir & Benítez (2012) — 시계열 검증

담당: B2 (수지니) 영역, A1 (찬영) cross-team contribution.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
)

logger = logging.getLogger(__name__)


def _precision_recall_at_k(
    y_true: np.ndarray,
    proba: np.ndarray,
    k_pct: int = 10,
) -> tuple[float, float]:
    """위험도 top K% 의 precision + recall.

    Args:
        y_true: 실제 label (0/1).
        proba: 예측 확률.
        k_pct: 상위 K% (1~100). >100 시 자동 clamp (n 으로 cap).

    Returns:
        (precision_at_k, recall_at_k). 둘 다 [0,1].
    """
    n = len(y_true)
    if n == 0:
        return 0.0, 0.0
    k = max(1, int(n * k_pct / 100))
    top_idx = np.argsort(-proba)[:k]
    y_top = y_true[top_idx]

    actual_k = len(top_idx)  # k > n 이면 n, 아니면 k
    precision = float(y_top.sum() / actual_k) if actual_k > 0 else 0.0
    n_pos = int(y_true.sum())
    recall = float(y_top.sum() / n_pos) if n_pos > 0 else 0.0
    return precision, recall


def _calibration_curve(
    y_true: np.ndarray,
    proba: np.ndarray,
    n_bins: int = 10,
) -> dict:
    """Reliability diagram 데이터 (10 bin uniform).

    Returns:
        {"bin_centers": [...], "actual_freq": [...], "n_per_bin": [...]}.
    """
    bins = np.linspace(0, 1, n_bins + 1)
    bin_centers = ((bins[:-1] + bins[1:]) / 2).tolist()
    actual_freq = []
    n_per_bin = []
    for i in range(n_bins):
        mask = (proba >= bins[i]) & (proba < bins[i + 1])
        if i == n_bins - 1:
            mask = (proba >= bins[i]) & (proba <= bins[i + 1])
        n = int(mask.sum())
        n_per_bin.append(n)
        if n > 0:
            actual_freq.append(float(y_true[mask].mean()))
        else:
            actual_freq.append(None)  # JSON null 로 직렬화 (RFC 8259 compliant)
    return {
        "bin_centers": bin_centers,
        "actual_freq": actual_freq,
        "n_per_bin": n_per_bin,
    }


def evaluate_model(
    y_true: np.ndarray,
    proba: np.ndarray,
    k_pct: int = 10,
) -> dict:
    """5 metric + calibration 측정.

    Args:
        y_true: 실제 binary label (0/1) 배열.
        proba: 예측 확률 배열 (같은 길이).
        k_pct: Precision/Recall@K 의 K% (default 10).

    Returns:
        {
            "auc": float, "pr_auc": float,
            "p_at_k": float, "r_at_k": float, "k_pct": int,
            "brier": float,
            "calibration": {"bin_centers": [...], "actual_freq": [...], "n_per_bin": [...]},
            "n_samples": int, "pos_ratio": float,
        }
    """
    y_true = np.asarray(y_true).astype(int)
    proba = np.asarray(proba).astype(float)
    n = len(y_true)
    if n == 0 or len(np.unique(y_true)) < 2:
        return {
            "auc": 0.5,
            "pr_auc": 0.0,
            "p_at_k": 0.0,
            "r_at_k": 0.0,
            "k_pct": k_pct,
            "brier": 0.0,
            "calibration": {"bin_centers": [], "actual_freq": [], "n_per_bin": []},
            "n_samples": int(n),
            "pos_ratio": float(y_true.mean()) if n > 0 else 0.0,
        }

    auc = float(roc_auc_score(y_true, proba))
    pr_auc = float(average_precision_score(y_true, proba))
    p_at_k, r_at_k = _precision_recall_at_k(y_true, proba, k_pct)
    brier = float(brier_score_loss(y_true, proba))
    cal = _calibration_curve(y_true, proba, n_bins=10)

    return {
        "auc": auc,
        "pr_auc": pr_auc,
        "p_at_k": p_at_k,
        "r_at_k": r_at_k,
        "k_pct": k_pct,
        "brier": brier,
        "calibration": cal,
        "n_samples": int(n),
        "pos_ratio": float(y_true.mean()),
    }


def _to_native(obj):
    """numpy 타입 → native python recursive (JSON serializable 보장)."""
    if isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_native(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def save_metrics_and_plot(
    metrics: dict,
    metrics_path: str | Path,
    plot_path: str | Path | None = None,
) -> None:
    """metrics.json + calibration_curve.png 저장.

    Args:
        metrics: 두 가지 형태 지원
            - single model: evaluate_model() 직접 결과 (auc/calibration/... 키)
            - multi-model: {"ensemble": {"val": {...}, "test": {...}}, "lgbm": {...}, ...}
        metrics_path: JSON 저장 경로.
        plot_path: PNG 저장 경로 (None 이면 plot skip).
    """
    metrics_path = Path(metrics_path)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    # numpy 타입 → native python 재귀 변환 (TypeError: int64 is not JSON serializable 회피)
    metrics_native = _to_native(metrics)
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics_native, f, ensure_ascii=False, indent=2)
    logger.info("metrics 저장: %s", metrics_path)

    if plot_path is None:
        return

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib 미설치 — calibration plot skip")
        return

    plot_path = Path(plot_path)
    plot_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot([0, 1], [0, 1], "k--", label="perfect calibration")

    plotted = False
    if "auc" in metrics and "calibration" in metrics:
        # single model dict — calibration 직접 사용
        cal = metrics.get("calibration", {})
        bc = cal.get("bin_centers", [])
        af = cal.get("actual_freq", [])
        if bc and af:
            af_clean = [v if v is not None else 0.0 for v in af]
            ax.plot(bc, af_clean, marker="o", label="single model")
            plotted = True
    else:
        # multi-model dict (ensemble/lgbm/tcn × val/test)
        for model_name in ["ensemble", "lgbm", "tcn"]:
            if model_name in metrics and "val" in metrics[model_name]:
                cal = metrics[model_name]["val"].get("calibration", {})
                bc = cal.get("bin_centers", [])
                af = cal.get("actual_freq", [])
                if bc and af:
                    af_clean = [v if v is not None else 0.0 for v in af]
                    ax.plot(bc, af_clean, marker="o", label=f"{model_name} (val)")
                    plotted = True

    ax.set_xlabel("Predicted probability")
    ax.set_ylabel("Actual frequency")
    ax.set_title("Calibration curve (val set, 10 bins)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(plot_path, dpi=120)
    plt.close(fig)
    logger.info("calibration plot 저장: %s (plotted=%s)", plot_path, plotted)
