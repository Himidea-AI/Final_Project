from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from src.config.constants import MAPO_DISTRICTS  # noqa: E402
from src.schemas.simulation_output import DistrictPredictionResult  # noqa: E402


def test_district_prediction_result_exposes_optional_extended_ml_fields():
    result = DistrictPredictionResult(
        district="district-a",
        dong_code="11440660",
        customer_segment={"profile_summary": "office workers"},
        living_pop_forecast={"dong_name": "district-a", "n_quarters": 4},
        emerging_signal={"signal": "emerging", "summary": "early growth"},
    )

    dumped = result.model_dump()

    assert dumped["customer_segment"] == {"profile_summary": "office workers"}
    assert dumped["living_pop_forecast"] == {"dong_name": "district-a", "n_quarters": 4}
    assert dumped["emerging_signal"] == {"signal": "emerging", "summary": "early growth"}


def test_district_prediction_result_defaults_extended_ml_fields_to_none():
    dumped = DistrictPredictionResult(district="district-a").model_dump()

    assert dumped["customer_segment"] is None
    assert dumped["living_pop_forecast"] is None
    assert dumped["emerging_signal"] is None


def test_predict_returns_extended_ml_fields_and_passes_segment_profile(monkeypatch):
    from src import main

    target_district = MAPO_DISTRICTS[0]

    async def fake_predict_single_district(
        dong_name: str,
        industry_code: str,
        industry_name: str,
        cost_config: dict,
        segment_profile: dict | None = None,
    ):
        assert dong_name == target_district
        assert segment_profile == {
            "age_groups": ["30s"],
            "gender": "female",
            "time_slots": ["time_11_14"],
            "day_type": "weekday",
        }
        return main.DistrictPredictionResult(
            district=dong_name,
            dong_code="11440660",
            customer_segment={"profile_summary": "30s female weekday lunch"},
            living_pop_forecast={"peak_time_zone": "11-14"},
            emerging_signal={"signal": "emerging"},
        )

    monkeypatch.setattr(main, "_predict_single_district", fake_predict_single_district)

    client = TestClient(main.app)
    response = client.post(
        "/predict",
        json={
            "target_district": target_district,
            "target_districts": [target_district],
            "business_type": "cafe",
            "brand_name": "Test Brand",
            "monthly_rent": 2_000_000,
            "initial_capital": 50_000_000,
            "target_age_groups": ["30s"],
            "target_gender": "female",
            "target_time_slots": ["time_11_14"],
            "target_day_type": "weekday",
            "target_monthly_sales": 30_000_000,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"][0]["customer_segment"] == {"profile_summary": "30s female weekday lunch"}
    assert body["data"][0]["living_pop_forecast"] == {"peak_time_zone": "11-14"}
    assert body["data"][0]["emerging_signal"] == {"signal": "emerging"}


def test_predict_response_serializes_numpy_scalars(monkeypatch):
    import numpy as np

    from src import main

    target_district = MAPO_DISTRICTS[0]

    async def fake_predict_single_district(
        dong_name: str,
        industry_code: str,
        industry_name: str,
        cost_config: dict,
        segment_profile: dict | None = None,
    ):
        return main.DistrictPredictionResult(
            district=dong_name,
            dong_code="11440660",
            closure_risk={
                "risk_score": np.float32(0.27),
                "risk_level": "caution",
                "top_signals_lgbm": [{"feature": "rent", "contribution": np.float32(0.12)}],
                "top_signals_tcn": [],
                "is_mock": False,
            },
            living_pop_forecast={
                "quarters": [
                    {
                        "quarter_offset": 1,
                        "peak_time_zone": np.int64(14),
                        "peak_pop": np.float32(1234.5),
                        "all_hours": [{"time_zone": 14, "predicted_pop": np.float32(1234.5)}],
                    }
                ]
            },
        )

    monkeypatch.setattr(main, "_predict_single_district", fake_predict_single_district)

    client = TestClient(main.app, raise_server_exceptions=False)
    response = client.post(
        "/predict",
        json={
            "target_district": target_district,
            "target_districts": [target_district],
            "business_type": "cafe",
            "brand_name": "Test Brand",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"][0]["closure_risk"]["risk_score"] == pytest.approx(0.27)
    assert body["data"][0]["closure_risk"]["top_signals_lgbm"][0]["contribution"] == pytest.approx(0.12)
    assert body["data"][0]["living_pop_forecast"]["quarters"][0]["peak_time_zone"] == 14
