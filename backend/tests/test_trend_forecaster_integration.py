"""trend_forecaster 에이전트 통합 테스트.

실 RDS 연결 (test_tools_demographic.py 패턴 복제).
conftest.py가 .env 로드 + POSTGRES_URL 처리.
LLM e2e 테스트는 실제 API 호출하여 비용/시간 소요 — 하나만 포함.

실행: cd backend && pytest tests/test_trend_forecaster_integration.py -v
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from src.agents.tools import MarketDataTool
from src.config.settings import settings
from src.database.postgres import PostgresClient


@pytest_asyncio.fixture
async def tool():
    db = PostgresClient(settings.postgres_url)
    await db.connect()
    try:
        yield MarketDataTool(db)
    finally:
        await db.disconnect()


# ==================== resolve_industry (순수 함수, DB 불필요) ====================


def test_resolve_industry_cs_code_priority():
    t = MarketDataTool(None)
    # CS 코드가 brand보다 우선
    assert t.resolve_industry(industry_filter="CS100010", brand_name="교촌") == "카페"


def test_resolve_industry_brand_before_business_type():
    t = MarketDataTool(None)
    # brand가 business_type보다 우선
    assert t.resolve_industry(brand_name="빽다방", business_type="한식") == "커피"


def test_resolve_industry_english_business_type():
    t = MarketDataTool(None)
    assert t.resolve_industry(business_type="cafe") == "카페"
    assert t.resolve_industry(business_type="COFFEE") == "커피"  # 대소문자 방어


def test_resolve_industry_default_fallback():
    t = MarketDataTool(None)
    assert t.resolve_industry() == "한식"
    assert t.resolve_industry(business_type="존재안하는업종") == "한식"


# ==================== get_industry_trend ====================


@pytest.mark.asyncio
async def test_get_industry_trend_coffee(tool: MarketDataTool):
    r = await tool.get_industry_trend("커피", months_back=24)
    assert r["current_ratio"] is not None
    assert r["current_ratio"] > 0
    assert r["direction"] in ("rising", "stable", "declining", "unknown")
    assert len(r["samples"]) >= 12  # 최소 12개월
    # YoY는 13개월 이상 데이터가 있을 때만 계산됨
    if len(r["samples"]) >= 13:
        assert r["yoy_change_pct"] is not None


@pytest.mark.asyncio
async def test_get_industry_trend_unknown_industry(tool: MarketDataTool):
    r = await tool.get_industry_trend("존재안하는업종")
    assert r["samples"] == []
    assert r["current_ratio"] is None
    assert r["direction"] == "unknown"


# ==================== get_dong_trend_quarterly ====================


@pytest.mark.asyncio
async def test_get_dong_trend_quarterly_seogyo(tool: MarketDataTool):
    r = await tool.get_dong_trend_quarterly("서교동", quarters_back=8)
    assert r["recent_score"] is not None
    assert r["max_quarter"] is not None
    assert r["max_quarter"] >= 20244  # Step 0 확인: 최신 2024 Q4
    assert len(r["samples"]) > 0


@pytest.mark.asyncio
async def test_get_dong_trend_quarterly_unknown(tool: MarketDataTool):
    r = await tool.get_dong_trend_quarterly("존재안하는동")
    assert r["samples"] == []
    assert r["recent_score"] is None


# ==================== get_adstrd_change_ix ====================


@pytest.mark.asyncio
async def test_get_adstrd_change_ix_seogyo(tool: MarketDataTool):
    r = await tool.get_adstrd_change_ix("서교동")
    assert r["current"] is not None
    # Step 0 확인: 서교동 2025 Q4 = LL (다이나믹)
    assert r["current"]["change_ix_class"] in ("HH", "LH", "HL", "LL")
    assert r["current"]["change_ix_label"] in ("정체", "상권확장", "상권축소", "다이나믹")
    assert r["current"]["opr_months"] is not None
    assert r["current"]["opr_vs_seoul_ratio"] is not None
    assert len(r["history"]) > 0


@pytest.mark.asyncio
async def test_get_adstrd_change_ix_seongsan2(tool: MarketDataTool):
    # Step 0 확인: 성산2동 = HH (정체)
    r = await tool.get_adstrd_change_ix("성산2동")
    assert r["current"]["change_ix_label"] == "정체"


@pytest.mark.asyncio
async def test_get_adstrd_change_ix_unknown(tool: MarketDataTool):
    r = await tool.get_adstrd_change_ix("존재안하는동")
    assert r["current"] is None
    assert r["history"] == []


# ==================== get_base_rate_trend ====================


@pytest.mark.asyncio
async def test_get_base_rate_trend(tool: MarketDataTool):
    r = await tool.get_base_rate_trend(months_back=12)
    assert r["current"] is not None
    # Step 0 확인: 2026-03 = 2.5%
    assert 1.0 <= r["current"] <= 5.0  # 상식 범위
    assert r["trend"] in ("rising", "stable", "declining", "unknown")
    assert len(r["samples"]) == 12


# ==================== Node e2e (LLM 실호출) ====================


@pytest.mark.asyncio
async def test_trend_forecaster_node_seogyo_coffee():
    """e2e: 서교동 + 빽다방 + 커피. 실 DB + 실 LLM."""
    from src.agents.nodes.trend_forecaster import trend_forecaster_node

    state = {
        "target_district": "서교동",
        "brand_name": "빽다방",
        "business_type": "카페",
        "industry_filter": "CS100010",  # B1 필드 활용
        "analysis_results": {},
        "analysis_metrics": {},
    }
    result = await trend_forecaster_node(state)

    # state 병합 결과 확인
    assert "analysis_results" in result
    assert "trend_forecast" in result["analysis_results"]
    assert "analysis_metrics" in result
    assert result["current_agent"] == "trend_forecaster"

    # report 구조 검증
    report = result["analysis_results"]["trend_forecast"]
    assert report["industry_trend"]["industry"] == "카페"  # CS100010 → 카페
    assert report["industry_trend"]["current_ratio"] is not None
    assert report["change_ix"] is not None
    assert report["macro"]["current_base_rate"] is not None

    # forecast 검증
    forecast = report["forecast"]
    assert 0 <= forecast["score"] <= 100
    assert forecast["direction"] in (
        "strong_growth",
        "growth",
        "stable",
        "decline",
        "strong_decline",
    )
    assert forecast["confidence"] in ("high", "medium", "low")
    assert forecast["horizon_months"] == 12
    assert isinstance(forecast["narrative"], str)
    assert len(forecast["narrative"]) > 10

    # metrics 병합 확인
    metrics = result["analysis_metrics"]
    assert "trend_forecast_score" in metrics
    assert "trend_base_rate" in metrics
