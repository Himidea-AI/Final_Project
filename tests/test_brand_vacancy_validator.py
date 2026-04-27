"""brand_vacancy_validator 트랙 단위 함수 테스트."""

import numpy as np
import pytest

from validation.brand_vacancy_validator import (
    _track_ci,
    _track_v1a,
    _track_v1b,
    _track_v1c,
    _track_v2,
)


class TestTrackV1a:
    def test_pass_when_strict_correlation(self):
        """sim ≈ actual×1.05 → r≈0.99, mape≈5% → pass."""
        actual = {(f"d{i}", "카페"): float(100 + i * 10) for i in range(20)}
        sim = {k: v * 1.05 for k, v in actual.items()}
        result = _track_v1a(sim, actual)
        assert result["status"] == "ok"
        assert result["pearson_r"] >= 0.85
        assert result["mape"] <= 0.25
        assert result["pass"] is True

    def test_fail_when_random(self):
        """sim 무작위 → r≈0, fail."""
        actual = {(f"d{i}", "카페"): float(100 + i * 10) for i in range(20)}
        rng = np.random.default_rng(42)
        sim = {k: float(rng.uniform(0, 1000)) for k in actual.keys()}
        result = _track_v1a(sim, actual)
        assert result["status"] == "ok"
        assert result["pass"] is False

    def test_incomplete_when_too_few_cells(self):
        """공통 cell < 10 → incomplete + pass=False."""
        actual = {(f"d{i}", "카페"): 100.0 for i in range(5)}
        sim = {k: 100.0 for k in actual.keys()}
        result = _track_v1a(sim, actual)
        assert result["status"] == "incomplete"
        assert result["pass"] is False


class TestTrackV1b:
    def test_pass_with_strict_threshold(self):
        actual = {(f"d{i}", "카페"): float(100 + i * 10) for i in range(20)}
        sim = {k: v * 1.10 for k, v in actual.items()}
        result = _track_v1b(sim, actual)
        assert result["pass"] is True
        assert result["thresholds"]["r_min"] == 0.80
        assert result["thresholds"]["mape_max"] == 0.30


class TestTrackV1c:
    def test_pass_when_ratio_within(self):
        sim = {(f"d{i}", "카페"): 1_200_000 for i in range(20)}
        actual = {(f"d{i}", "카페"): 1_000_000 for i in range(20)}
        result = _track_v1c(sim, actual)
        assert result["pass"] is True
        assert result["mean_ratio"] == pytest.approx(1.2, abs=0.01)

    def test_fail_when_ratio_too_high(self):
        sim = {(f"d{i}", "카페"): 3_000_000 for i in range(20)}
        actual = {(f"d{i}", "카페"): 1_000_000 for i in range(20)}
        result = _track_v1c(sim, actual)
        assert result["pass"] is False
        assert result["mean_ratio"] == pytest.approx(3.0, abs=0.01)

    def test_fail_when_ratio_too_low(self):
        sim = {(f"d{i}", "카페"): 500_000 for i in range(20)}
        actual = {(f"d{i}", "카페"): 1_000_000 for i in range(20)}
        result = _track_v1c(sim, actual)
        assert result["pass"] is False
        assert result["mean_ratio"] == pytest.approx(0.5, abs=0.01)


class TestTrackV2:
    def test_pass_when_ratio_within(self):
        result = _track_v2(sim_yearly=120_000_000, ftc_avg_yearly=100_000_000)
        assert result["pass"] is True
        assert result["ratio"] == 1.2

    def test_skipped_when_ftc_missing(self):
        result = _track_v2(sim_yearly=120_000_000, ftc_avg_yearly=None)
        assert result["status"] == "skipped"
        assert result["pass"] is False

    def test_fail_when_ratio_too_high(self):
        result = _track_v2(sim_yearly=300_000_000, ftc_avg_yearly=100_000_000)
        assert result["pass"] is False
        assert result["ratio"] == 3.0


class TestTrackCi:
    def test_pass_when_low_variance(self):
        pse = {"revenue_per_day": {"mean": 100, "ci95": 8}}
        result = _track_ci(pse)
        assert result["pass"] is True
        assert result["ci_ratio"] == pytest.approx(0.08, abs=0.001)

    def test_fail_when_high_variance(self):
        pse = {"revenue_per_day": {"mean": 100, "ci95": 25}}
        result = _track_ci(pse)
        assert result["pass"] is False

    def test_incomplete_when_zero_mean(self):
        pse = {"revenue_per_day": {"mean": 0, "ci95": 0}}
        result = _track_ci(pse)
        assert result["status"] == "incomplete"
        assert result["pass"] is False
