"""demographic_depth_node 통합 테스트: 실 DB + LLM mock."""

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
import redis.asyncio as aioredis

from src.config.settings import settings
from src.schemas.demographic import DemographicAnalysis


@pytest_asyncio.fixture(autouse=True)
async def clear_demographic_cache():
    """각 테스트 전 Redis의 v2:demographic:* 키를 정리해 캐시가 LLM mock을 건너뛰지 않도록 함."""
    r = None
    try:
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        keys = await r.keys("v2:demographic:*")
        if keys:
            await r.delete(*keys)
    except Exception:
        pass
    finally:
        if r is not None:
            try:
                await r.aclose()
            except Exception:
                pass
    yield


@pytest.mark.asyncio
async def test_demographic_depth_seogyo_coffee():
    """서교동 커피 — 모든 필드 채워짐"""
    from src.agents.nodes.demographic_depth import demographic_depth_node

    mock_analysis = DemographicAnalysis(
        brand_target_match_score=78.0,
        match_rationale="20대 여성 주 고객 매칭",
        narrative="서교동 커피는 20대 여성 주도",
    )
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_analysis)

    with patch("src.agents.nodes.demographic_depth.get_fast_llm") as mock_get_llm:
        mock_get_llm.return_value.with_structured_output.return_value = mock_llm
        state = {
            "target_district": "서교동",
            "brand_name": "빽다방",
            "industry_filter": "CS100010",
        }
        result = await demographic_depth_node(state)

    r = result["analysis_results"]["demographic_report"]
    assert r["core_demographic"]["share"] > 0
    assert len(r["top_3_age_groups"]) > 0
    assert len(r["peak_consumption_hours"]) > 0
    assert r["brand_target_match_score"] == 78.0
    assert r["match_rationale"] == "20대 여성 주 고객 매칭"


@pytest.mark.asyncio
async def test_demographic_depth_no_brand():
    from src.agents.nodes.demographic_depth import demographic_depth_node

    mock_analysis = DemographicAnalysis(
        brand_target_match_score=None,
        match_rationale=None,
        narrative="브랜드 없이 지역 분석만",
    )
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_analysis)

    with patch("src.agents.nodes.demographic_depth.get_fast_llm") as mock_get_llm:
        mock_get_llm.return_value.with_structured_output.return_value = mock_llm
        state = {"target_district": "서교동"}
        result = await demographic_depth_node(state)

    r = result["analysis_results"]["demographic_report"]
    assert r["brand_target_match_score"] is None
    assert r["match_rationale"] is None


@pytest.mark.asyncio
async def test_demographic_depth_unknown_dong():
    """매핑 없는 동 → 서교동 폴백 + 코드 그대로 통과 검증"""
    from src.agents.nodes.demographic_depth import _resolve_dong_code

    assert _resolve_dong_code("없는동") == "11440660"
    assert _resolve_dong_code("11440710") == "11440710"  # 코드 그대로
    assert _resolve_dong_code("서교동") == "11440660"


@pytest.mark.asyncio
async def test_demographic_depth_llm_failure_fallback():
    """LLM 예외 시에도 narrative가 기본값으로 채워져야 함"""
    from src.agents.nodes.demographic_depth import demographic_depth_node

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM down"))

    with patch("src.agents.nodes.demographic_depth.get_fast_llm") as mock_get_llm:
        mock_get_llm.return_value.with_structured_output.return_value = mock_llm
        state = {
            "target_district": "서교동",
            "industry_filter": "CS100010",
        }
        result = await demographic_depth_node(state)

    r = result["analysis_results"]["demographic_report"]
    assert r["narrative"]  # 기본값이라도 비어있지 않음
    assert "서교동" in r["narrative"] or "11440660" in r["narrative"]
