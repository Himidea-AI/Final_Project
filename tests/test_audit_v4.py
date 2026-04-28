# tests/test_audit_v4.py
"""Phase 2 감사 단위 테스트 — 10 지표 정확성."""

from __future__ import annotations

import numpy as np

from validation.audit_v4 import (
    diagnose_failure,
    f1_4tier,
    mase,
    oom_accuracy,
    rmsle,
)


def test_oom_accuracy_perfect():
    actual = np.array([100, 200, 300])
    pred = actual.copy()
    assert oom_accuracy(actual, pred) == 1.0


def test_oom_accuracy_one_outlier():
    actual = np.array([100, 200, 300, 400])
    pred = np.array([100, 200, 300, 1000])  # 마지막만 2.5x
    assert 0.7 < oom_accuracy(actual, pred) < 0.8


def test_f1_4tier_perfect():
    actual = np.array([10, 20, 30, 40, 50, 60, 70, 80])
    pred = actual.copy()
    assert f1_4tier(actual, pred) > 0.99


def test_mase_naive_baseline():
    actual = np.array([100, 110, 120, 130])
    pred = actual.copy()  # 완벽 예측
    assert mase(actual, pred) < 0.01


def test_rmsle_perfect():
    actual = np.array([100, 200, 300])
    pred = actual.copy()
    assert rmsle(actual, pred) < 1e-6


def test_diagnose_failure_mnar_over_15():
    audit = {
        "mnar_wape": {"mean": 0.20, "pass": False},
        "lodo_wape": {"mean": 0.25, "pass": True},
        "pearson_r": {"value": 0.98, "pass": True},
    }
    diags = diagnose_failure(audit)
    assert any("MNAR" in d for d in diags)
    assert any("confidence 일괄 0.10 하향" in d for d in diags)


def test_diagnose_failure_lodo_over_30():
    audit = {
        "mnar_wape": {"mean": 0.13, "pass": True},
        "lodo_wape": {"mean": 0.35, "pass": False},
        "pearson_r": {"value": 0.98, "pass": True},
    }
    diags = diagnose_failure(audit)
    assert any("LODO" in d for d in diags)


def test_diagnose_failure_pearson_r_low():
    audit = {
        "mnar_wape": {"mean": 0.13, "pass": True},
        "lodo_wape": {"mean": 0.25, "pass": True},
        "pearson_r": {"value": 0.92, "pass": False},
    }
    diags = diagnose_failure(audit)
    assert any("Pearson r" in d or "순위" in d for d in diags)
