from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from src.config.constants import MAPO_DISTRICTS  # noqa: E402
from src.main import app, map_state_to_simulation_output  # noqa: E402


def test_map_state_to_simulation_output_includes_final_report(monkeypatch):
    import src.main as main

    target_district = MAPO_DISTRICTS[0]
    monkeypatch.setattr(main, "_resolve_dong_code", lambda _dong: "11440660")
    monkeypatch.setattr(main, "explain_tcn_prediction", lambda dong_code, industry_code: None)

    state = {
        "target_district": target_district,
        "target_districts": [target_district],
        "market_data": {},
        "analysis_metrics": {},
        "analysis_results": {
            "legal_risks": [],
            "final_report": {
                "summary": "recommended district",
                "sections": [{"title": "summary", "body": "good fit"}],
            },
        },
    }

    output = map_state_to_simulation_output(state, "request-1")

    assert output["final_report"] == {
        "summary": "recommended district",
        "sections": [{"title": "summary", "body": "good fit"}],
    }


def test_map_state_to_simulation_output_uses_null_when_final_report_missing(monkeypatch):
    import src.main as main

    target_district = MAPO_DISTRICTS[0]
    monkeypatch.setattr(main, "_resolve_dong_code", lambda _dong: "11440660")
    monkeypatch.setattr(main, "explain_tcn_prediction", lambda dong_code, industry_code: None)

    state = {
        "target_district": target_district,
        "target_districts": [target_district],
        "market_data": {},
        "analysis_metrics": {},
        "analysis_results": {"legal_risks": []},
    }

    output = map_state_to_simulation_output(state, "request-1")

    assert output["final_report"] is None


def test_simulate_endpoint_is_kept_as_deprecated_legacy_route():
    routes = [
        route
        for route in app.routes
        if getattr(route, "path", None) == "/simulate" and "POST" in getattr(route, "methods", set())
    ]

    assert routes, "POST /simulate should remain for frontend compatibility"
    assert getattr(routes[0], "deprecated", False) is True


def test_simulate_endpoint_sets_deprecation_headers(monkeypatch):
    monkeypatch.setenv("LLM_AGENTS_DISABLED", "1")
    target_district = MAPO_DISTRICTS[0]

    response = TestClient(app).post(
        "/simulate",
        json={
            "target_district": target_district,
            "target_districts": [target_district],
            "business_type": "cafe",
            "brand_name": "Legacy Header Test",
        },
    )

    assert response.status_code == 200
    assert response.headers["Deprecation"] == "true"
    assert "/predict" in response.headers["Link"]
    assert "/analyze/llm" in response.headers["Link"]
