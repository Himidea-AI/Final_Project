"""seoul_adstrd_change_ix 기반 supervised eval.

ground truth:
- HL → LH 전이 = is_emerging = 1
- HH → HL 전이 = is_declining = 1
- 그 외 = 0

LSTM AE anomaly_score 의 AUC-ROC 측정 (vs is_emerging or is_declining).
"""

from __future__ import annotations

import logging
import os
import pickle
from pathlib import Path

import pandas as pd
import torch
from dotenv import load_dotenv
from sklearn.metrics import roc_auc_score
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / "backend" / ".env")

DB_URL = os.environ.get(
    "POSTGRES_URL",
    "postgresql://postgres:MapoSpotter1!%23@mapo-simulator.cx8eakyuk1jf.ap-northeast-2.rds.amazonaws.com:5432/mapo_simulator",
)


def load_change_ix(dong_prefix: str = "11440") -> pd.DataFrame:
    """seoul_adstrd_change_ix 로드 — (dong_code, quarter, change_ix)."""
    if DB_URL is None:
        raise RuntimeError("POSTGRES_URL 미설정")
    engine = create_engine(DB_URL, isolation_level="AUTOCOMMIT")
    sql = """
        SELECT dong_code, quarter, change_ix
        FROM seoul_adstrd_change_ix
        WHERE dong_code LIKE :prefix
        ORDER BY dong_code, quarter
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(sql), conn, params={"prefix": f"{dong_prefix}%"})
    df["dong_code"] = df["dong_code"].astype(str)
    df["quarter"] = df["quarter"].astype(int)
    return df


def compute_transition_labels(df: pd.DataFrame) -> pd.DataFrame:
    """change_ix 변화 전이를 binary 라벨로.

    Returns
    -------
    pd.DataFrame
        원본 df + is_emerging (HL→LH=1), is_declining (HH→HL=1), is_anomaly (둘 중 하나=1).
    """
    df = df.sort_values(["dong_code", "quarter"]).copy()
    df["prev_ix"] = df.groupby("dong_code")["change_ix"].shift(1)
    df["is_emerging"] = ((df["prev_ix"] == "HL") & (df["change_ix"] == "LH")).astype(int)
    df["is_declining"] = ((df["prev_ix"] == "HH") & (df["change_ix"] == "HL")).astype(int)
    df["is_anomaly"] = (df["is_emerging"] | df["is_declining"]).astype(int)
    return df


def compute_lstm_anomaly_scores() -> pd.DataFrame:
    """현재 LSTM AE 모델로 마포 (dong, industry, quarter) 별 anomaly score."""
    from models.emerging_district.data_prep import (
        build_windows,
        load_emerging_data,
    )
    from models.emerging_district.model import WEIGHTS_DIR, LSTMAutoencoder

    with open(WEIGHTS_DIR / "autoencoder_meta.pkl", "rb") as f:
        meta = pickle.load(f)
    df = load_emerging_data(dong_prefix="11440")
    X, meta_rows, _ = build_windows(df, window_size=meta["window_size"])

    model = LSTMAutoencoder(
        input_size=meta["input_size"],
        hidden_size=meta["hidden_size"],
        num_layers=meta["num_layers"],
    )
    model.load_weights(WEIGHTS_DIR / "autoencoder.pt")
    model.eval()

    with torch.no_grad():
        Xt = torch.from_numpy(X)
        recon = model(Xt)
        errs = ((recon - Xt) ** 2).mean(dim=(1, 2)).numpy()

    rows = []
    for i, m in enumerate(meta_rows):
        rows.append(
            {
                "dong_code": m["dong_code"],
                "industry_code": m["industry_code"],
                "quarter": m["last_quarter"],
                "anomaly_score": float(errs[i]),
            }
        )
    return pd.DataFrame(rows)


def evaluate_lstm_change_ix_auc() -> dict:
    """LSTM AE anomaly_score 의 change_ix transition AUC-ROC."""
    change_df = load_change_ix(dong_prefix="11440")
    labels = compute_transition_labels(change_df)
    scores = compute_lstm_anomaly_scores()

    # join: (dong_code, quarter) — industry 별로 anomaly_score 가 여러개라 동 평균
    score_avg = scores.groupby(["dong_code", "quarter"])["anomaly_score"].mean().reset_index()
    merged = labels.merge(score_avg, on=["dong_code", "quarter"], how="inner")
    if merged.empty:
        raise RuntimeError("change_ix 와 anomaly_score join 결과 빈 결과")

    n_emerging = int(merged["is_emerging"].sum())
    n_declining = int(merged["is_declining"].sum())
    n_anomaly = int(merged["is_anomaly"].sum())

    out: dict = {
        "n_total": len(merged),
        "n_emerging": n_emerging,
        "n_declining": n_declining,
        "n_anomaly_total": n_anomaly,
    }
    if n_emerging > 0:
        out["AUC_emerging"] = float(roc_auc_score(merged["is_emerging"], merged["anomaly_score"]))
    if n_declining > 0:
        out["AUC_declining"] = float(roc_auc_score(merged["is_declining"], merged["anomaly_score"]))
    if n_anomaly > 0:
        out["AUC_any"] = float(roc_auc_score(merged["is_anomaly"], merged["anomaly_score"]))
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    result = evaluate_lstm_change_ix_auc()
    print("\n=== LSTM AE vs change_ix AUC ===")
    for k, v in result.items():
        print(f"  {k}: {v}")

    # 게이트
    auc_any = result.get("AUC_any", 0.0)
    print("\n게이트:")
    if auc_any > 0.7:
        print(f"  AUC_any={auc_any:.3f} > 0.7 → LSTM AE 의미있음")
    elif auc_any > 0.5:
        print(f"  AUC_any={auc_any:.3f} 0.5~0.7 → 약함, 재학습 가치 small")
    else:
        print(f"  AUC_any={auc_any:.3f} < 0.5 → 무가치, 폐기 권장")


if __name__ == "__main__":
    main()
