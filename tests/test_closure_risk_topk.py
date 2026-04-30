"""D layer (threshold + top-K) unit test."""

from __future__ import annotations

import json
from pathlib import Path  # noqa: F401  (T2/T3 사용 예정 — 미리 import 보존)

import pytest


@pytest.fixture
def clear_risk_levels_cache():
    """`_load_risk_levels` lru_cache clear — test 격리."""
    from models.closure_risk import predict as predict_mod

    predict_mod._load_risk_levels.cache_clear()
    yield
    predict_mod._load_risk_levels.cache_clear()


def test_load_risk_levels_from_metrics(tmp_path, monkeypatch, clear_risk_levels_cache):
    """metrics.json 의 fit threshold 정확히 load."""
    from models.closure_risk import predict as predict_mod

    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(
        json.dumps(
            {"thresholds": {"danger": 0.4523, "caution": 0.3145, "danger_quantile": 0.90, "caution_quantile": 0.70}}
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(predict_mod, "WEIGHTS_DIR", tmp_path)

    levels = predict_mod._load_risk_levels()
    assert levels[0] == (0.4523, "danger")
    assert levels[1] == (0.3145, "caution")
    assert levels[2] == (0.0, "safe")


def test_load_risk_levels_fallback_on_missing(tmp_path, monkeypatch, clear_risk_levels_cache):
    """metrics.json 미존재 → default fallback."""
    from models.closure_risk import predict as predict_mod

    monkeypatch.setattr(predict_mod, "WEIGHTS_DIR", tmp_path)

    levels = predict_mod._load_risk_levels()
    assert levels == ((0.65, "danger"), (0.40, "caution"), (0.0, "safe"))


def test_load_risk_levels_fallback_on_corrupt(tmp_path, monkeypatch, clear_risk_levels_cache):
    """JSON parse 실패 → default fallback."""
    from models.closure_risk import predict as predict_mod

    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(predict_mod, "WEIGHTS_DIR", tmp_path)

    levels = predict_mod._load_risk_levels()
    assert levels == ((0.65, "danger"), (0.40, "caution"), (0.0, "safe"))


def test_classify_uses_loaded_threshold(tmp_path, monkeypatch, clear_risk_levels_cache):
    """fit threshold 적용 확인."""
    from models.closure_risk import predict as predict_mod

    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(
        json.dumps(
            {"thresholds": {"danger": 0.45, "caution": 0.30, "danger_quantile": 0.90, "caution_quantile": 0.70}}
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(predict_mod, "WEIGHTS_DIR", tmp_path)

    assert predict_mod._classify(0.50) == "danger"  # >= 0.45
    assert predict_mod._classify(0.40) == "caution"  # 0.30~0.45
    assert predict_mod._classify(0.20) == "safe"  # < 0.30


def test_classify_default_when_no_metrics(tmp_path, monkeypatch, clear_risk_levels_cache):
    """metrics.json 미존재 시 default 0.65/0.40 사용."""
    from models.closure_risk import predict as predict_mod

    monkeypatch.setattr(predict_mod, "WEIGHTS_DIR", tmp_path)

    assert predict_mod._classify(0.7) == "danger"
    assert predict_mod._classify(0.5) == "caution"
    assert predict_mod._classify(0.1) == "safe"


def test_train_writes_thresholds_to_metrics():
    """train() 실행 후 metrics.json 의 thresholds field 가 생성되어야 함.

    DB 호출 없는 sanity test — 실제 retrain 은 T4 에서.
    여기서는 이미 존재하는 weights/metrics.json 의 thresholds field shape 만 검증.
    metrics.json 미존재 또는 thresholds key 미존재 (T4 retrain 전) 시 skip.
    """
    from models.closure_risk.model import WEIGHTS_DIR

    metrics_path = WEIGHTS_DIR / "metrics.json"
    if not metrics_path.exists():
        pytest.skip("metrics.json 미존재 — production retrain 후 검증 가능")

    with open(metrics_path, encoding="utf-8") as f:
        m = json.load(f)

    if "thresholds" not in m:
        pytest.skip("thresholds key 미존재 — T4 retrain 후 검증 가능")

    t = m["thresholds"]
    assert "danger" in t and "caution" in t, "thresholds 가 danger/caution 키를 포함해야 함"
    assert "danger_quantile" in t and "caution_quantile" in t
    assert 0.0 <= t["caution"] <= t["danger"] <= 1.0, (
        f"threshold 정렬 위반: caution={t['caution']}, danger={t['danger']}"
    )
    assert t["danger_quantile"] >= t["caution_quantile"]
