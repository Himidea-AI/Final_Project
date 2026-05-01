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
import os
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

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/postgres",
)

# v1: 자기회귀 단일스텝 (window_size=4, output_size=1)
V1_CONFIG = {
    "window_size": 4,
    "n_channels": 128,
    "dilations": [1, 2],
    "output_size": 1,
}

# v2: DMS 4분기 동시출력 (window_size=8, output_size=4)
V2_CONFIG = {
    "window_size": 8,  # TCN v2 최소 학습 윈도우
    "n_channels": 128,
    "dilations": [1, 2, 4],
    "output_size": 4,
}

_WEIGHTS_DIR = Path(__file__).resolve().parent.parent / "models" / "tcn_forecast" / "weights"
V1_WEIGHTS_PATH = _WEIGHTS_DIR / "finetuned_mapo_tcn_34f.pt"
V1_SCALERS_PATH = _WEIGHTS_DIR / "finetune_tcn_scalers_34f.pkl"

EXCLUDE_COMBOS: set[tuple[str, str]] = set()  # 평가 제외 조합 (필요 시 추가)

# ---------------------------------------------------------------------------
# 외부 의존성 — 모듈 수준 심볼 (테스트 패치 대상). 실제 import는 런타임에 발생.
# ---------------------------------------------------------------------------

try:
    from models.lstm_forecast.data_prep import load_timeseries
    from models.tcn_forecast.model import TCNForecaster
    from models.tcn_forecast.train import load_scalers
except Exception:  # noqa: BLE001
    load_timeseries = None  # type: ignore[assignment]
    TCNForecaster = None  # type: ignore[assignment,misc]
    load_scalers = None  # type: ignore[assignment]


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


# ---------------------------------------------------------------------------
# 통합 평가 실행
# ---------------------------------------------------------------------------


def run_evaluation(
    v2_weights: Path | str,
    v2_scalers: Path | str,
    v1_weights: Path | str = V1_WEIGHTS_PATH,
    v1_scalers: Path | str = V1_SCALERS_PATH,
) -> Path:
    """v1 vs v2 비교 평가 실행. 리포트 파일 Path 반환."""
    v2_weights, v2_scalers = Path(v2_weights), Path(v2_scalers)
    v1_weights, v1_scalers = Path(v1_weights), Path(v1_scalers)

    ts = load_timeseries(db_url=DB_URL, dong_prefix="11440")
    train_ts, val_ts = split_train_val(ts)
    valid_combos = get_valid_combos(ts)
    logger.info("평가 대상 조합: %d개", len(valid_combos))

    from models.lstm_forecast.data_prep import ALL_FEATURES

    def _run_model(weights_path, scalers_path, config, is_dms):
        import torch

        feat_scaler, tgt_scaler = load_scalers(scalers_path)
        input_size = len(feat_scaler.scale_)
        model = TCNForecaster(
            input_size=input_size,
            n_channels=config["n_channels"],
            kernel_size=2,
            dilations=config["dilations"],
            dropout=0.2,
            output_size=config["output_size"],
        )
        model.load_weights(weights_path)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.to(device)

        feature_cols = [c for c in ALL_FEATURES if c in ts.columns]
        target_col = "monthly_sales"
        target_idx = feature_cols.index(target_col) if target_col in feature_cols else 0
        window_size = config["window_size"]

        preds, trues, q0s = [], [], []
        for dong, ind in valid_combos:
            train_g = train_ts[(train_ts["dong_code"] == dong) & (train_ts["industry_code"] == ind)].sort_values(
                "quarter"
            )
            val_g = val_ts[(val_ts["dong_code"] == dong) & (val_ts["industry_code"] == ind)].sort_values("quarter")
            seq = feat_scaler.transform(train_g[feature_cols].values[-window_size:].astype("float32"))
            if is_dms:
                pred = _dms_predict(model, seq, tgt_scaler, device)
            else:
                pred = _autoregressive_predict(model, seq, target_idx, 4, tgt_scaler, device)
            preds.append(pred)
            trues.append(list(np.expm1(val_g[target_col].values[:4].astype("float64"))))
            q0s.append(float(np.expm1(train_g[target_col].values[-1])))

        model.cpu()
        del model
        torch.cuda.empty_cache()
        return np.array(preds), np.array(trues), np.array(q0s)

    preds_v1, trues_v1, q0s_v1 = _run_model(v1_weights, v1_scalers, V1_CONFIG, is_dms=False)
    preds_v2, trues_v2, q0s_v2 = _run_model(v2_weights, v2_scalers, V2_CONFIG, is_dms=True)

    def _metrics(preds, trues, q0s):
        flat_p, flat_t = preds.flatten(), trues.flatten()
        return dict(
            mape=compute_mape(flat_p, flat_t),
            mae=compute_mae(flat_p, flat_t),
            rmse=compute_rmse(flat_p, flat_t),
            da=compute_directional_accuracy(q0s, preds, trues),
            bias=compute_bias(flat_p, flat_t),
            pq_mape=compute_per_quarter_mape(preds, trues),
        )

    warn_combos = []
    for i, (dong, ind) in enumerate(valid_combos):
        m = compute_mape(preds_v2[i], trues_v2[i])
        if not np.isnan(m) and m > 30:
            warn_combos.append((dong, ind, m))

    residual_std_path = Path(str(v2_scalers).replace("scalers", "residual_std"))
    residual_std = None
    if residual_std_path.exists():
        import pickle

        with open(residual_std_path, "rb") as f:
            residual_std = pickle.load(f)  # noqa: S301

    report_path = _generate_report(
        metrics_v1=_metrics(preds_v1, trues_v1, q0s_v1),
        metrics_v2=_metrics(preds_v2, trues_v2, q0s_v2),
        v1_weights_name=v1_weights.name,
        v2_weights_name=v2_weights.name,
        n_combos=len(valid_combos),
        reports_dir=REPORTS_DIR,
        residual_std=residual_std,
        warn_combos=warn_combos,
    )
    logger.info("평가 리포트 저장: %s", report_path)
    return report_path


# ---------------------------------------------------------------------------
# CLI 진입점
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="TCN v1 vs v2 비교 평가")
    parser.add_argument("--v2-weights", required=True)
    parser.add_argument("--v2-scalers", required=True)
    parser.add_argument("--v1-weights", default=str(V1_WEIGHTS_PATH))
    parser.add_argument("--v1-scalers", default=str(V1_SCALERS_PATH))
    args = parser.parse_args()
    report = run_evaluation(
        v2_weights=args.v2_weights,
        v2_scalers=args.v2_scalers,
        v1_weights=args.v1_weights,
        v1_scalers=args.v1_scalers,
    )
    print(f"리포트 저장 완료: {report}")


if __name__ == "__main__":
    main()
