"""evaluate_model 5 metric 정확성 + JSON/PNG 저장 검증."""

from __future__ import annotations

import json

import numpy as np

from models.closure_risk.evaluate import evaluate_model, save_metrics_and_plot


def test_evaluate_model_returns_5_metrics():
    """deterministic input → 5 metric 모두 [0,1] 범위."""
    rng = np.random.default_rng(42)
    n = 200
    y_true = rng.choice([0, 1], size=n, p=[0.8, 0.2])
    proba = np.clip(y_true * 0.5 + rng.normal(0.3, 0.15, size=n), 0, 1)

    metrics = evaluate_model(y_true=y_true, proba=proba, k_pct=10)

    for key in ["auc", "pr_auc", "p_at_k", "r_at_k", "brier"]:
        assert key in metrics, f"missing: {key}"
        assert 0.0 <= metrics[key] <= 1.0, f"{key} out of range: {metrics[key]}"
    assert "calibration" in metrics
    assert isinstance(metrics["calibration"], dict)
    assert "bin_centers" in metrics["calibration"]
    assert "actual_freq" in metrics["calibration"]


def test_evaluate_model_handles_imbalanced():
    """y 가 모두 0 → safe degenerate (모든 metric 0 또는 default)."""
    n = 100
    y_true = np.zeros(n, dtype=int)
    proba = np.full(n, 0.1)

    metrics = evaluate_model(y_true=y_true, proba=proba)
    assert metrics["auc"] == 0.5
    assert metrics["pr_auc"] == 0.0
    assert metrics["pos_ratio"] == 0.0


def test_save_metrics_creates_json(tmp_path):
    """metrics.json 저장 + 재로드 가능."""
    metrics = {
        "ensemble": {"val": evaluate_model(np.array([0, 1, 0, 1, 1]), np.array([0.1, 0.8, 0.2, 0.9, 0.6]))},
    }
    json_path = tmp_path / "metrics.json"

    save_metrics_and_plot(metrics, json_path, plot_path=None)

    assert json_path.exists()
    with open(json_path, encoding="utf-8") as f:
        loaded = json.load(f)
    assert "ensemble" in loaded
    assert "val" in loaded["ensemble"]
    assert "auc" in loaded["ensemble"]["val"]


def test_save_metrics_creates_png(tmp_path):
    """matplotlib 사용 가능 환경에서 calibration png 생성."""
    metrics = {
        "ensemble": {
            "val": evaluate_model(
                np.array([0, 1, 0, 1, 1, 0, 1, 0]), np.array([0.1, 0.8, 0.2, 0.9, 0.6, 0.3, 0.7, 0.15])
            )
        },
    }
    json_path = tmp_path / "metrics.json"
    plot_path = tmp_path / "calibration_curve.png"

    save_metrics_and_plot(metrics, json_path, plot_path=plot_path)

    assert json_path.exists()
    try:
        import matplotlib  # noqa: F401

        assert plot_path.exists()
    except ImportError:
        pass


def test_calibration_bins_have_correct_count():
    """10 bin → 10개 bin_centers."""
    rng = np.random.default_rng(0)
    n = 500
    y = rng.choice([0, 1], size=n, p=[0.7, 0.3])
    p = rng.uniform(0, 1, size=n)

    metrics = evaluate_model(y_true=y, proba=p)
    cal = metrics["calibration"]

    assert len(cal["bin_centers"]) == 10
    assert len(cal["actual_freq"]) == 10
    assert len(cal["n_per_bin"]) == 10
    assert sum(cal["n_per_bin"]) == n


def test_precision_at_k_correctness():
    """간단한 ground-truth — top 2 (k=20%) 중 1 개 양성 → P@K=0.5."""
    y_true = np.array([0, 0, 1, 0, 0, 0, 0, 0, 0, 1])
    proba = np.array([0.05, 0.1, 0.95, 0.2, 0.3, 0.15, 0.4, 0.35, 0.5, 0.6])
    # top 2 (k=20%) 의 idx: [2, 9] (proba 0.95, 0.6) → y=[1, 1] → P@K=1.0, R@K=2/2=1.0
    metrics = evaluate_model(y_true=y_true, proba=proba, k_pct=20)
    assert abs(metrics["p_at_k"] - 1.0) < 1e-6
    assert abs(metrics["r_at_k"] - 1.0) < 1e-6


def test_calibration_empty_bins_use_none_not_nan():
    """empty bin 의 actual_freq 가 None (NaN X) — JSON 호환."""
    # proba 가 한 bin 에만 몰려 다른 bin 들 비도록
    n = 100
    y_true = np.random.default_rng(0).choice([0, 1], size=n)
    proba = np.full(n, 0.05)  # 모두 첫 bin (0.0~0.1)

    metrics = evaluate_model(y_true=y_true, proba=proba)
    cal = metrics["calibration"]

    # 첫 bin 외 9 bin 은 모두 None (이전: NaN)
    for i, freq in enumerate(cal["actual_freq"]):
        if cal["n_per_bin"][i] == 0:
            assert freq is None, f"bin {i}: expected None, got {freq}"
        else:
            assert isinstance(freq, float)

    # JSON dump round-trip 가능 — NaN 이면 strict parser 실패
    import json

    s = json.dumps(metrics, allow_nan=False)  # strict
    loaded = json.loads(s)
    assert loaded["calibration"]["actual_freq"] == cal["actual_freq"]


def test_precision_at_k_clamps_when_k_exceeds_n():
    """k_pct=150 (n=10 → k=15 요청) → 실제 분모는 n=10 으로 clamp."""
    y_true = np.array([0, 0, 1, 0, 0, 0, 0, 0, 0, 1])
    proba = np.array([0.05, 0.1, 0.95, 0.2, 0.3, 0.15, 0.4, 0.35, 0.5, 0.6])
    # k_pct=150 → k=int(10*1.5)=15. 실제 top 은 n=10 개. precision 분모 10 으로 clamp.
    metrics = evaluate_model(y_true=y_true, proba=proba, k_pct=150)
    # 모든 양성 (2/10) 이 top 10 에 포함 → precision = 2/10 = 0.2
    assert abs(metrics["p_at_k"] - 0.2) < 1e-6, f"got {metrics['p_at_k']}"
