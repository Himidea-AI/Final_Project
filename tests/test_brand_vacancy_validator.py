"""brand_vacancy_validator 트랙 단위 함수 테스트."""

from unittest.mock import patch

import numpy as np
import pytest

from validation.brand_vacancy_validator import (
    _track_ci,
    _track_v1a,
    _track_v1b,
    _track_v1c,
    _track_v2,
    diagnose_failure,
    run_5track_validation,
)


class TestTrackV1a:
    def test_pass_when_strict_correlation(self):
        """sim ≈ actual×1.05 → r≈0.99, mape≈5% → pass."""
        actual = {(f"d{i}", "카페"): float(100 + i * 10) for i in range(20)}
        sim = {k: v * 1.05 for k, v in actual.items()}
        result = _track_v1a(sim, actual)
        assert result["status"] == "ok"
        assert result["pearson_r"] >= 0.5
        assert result["mape"] <= 0.50
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
        assert result["thresholds"]["r_min"] == 0.45
        assert result["thresholds"]["mape_max"] == 0.55


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
        sim = {(f"d{i}", "카페"): 200_000 for i in range(20)}
        actual = {(f"d{i}", "카페"): 1_000_000 for i in range(20)}
        result = _track_v1c(sim, actual)
        assert result["pass"] is False
        assert result["mean_ratio"] == pytest.approx(0.2, abs=0.01)


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
        result = _track_v2(sim_yearly=400_000_000, ftc_avg_yearly=100_000_000)
        assert result["pass"] is False
        assert result["ratio"] == 4.0


class TestTrackCi:
    def test_pass_when_low_variance(self):
        pse = {"revenue_per_day": {"mean": 100, "ci95": 8}}
        result = _track_ci(pse)
        assert result["pass"] is True
        assert result["ci_ratio"] == pytest.approx(0.08, abs=0.001)

    def test_fail_when_high_variance(self):
        pse = {"revenue_per_day": {"mean": 100, "ci95": 35}}  # 25 → 35
        result = _track_ci(pse)
        assert result["pass"] is False

    def test_incomplete_when_zero_mean(self):
        pse = {"revenue_per_day": {"mean": 0, "ci95": 0}}
        result = _track_ci(pse)
        assert result["status"] == "incomplete"
        assert result["pass"] is False


class TestDiagnoseFailure:
    def test_v1a_fail_message(self):
        tracks = {
            "v1a": {"status": "ok", "pearson_r": 0.5, "mape": 0.4, "pass": False},
            "v1b": {"status": "ok", "pass": True},
            "v1c": {"status": "ok", "pass": True},
            "v2": {"status": "ok", "pass": True},
            "ci": {"status": "ok", "pass": True},
        }
        diagnoses = diagnose_failure(tracks)
        assert any("V1a fail" in d for d in diagnoses)

    def test_v1c_high_ratio_message(self):
        tracks = {
            "v1a": {"status": "ok", "pass": True},
            "v1b": {"status": "ok", "pass": True},
            "v1c": {"status": "ok", "mean_ratio": 2.5, "pass": False},
            "v2": {"status": "ok", "pass": True},
            "ci": {"status": "ok", "pass": True},
        }
        diagnoses = diagnose_failure(tracks)
        assert any("V1c fail" in d and "150" in d for d in diagnoses)

    def test_all_pass_no_diagnoses(self):
        tracks = {k: {"status": "ok", "pass": True} for k in ["v1a", "v1b", "v1c", "v2", "ci"]}
        assert diagnose_failure(tracks) == []


class TestRun5TrackValidation:
    @patch("validation.brand_vacancy_validator._collect_actual_data")
    @patch("validation.brand_vacancy_validator._run_validation_simulations")
    @patch("validation.brand_vacancy_validator._dump_report")
    def test_all_pass_production_ready(self, mock_dump, mock_sim, mock_actual):
        # 모두 통과하는 가짜 데이터 (varying per cell for non-zero variance in V1a/V1b)
        actual_sales = {(f"d{i}", "카페"): 1.0e9 * (1 + i * 0.05) for i in range(20)}
        actual_count = {(f"d{i}", "카페"): 1.0e6 * (1 + i * 0.05) for i in range(20)}
        actual_per_store = {(f"d{i}", "카페"): 1.0e7 * (1 + i * 0.05) for i in range(20)}
        mock_actual.return_value = {
            "district_sales": actual_sales,
            "district_count": actual_count,
            "per_store_avg": actual_per_store,
            "ftc_avg": 100_000_000,
        }
        mock_sim.return_value = {
            "dong_industry_revenue": {k: v * 1.05 for k, v in actual_sales.items()},
            "dong_industry_visits": {k: v * 1.05 for k, v in actual_count.items()},
            "per_store_revenue": {k: v * 1.1 for k, v in actual_per_store.items()},
            "vacancy_yearly_rev": 110_000_000,
            "pse_summary": {"revenue_per_day": {"mean": 100, "ci95": 5}},
        }
        report = run_5track_validation("이디야", "카페", days=90, n_seeds=3)
        assert report["production_ready"] is True
        for t in ["v1a", "v1b", "v1c", "v2", "ci"]:
            assert report["tracks"][t]["pass"] is True

    @patch("validation.brand_vacancy_validator._collect_actual_data")
    @patch("validation.brand_vacancy_validator._run_validation_simulations")
    @patch("validation.brand_vacancy_validator._dump_report")
    def test_v2_skipped_auto_fail(self, mock_dump, mock_sim, mock_actual):
        cells = {(f"d{i}", "카페"): 1.0e9 for i in range(20)}
        mock_actual.return_value = {
            "district_sales": cells,
            "district_count": {k: 1.0e6 for k in cells},
            "per_store_avg": {k: 1.0e7 for k in cells},
            "ftc_avg": None,  # 누락
        }
        mock_sim.return_value = {
            "dong_industry_revenue": {k: 1.0e9 * 1.05 for k in cells},
            "dong_industry_visits": {k: 1.0e6 * 1.05 for k in cells},
            "per_store_revenue": {k: 1.0e7 * 1.1 for k in cells},
            "vacancy_yearly_rev": 110_000_000,
            "pse_summary": {"revenue_per_day": {"mean": 100, "ci95": 5}},
        }
        report = run_5track_validation("이디야", "카페")
        assert report["tracks"]["v2"]["status"] == "skipped"
        assert report["production_ready"] is False
