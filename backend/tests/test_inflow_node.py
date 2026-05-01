"""
inflow_node (LangGraph 에이전트 래퍼) 테스트

에이전트 노드의 책임:
    1. score_all_districts 호출
    2. AgentAttribution 생성
    3. analysis_results["inflow_result"] 구조로 저장
    4. inflow_results 필드로 16동 전체 결과 전달

담당: A2 봉환
"""

from __future__ import annotations

import asyncio
import os
from unittest.mock import patch

import pytest

from src.agents.nodes.inflow import inflow_node


# ---------------------------------------------------------------------------
# Mock 기반 단위 테스트 (DB 불필요)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inflow_node_success_with_mock() -> None:
    """정상 경로 — score_all_districts mock 결과로 attribution·evidence 생성 확인."""
    mock_results = {
        "서교동": {
            "inflow_score": 95.7,
            "subway_sub": 56.7,
            "bus_sub": 100.0,
            "fclty_sub": 100.0,
            "evidence": {
                "nearest_subway": "망원 6호선",
                "subway_distance_m": 417,
                "subway_count_1km": 4,
                "bus_stop_count": 12,
                "bus_daily_avg_boarding": 8500.0,
                "fclty_count_by_type": {"univ_co": 1, "gnrl_hsptl_co": 2},
                "quarter": 20251,
            },
        },
        "연남동": {
            "inflow_score": 14.1,
            "subway_sub": 10.0,
            "bus_sub": 20.3,
            "fclty_sub": 10.0,
            "evidence": {"nearest_subway": "가좌 경의중앙선", "subway_distance_m": 728},
        },
    }

    state = {"winner_district": "서교동", "target_district": "서교동"}

    with patch("src.agents.nodes.inflow.score_all_districts", return_value=mock_results):
        result = await inflow_node(state)

    # 필드 구조 검증
    assert result["current_agent"] == "inflow"
    assert result["inflow_results"] == mock_results
    assert "analysis_results" in result
    assert "inflow_result" in result["analysis_results"]

    blob = result["analysis_results"]["inflow_result"]
    assert blob["target_district"] == "서교동"
    assert blob["target_score"] == 95.7
    assert blob["target_evidence"]["nearest_subway"] == "망원 6호선"

    attr = blob["agent_attribution"]
    assert attr["id"] == "inflow"
    assert attr["kind"] == "Python"
    assert attr["confidence"] == 0.85
    assert "서교동" in attr["verdict"]
    assert "96" in attr["verdict"] or "95" in attr["verdict"]  # 95.7 rounded
    assert "Hansen" in attr["reasoning"]
    assert "E2SFCA" in attr["reasoning"]
    assert set(attr["sources"]) == {"dong_subway_access", "bus_boarding_daily", "seoul_adstrd_fclty"}


@pytest.mark.asyncio
async def test_inflow_node_empty_results_graceful_fail() -> None:
    """빈 결과 반환 시 confidence 0, verdict '데이터 없음'."""
    state = {"winner_district": "서교동", "target_district": "서교동"}

    with patch("src.agents.nodes.inflow.score_all_districts", return_value={}):
        result = await inflow_node(state)

    attr = result["analysis_results"]["inflow_result"]["agent_attribution"]
    assert attr["confidence"] == 0.0
    assert "없음" in attr["verdict"]
    assert result["inflow_results"] == {}


@pytest.mark.asyncio
async def test_inflow_node_exception_graceful_fail() -> None:
    """score_all_districts가 예외 던져도 노드는 정상 반환."""
    state = {"winner_district": "서교동"}

    async def _raise(*args, **kwargs):
        raise RuntimeError("DB connection failed")

    with patch("src.agents.nodes.inflow.score_all_districts", side_effect=_raise):
        result = await inflow_node(state)

    assert result["current_agent"] == "inflow"
    assert result["inflow_results"] == {}
    attr = result["analysis_results"]["inflow_result"]["agent_attribution"]
    assert attr["confidence"] == 0.0


@pytest.mark.asyncio
async def test_inflow_node_uses_target_district_when_no_winner() -> None:
    """winner_district 없으면 target_district 사용."""
    mock_results = {
        "공덕동": {
            "inflow_score": 47.8,
            "subway_sub": 47.9,
            "bus_sub": 49.1,
            "fclty_sub": 46.3,
            "evidence": {"nearest_subway": "애오개 5호선"},
        }
    }
    state = {"target_district": "공덕동"}  # winner_district 없음

    with patch("src.agents.nodes.inflow.score_all_districts", return_value=mock_results):
        result = await inflow_node(state)

    blob = result["analysis_results"]["inflow_result"]
    assert blob["target_district"] == "공덕동"
    assert blob["target_score"] == 47.8


# ---------------------------------------------------------------------------
# DB 통합 테스트 (RUN_DB_TESTS=1)
# ---------------------------------------------------------------------------


_DB_TESTS_ENABLED = os.environ.get("RUN_DB_TESTS", "").strip() == "1"


@pytest.mark.skipif(not _DB_TESTS_ENABLED, reason="RUN_DB_TESTS=1에서만 실행")
def test_inflow_node_real_db() -> None:
    """실DB로 에이전트 실행 — 16동 전체 계산 + attribution 생성 확인."""
    state = {"winner_district": "서교동", "target_district": "서교동"}
    result = asyncio.run(inflow_node(state))

    assert len(result["inflow_results"]) == 16
    attr = result["analysis_results"]["inflow_result"]["agent_attribution"]
    assert attr["confidence"] == 0.85
    assert "서교동" in attr["verdict"]

    # 기존 Phase B 검증(R²=0.55)과 분포 일치 확인
    scores = [r["inflow_score"] for r in result["inflow_results"].values()]
    assert max(scores) - min(scores) > 5.0, "점수 분포 너무 좁음"
