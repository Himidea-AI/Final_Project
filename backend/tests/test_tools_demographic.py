"""
MarketDataTool demographic_depth 쿼리 함수 통합 테스트.

실제 RDS에 연결해 검증 (integration-style, SPOTTER 프로젝트 관례).
필요한 .env는 `C:/mapo-franchise-simulator/.env` (프로젝트 루트)에 위치.
conftest.py가 이미 load_dotenv() 및 POSTGRES_URL 환경변수를 처리함.
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


@pytest.mark.asyncio
async def test_demographic_sales_breakdown_seogyo_coffee(tool: MarketDataTool):
    r = await tool.get_demographic_sales_breakdown("11440660", industry_filter="CS100010")
    assert r.get("monthly_sales", 0) > 0
    assert set(r["age_breakdown"].keys()) == {"10", "20", "30", "40", "50", "60+"}
    assert set(r["gender_breakdown"].keys()) == {"male", "female"}
    assert len(r["time_breakdown"]) == 6
    assert len(r["weekday_breakdown"]) == 7
    assert r["quarter"] > 20200


@pytest.mark.asyncio
async def test_demographic_sales_breakdown_unknown_dong(tool: MarketDataTool):
    r = await tool.get_demographic_sales_breakdown("99999999")
    assert "error" in r


@pytest.mark.asyncio
async def test_realtime_resident_visitor_seogyo(tool: MarketDataTool):
    r = await tool.get_realtime_resident_visitor("11440660")
    # 7-day window 내 데이터가 없을 수 있으므로 shape만 확인
    assert "resident_rate" in r
    assert "visitor_rate" in r
    assert "source_poi" in r
    assert "sample_size" in r
    assert r["source_poi"] == ["POI007"]


@pytest.mark.asyncio
async def test_realtime_resident_visitor_unmapped_dong(tool: MarketDataTool):
    # 염리동 (11440610) — POI 매핑 없음
    r = await tool.get_realtime_resident_visitor("11440610")
    assert r["resident_rate"] is None
    assert r["visitor_rate"] is None
    assert r["source_poi"] is None
    assert r["sample_size"] == 0
