"""
TCN v1(자기회귀) vs v2(DMS) 비교 평가 스크립트

Usage:
    python scripts/evaluate_model.py \
        --v2-weights models/tcn_forecast/weights/finetuned_mapo_tcn_v2.pt \
        --v2-scalers models/tcn_forecast/weights/finetune_tcn_scalers_v2.pkl

담당: B2 — 수지니
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"

VAL_QUARTER = 20241  # 검증 시작 분기 (2024Q1 이상 → val)

V2_CONFIG = {
    "window_size": 8,  # TCN v2 최소 학습 윈도우
}

EXCLUDE_COMBOS: set[tuple[str, str]] = set()  # 평가 제외 조합 (필요 시 추가)


# ---------------------------------------------------------------------------
# 지표 계산 함수
# ---------------------------------------------------------------------------


def compute_mape(pred: np.ndarray, true: np.ndarray) -> float:
    """MAPE 계산. true < 1000원(near-zero) 포인트 제외."""
    mask = true >= 1000
    if mask.sum() == 0:
        return float("nan")
    return float(np.mean(np.abs(pred[mask] - true[mask]) / true[mask]) * 100)


def compute_mae(pred: np.ndarray, true: np.ndarray) -> float:
    return float(np.mean(np.abs(pred - true)))


def compute_rmse(pred: np.ndarray, true: np.ndarray) -> float:
    return float(np.sqrt(np.mean((pred - true) ** 2)))


def compute_bias(pred: np.ndarray, true: np.ndarray) -> float:
    return float(np.mean(pred - true))


def compute_per_quarter_mape(pred: np.ndarray, true: np.ndarray) -> list[float]:
    """분기별 MAPE. pred/true shape: (n_combos, 4). true < 1000원 제외."""
    result = []
    for q in range(4):
        mask = true[:, q] >= 1000
        if mask.sum() == 0:
            result.append(float("nan"))
        else:
            result.append(float(np.mean(np.abs(pred[mask, q] - true[mask, q]) / true[mask, q]) * 100))
    return result


def compute_directional_accuracy(q0: np.ndarray, pred: np.ndarray, true: np.ndarray) -> float:
    """방향 정확도. q0: (n_combos,), pred/true: (n_combos, 4)."""
    pred_seq = np.concatenate([q0[:, None], pred], axis=1)
    true_seq = np.concatenate([q0[:, None], true], axis=1)
    return float(np.mean(np.sign(np.diff(pred_seq, axis=1)) == np.sign(np.diff(true_seq, axis=1))) * 100)


# ---------------------------------------------------------------------------
# val 데이터 분리 / 유효 조합 필터링
# ---------------------------------------------------------------------------


def split_train_val(ts: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """quarter 기준으로 train / val 분리. VAL_QUARTER 이상 → val."""
    return ts[ts["quarter"] < VAL_QUARTER].copy(), ts[ts["quarter"] >= VAL_QUARTER].copy()


def get_valid_combos(ts: pd.DataFrame) -> list[tuple[str, str]]:
    """평가 가능한 (dong_code, industry_code) 조합 목록 반환."""
    train_ts, val_ts = split_train_val(ts)
    v2_window = V2_CONFIG["window_size"]  # 8
    valid = []
    for (dong, ind), train_group in train_ts.groupby(["dong_code", "industry_code"]):
        if (dong, ind) in EXCLUDE_COMBOS:
            continue
        if len(train_group) < v2_window:
            continue
        val_group = val_ts[(val_ts["dong_code"] == dong) & (val_ts["industry_code"] == ind)]
        if len(val_group) < 4:
            continue
        valid.append((dong, ind))
    return valid


# ---------------------------------------------------------------------------
# v1 자기회귀 추론 헬퍼
# ---------------------------------------------------------------------------


def _autoregressive_predict(
    model,
    window_seq: np.ndarray,  # (window_size, input_size), feat_scaler 변환 완료
    target_idx: int,
    n_steps: int,
    tgt_scaler,
    device,
) -> list[float]:
    """v1 자기회귀 추론. n_steps회 반복, expm1 역변환 적용."""
    import torch

    model.eval()
    with torch.no_grad():
        current_seq = torch.from_numpy(window_seq).unsqueeze(0).to(device)
        predictions: list[float] = []
        for _ in range(n_steps):
            pred_val = model(current_seq).cpu().numpy().flatten()[0]
            pred_log = tgt_scaler.inverse_transform([[pred_val]])[0][0]
            predictions.append(float(np.expm1(pred_log)))
            new_step = current_seq[0, -1, :].clone()
            new_step[target_idx] = float(pred_val)
            current_seq = torch.cat([current_seq[:, 1:, :], new_step.unsqueeze(0).unsqueeze(0)], dim=1)
    return predictions


# ---------------------------------------------------------------------------
# v2 DMS 추론 헬퍼
# ---------------------------------------------------------------------------


def _dms_predict(
    model,
    window_seq: np.ndarray,  # (window_size, input_size), feat_scaler 변환 완료
    tgt_scaler,
    device,
) -> list[float]:
    """v2 DMS 추론. forward 1회 → 4분기 동시 출력, expm1 역변환 적용."""
    import torch

    model.eval()
    with torch.no_grad():
        pred_scaled = model(torch.from_numpy(window_seq).unsqueeze(0).to(device)).cpu().numpy().flatten()
    return [float(np.expm1(tgt_scaler.inverse_transform([[v]])[0][0])) for v in pred_scaled]


# ---------------------------------------------------------------------------
# 마크다운 리포트 생성
# ---------------------------------------------------------------------------


def _generate_report(
    *,
    metrics_v1: dict,
    metrics_v2: dict,
    v1_weights_name: str,
    v2_weights_name: str,
    n_combos: int,
    reports_dir: Path,
    residual_std: list[float] | None,
    warn_combos: list[tuple[str, str, float]],
) -> Path:
    """마크다운 리포트 생성 후 파일 경로 반환."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

    def _krw(v: float) -> str:
        return f"{v:,.0f}원"

    def _improvement(v1: float, v2: float, higher_is_better: bool = False) -> str:
        diff = v2 - v1
        if higher_is_better:
            return f"▲ {diff:+.1f}%p" if diff > 0 else f"▼ {diff:.1f}%p"
        return f"▼ {v1 - v2:.1f}%p" if diff < 0 else f"▲ {diff:+.1f}%p"

    pq1, pq2 = metrics_v1["pq_mape"], metrics_v2["pq_mape"]
    pq_labels = ["Q1 (+1분기)", "Q2 (+2분기)", "Q3 (+3분기)", "Q4 (+4분기)"]

    lines = [
        "# TCN 매출예측 모델 평가 리포트\n",
        f"생성 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"v1 가중치: {v1_weights_name}  ",
        f"v2 가중치: {v2_weights_name}  ",
        "val 기간: 2024Q1~2024Q4 (quarter >= 20241)  ",
        f"평가 조합 수: {n_combos}개\n",
        "---\n",
        "## 1. 전체 지표 비교\n",
        "| 지표 | v1 (자기회귀) | v2 (DMS) | 개선 |",
        "|------|--------------|----------|------|",
        f"| MAPE | {metrics_v1['mape']:.1f}% | {metrics_v2['mape']:.1f}% | {_improvement(metrics_v1['mape'], metrics_v2['mape'])} |",
        f"| MAE | {_krw(metrics_v1['mae'])} | {_krw(metrics_v2['mae'])} | {_improvement(metrics_v1['mae'], metrics_v2['mae'])} |",
        f"| RMSE | {_krw(metrics_v1['rmse'])} | {_krw(metrics_v2['rmse'])} | {_improvement(metrics_v1['rmse'], metrics_v2['rmse'])} |",
        f"| Directional Accuracy | {metrics_v1['da']:.1f}% | {metrics_v2['da']:.1f}% | {_improvement(metrics_v1['da'], metrics_v2['da'], higher_is_better=True)} |",
        f"| Bias | {_krw(metrics_v1['bias'])} | {_krw(metrics_v2['bias'])} | - |",
        "\n> Bias: 양수=과대예측, 음수=과소예측.\n",
        "---\n",
        "## 2. 분기별 MAPE (Per-Quarter MAPE)\n",
        "| 분기 | v1 | v2 | 해석 |",
        "|------|----|----|------|",
    ]
    for i, label in enumerate(pq_labels):
        interp = "v2 우세" if pq2[i] < pq1[i] else "v1 우세"
        lines.append(f"| {label} | {pq1[i]:.1f}% | {pq2[i]:.1f}% | {interp} |")

    v1_drift = pq1[3] - pq1[0]
    v2_drift = pq2[3] - pq2[0]
    lines += [
        f"\n→ v1은 Q4로 갈수록 오차 확대 (Q1 대비 +{v1_drift:.1f}%p).",
        f"  v2는 DMS 구조로 오차 누적 억제 (Q1 대비 +{v2_drift:.1f}%p).\n",
        "---\n",
    ]

    if residual_std is not None:
        lines += [
            "## 3. v2 신뢰구간 폭 (residual_std 기반)\n",
            "| 분기 | residual_std | 95% CI 폭 (±) |",
            "|------|-------------|--------------|",
        ]
        for i, std in enumerate(residual_std):
            lines.append(f"| Q{i + 1} | {_krw(std)} | {_krw(std * 1.96)} |")
        lines.append("\n---\n")

    if warn_combos:
        lines += [
            "## 4. 주의 조합 (v2 MAPE > 30%)\n",
            "| 동코드 | 업종코드 | v2 MAPE |",
            "|---|---|---|",
        ]
        for dong, ind, mape_val in warn_combos:
            lines.append(f"| {dong} | {ind} | {mape_val:.1f}% |")
        lines.append("\n---\n")

    v2_wins = sum([metrics_v2["mape"] < metrics_v1["mape"], metrics_v2["da"] > metrics_v1["da"]])
    if v2_wins == 2:
        conclusion = "**채택 권장: v2 (DMS)**"
    elif v2_wins == 0:
        conclusion = "**채택 권장: v1 (자기회귀)**"
    else:
        conclusion = "**판단 필요: MAPE와 Directional Accuracy 결과가 엇갈립니다.**"

    lines += [
        "## 5. 결론\n",
        conclusion,
        f"- MAPE: {metrics_v1['mape']:.1f}% → {metrics_v2['mape']:.1f}%",
        f"- Directional Accuracy: {metrics_v1['da']:.1f}% → {metrics_v2['da']:.1f}%",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")
    return path
