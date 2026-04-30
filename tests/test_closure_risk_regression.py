"""train.py + evaluate.py 통합 + 기존 predict.py 인터페이스 보존 검증."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from models.closure_risk.data_prep import _time_based_split
from models.closure_risk.evaluate import evaluate_model, save_metrics_and_plot


def test_time_based_split_used_in_train_config():
    """DEFAULT_CONFIG 가 time-based split 을 default 로 사용."""
    from models.closure_risk.train import DEFAULT_CONFIG

    assert DEFAULT_CONFIG["split_strategy"] == "time"
    assert 0.5 <= DEFAULT_CONFIG["train_ratio"] <= 0.9
    assert 0.05 <= DEFAULT_CONFIG["val_ratio"] <= 0.3
    test_ratio = 1 - DEFAULT_CONFIG["train_ratio"] - DEFAULT_CONFIG["val_ratio"]
    assert test_ratio > 0


def test_predict_py_interface_unchanged(tmp_path, monkeypatch):
    """predict.py 의 _classify, RISK_LEVELS 변경 X (회귀 안전).

    D layer fix (2026-05-01) 후 _classify 가 metrics.json 의 fit threshold 를
    동적 load — 회귀 검증을 위해 monkeypatch 로 WEIGHTS_DIR=tmp 격리하여
    default fallback (0.65/0.40) 모드에서 검증.
    """
    from models.closure_risk import predict as predict_mod
    from models.closure_risk.predict import RISK_LEVELS, _classify

    assert len(RISK_LEVELS) == 3
    for thr, lvl in RISK_LEVELS:
        assert 0.0 <= thr <= 1.0
        assert lvl in ("danger", "caution", "safe")

    # default fallback 모드 격리 — metrics.json 미존재 → 0.65/0.40
    predict_mod._load_risk_levels.cache_clear()
    monkeypatch.setattr(predict_mod, "WEIGHTS_DIR", tmp_path)

    assert _classify(0.7) == "danger"
    assert _classify(0.5) == "caution"
    assert _classify(0.1) == "safe"


def test_predict_does_not_use_label_pipeline():
    """predict.py 가 _make_labels / build_closure_risk_dataset 를 호출하지 않음.

    predict.py 는 학습된 weight 파일만 load → label 생성 layer 변경에 무영향.
    C layer (label) fix 회귀 격리 검증.
    """
    import inspect

    from models.closure_risk import predict as predict_mod

    src = inspect.getsource(predict_mod)
    assert "_make_labels" not in src, "predict.py 가 _make_labels 호출하면 안 됨"
    assert "build_closure_risk_dataset" not in src, "predict.py 가 dataset builder 호출하면 안 됨"


def test_full_pipeline_with_synthetic_data(tmp_path):
    """build_dataset 거치지 않고 _time_based_split + evaluate 통합 동작 확인."""
    rng = np.random.default_rng(7)
    n_per_q = 30
    quarters = [f"2020Q{(i % 4) + 1}" if i < 4 else f"202{1 + (i - 4) // 4}Q{((i - 4) % 4) + 1}" for i in range(20)]
    rows = []
    for q in quarters:
        for _ in range(n_per_q):
            rows.append(
                {
                    "quarter": q,
                    "dong_code": f"d{rng.integers(0, 5)}",
                    "industry_code": "x",
                    "label": int(rng.choice([0, 1], p=[0.8, 0.2])),
                    "feature1": rng.normal(),
                }
            )
    df = pd.DataFrame(rows)

    train_df, val_df, test_df = _time_based_split(df)
    assert len(train_df) + len(val_df) + len(test_df) == len(df)

    val_proba = np.clip(val_df["label"].values * 0.5 + rng.normal(0.3, 0.15, size=len(val_df)), 0, 1)
    test_proba = np.clip(test_df["label"].values * 0.5 + rng.normal(0.3, 0.15, size=len(test_df)), 0, 1)

    val_metrics = evaluate_model(val_df["label"].values, val_proba)
    test_metrics = evaluate_model(test_df["label"].values, test_proba)

    summary = {
        "split_strategy": "time",
        "ensemble": {"val": val_metrics, "test": test_metrics},
    }

    json_path = tmp_path / "metrics.json"
    save_metrics_and_plot(summary, json_path, plot_path=None)
    assert json_path.exists()

    with open(json_path, encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["split_strategy"] == "time"
    assert "ensemble" in loaded
    assert loaded["ensemble"]["val"]["auc"] > 0.5
