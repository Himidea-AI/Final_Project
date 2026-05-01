"""4 신규 endpoint + /single 의 collect_trajectory 인자 테스트."""

import time

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services.vacancy_evaluation_service import vacancy_pse_cache

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_cache():
    vacancy_pse_cache.clear()
    yield
    vacancy_pse_cache.clear()


def test_status_404_for_unknown_job():
    r = client.get("/vacancy-evaluation/nonexistent_uuid/status")
    assert r.status_code == 404


def test_status_running_then_done():
    """job 등록 후 status 조회."""
    vacancy_pse_cache["test_job"] = {
        "status": "running",
        "started_at": time.time(),
        "result": None,
        "error": None,
    }
    r = client.get("/vacancy-evaluation/test_job/status")
    assert r.status_code == 200
    assert r.json()["status"] == "running"


def test_trajectory_returns_list():
    """job done 시 trajectory list 반환."""
    vacancy_pse_cache["test_job"] = {
        "status": "done",
        "started_at": time.time(),
        "result": {
            "trajectory": [{"agent_id": 1, "hour": 7, "lat": 37.55, "lon": 126.92, "dong": "서교동"}],
            "visits_events": [],
            "pse_summary": {},
        },
        "error": None,
    }
    r = client.get("/vacancy-evaluation/test_job/trajectory")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["trajectory"], list)
    assert body["trajectory"][0]["agent_id"] == 1


def test_visits_returns_events():
    vacancy_pse_cache["test_job"] = {
        "status": "done",
        "started_at": time.time(),
        "result": {
            "trajectory": [],
            "visits_events": [{"agent_id": 1, "store_id": "vacancy_0_서교동", "hour": 13, "spend": 5000}],
            "pse_summary": {},
        },
        "error": None,
    }
    r = client.get("/vacancy-evaluation/test_job/visits")
    assert r.status_code == 200
    assert r.json()["visits_events"][0]["spend"] == 5000


def test_running_job_returns_409():
    """아직 running 인 job 의 trajectory 호출 → 409 Conflict."""
    vacancy_pse_cache["test_job"] = {
        "status": "running",
        "started_at": time.time(),
        "result": None,
        "error": None,
    }
    r = client.get("/vacancy-evaluation/test_job/trajectory")
    assert r.status_code == 409


def test_failed_job_returns_500():
    vacancy_pse_cache["test_job"] = {
        "status": "failed",
        "started_at": time.time(),
        "result": None,
        "error": "test error",
    }
    r = client.get("/vacancy-evaluation/test_job/trajectory")
    assert r.status_code == 500
    assert "test error" in r.json()["detail"]
