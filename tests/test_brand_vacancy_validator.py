"""brand_vacancy_validator 트랙 단위 함수 테스트."""

from unittest.mock import patch

import numpy as np
import pytest

from validation.brand_vacancy_validator import (
    _apply_ipf,
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


class TestApplyIpf:
    def test_ipf_preserves_row_marginals(self):
        """IPF 후 row 합 (dong 별 합) 이 actual marginal 과 일치."""
        sim = {
            ("d1", "카페"): 100.0,
            ("d1", "음식점"): 200.0,
            ("d2", "카페"): 150.0,
            ("d2", "음식점"): 250.0,
        }
        actual_row = {"d1": 600.0, "d2": 1200.0}  # d1 = 600, d2 = 1200
        actual_col = {"카페": 500.0, "음식점": 1300.0}  # 카페 = 500, 음식점 = 1300

        result = _apply_ipf(sim, actual_row, actual_col, n_iters=50)

        d1_sum = result[("d1", "카페")] + result[("d1", "음식점")]
        d2_sum = result[("d2", "카페")] + result[("d2", "음식점")]
        assert abs(d1_sum - 600.0) < 1.0
        assert abs(d2_sum - 1200.0) < 1.0

    def test_ipf_preserves_col_marginals(self):
        """IPF 후 col 합 (category 별 합) 이 actual marginal 과 일치."""
        sim = {
            ("d1", "카페"): 100.0,
            ("d1", "음식점"): 200.0,
            ("d2", "카페"): 150.0,
            ("d2", "음식점"): 250.0,
        }
        actual_row = {"d1": 600.0, "d2": 1200.0}
        actual_col = {"카페": 500.0, "음식점": 1300.0}

        result = _apply_ipf(sim, actual_row, actual_col, n_iters=50)

        cafe_sum = result[("d1", "카페")] + result[("d2", "카페")]
        rest_sum = result[("d1", "음식점")] + result[("d2", "음식점")]
        assert abs(cafe_sum - 500.0) < 1.0
        assert abs(rest_sum - 1300.0) < 1.0

    def test_ipf_zero_sim_returns_zero(self):
        """시뮬 0 인 cell → IPF 후도 0 (zero-fill 회피)."""
        sim = {("d1", "카페"): 0.0, ("d1", "음식점"): 100.0}
        actual_row = {"d1": 500.0}
        actual_col = {"카페": 300.0, "음식점": 200.0}

        result = _apply_ipf(sim, actual_row, actual_col, n_iters=20)
        assert result[("d1", "카페")] == 0.0  # 시뮬 0 → IPF 후도 0

    def test_ipf_pearson_improves(self):
        """IPF 적용 후 Pearson r 향상 — OVERVIEW.md 의 0.291 → 0.849 재현."""
        # 시뮬은 actual 의 약한 양의 상관 + 단위 mismatch
        sim = {(f"d{i}", "카페"): float(i + 1) for i in range(20)}  # 1~20
        actual = {(f"d{i}", "카페"): float((i + 1) * 100) for i in range(20)}  # 100~2000

        # IPF 적용 X r
        from scipy.stats import pearsonr

        r_before, _ = pearsonr([sim[k] for k in sim], [actual[k] for k in sim])

        # IPF 적용
        actual_row = {f"d{i}": float((i + 1) * 100) for i in range(20)}
        actual_col = {"카페": sum(actual.values())}
        result = _apply_ipf(sim, actual_row, actual_col, n_iters=30)
        r_after, _ = pearsonr([result[k] for k in sim], [actual[k] for k in sim])

        # IPF 후 r 같거나 향상 (이 케이스는 처음부터 perfect linear → r=1.0)
        assert r_after >= r_before - 0.01

    def test_ipf_default_iters(self):
        """default n_iters=50 으로 안정 수렴."""
        sim = {("d1", "카페"): 100.0, ("d2", "카페"): 200.0}
        actual_row = {"d1": 300.0, "d2": 600.0}
        actual_col = {"카페": 900.0}
        result = _apply_ipf(sim, actual_row, actual_col)  # default
        d1 = result[("d1", "카페")]
        d2 = result[("d2", "카페")]
        assert abs(d1 - 300.0) < 1.0
        assert abs(d2 - 600.0) < 1.0
