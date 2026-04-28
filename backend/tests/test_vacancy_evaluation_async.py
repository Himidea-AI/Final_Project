"""vacancy_pse 비동기 실행 + cache 단위 테스트."""

import time
from unittest.mock import patch

import pytest

from src.services.vacancy_evaluation_service import (
    cleanup_expired_cache,
    run_vacancy_pse_async,
    vacancy_pse_cache,
)


@pytest.fixture(autouse=True)
def clear_cache():
    vacancy_pse_cache.clear()
    yield
    vacancy_pse_cache.clear()


def test_run_async_returns_job_id():
    """run_vacancy_pse_async 즉시 job_id 반환 (시뮬은 background)."""
    spot = {"dong": "서교동", "lat": 37.5544, "lon": 126.9220}
    with patch("src.services.vacancy_evaluation_service.evaluate_vacancy_pse") as mock_pse:
        mock_pse.return_value = {"pse_summary": {"revenue_per_day": {"mean": 0}}}
        job_id = run_vacancy_pse_async(spot, "카페")
    assert isinstance(job_id, str)
    assert len(job_id) >= 16  # uuid
    assert job_id in vacancy_pse_cache


def test_async_status_running_then_done():
    """비동기 시작 시 'running', 시뮬 완료 후 'done'."""
    spot = {"dong": "서교동", "lat": 37.5544, "lon": 126.9220}
    with patch("src.services.vacancy_evaluation_service.evaluate_vacancy_pse") as mock_pse:
        mock_pse.return_value = {"pse_summary": {}, "narrative": "test"}
        job_id = run_vacancy_pse_async(spot, "카페")

    # max 5초 대기
    for _ in range(50):
        if vacancy_pse_cache[job_id]["status"] == "done":
            break
        time.sleep(0.1)

    assert vacancy_pse_cache[job_id]["status"] == "done"
    assert vacancy_pse_cache[job_id]["result"] is not None


def test_async_failed_on_exception():
    """vacancy_pse 예외 시 status='failed' + error message."""
    spot = {"dong": "서교동", "lat": 37.5544, "lon": 126.9220}
    with patch("src.services.vacancy_evaluation_service.evaluate_vacancy_pse") as mock_pse:
        mock_pse.side_effect = ValueError("test error")
        job_id = run_vacancy_pse_async(spot, "카페")

    for _ in range(50):
        if vacancy_pse_cache[job_id]["status"] == "failed":
            break
        time.sleep(0.1)

    assert vacancy_pse_cache[job_id]["status"] == "failed"
    assert "test error" in vacancy_pse_cache[job_id]["error"]


def test_cleanup_expired():
    """1시간 경과 job 제거."""
    vacancy_pse_cache["old_job"] = {"started_at": time.time() - 4000, "status": "done"}
    vacancy_pse_cache["new_job"] = {"started_at": time.time(), "status": "done"}
    cleanup_expired_cache(ttl_seconds=3600)
    assert "old_job" not in vacancy_pse_cache
    assert "new_job" in vacancy_pse_cache


def test_run_async_passes_collect_trajectory():
    """collect_trajectory=True / dump_visits=True 인자가 vacancy_pse 에 전달."""
    spot = {"dong": "서교동", "lat": 37.5544, "lon": 126.9220}
    with patch("src.services.vacancy_evaluation_service.evaluate_vacancy_pse") as mock_pse:
        mock_pse.return_value = {"pse_summary": {}}
        run_vacancy_pse_async(
            spot,
            "카페",
            collect_trajectory=True,
            dump_visits=True,
        )
        time.sleep(0.5)
        _, kwargs = mock_pse.call_args
        assert kwargs.get("collect_trajectory") is True
        assert kwargs.get("dump_visits") is True
