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
