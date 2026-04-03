"""
API 클라이언트 검증 — 외부 API 연동 테스트
모든 테스트는 외부 API를 호출하지 않고 httpx mock으로 검증.
"""
import pytest
import httpx
from unittest.mock import AsyncMock, patch

from src.services.base_client import BaseAPIClient
from src.services.seoul_opendata import SeoulOpendataClient


def _mock_response(status_code: int = 200, json_data: dict = None) -> httpx.Response:
    """테스트용 mock response 생성 (request 인스턴스 포함)"""
    response = httpx.Response(
        status_code,
        json=json_data,
        request=httpx.Request("GET", "https://example.com"),
    )
    return response


@pytest.mark.asyncio
async def test_base_client_get():
    """BaseAPIClient GET 요청 동작 검증"""
    client = BaseAPIClient(base_url="https://example.com", timeout=5)

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=_mock_response(json_data={"status": "ok"})):
        result = await client.get("/test")
        assert result == {"status": "ok"}


@pytest.mark.asyncio
async def test_base_client_post():
    """BaseAPIClient POST 요청 동작 검증"""
    client = BaseAPIClient(base_url="https://example.com", timeout=5)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=_mock_response(json_data={"result": "created"})):
        result = await client.post("/test", json_data={"key": "value"})
        assert result == {"result": "created"}


# ---------------------------------------------------------------------------
# SeoulOpendataClient 테스트
# ---------------------------------------------------------------------------

MOCK_LIVING_POPULATION_RESPONSE = {
    "SPOP_LOCAL_RESD_DONG": {
        "list_total_count": 1,
        "row": [
            {
                "STDR_DE_ID": "20260101",
                "TMZON_PD_SE": "00",
                "ADSTRD_CODE_SE": "11440",
                "TOT_LVPOP_CO": "12345.67",
                "MALE_F0T9_LVPOP_CO": "500.0",
                "MALE_F10T14_LVPOP_CO": "600.0",
                "MALE_F15T19_LVPOP_CO": "0.0",
                "MALE_F20T24_LVPOP_CO": "0.0",
                "MALE_F25T29_LVPOP_CO": "0.0",
                "MALE_F30T34_LVPOP_CO": "0.0",
                "MALE_F35T39_LVPOP_CO": "0.0",
                "MALE_F40T44_LVPOP_CO": "0.0",
                "MALE_F45T49_LVPOP_CO": "0.0",
                "MALE_F50T54_LVPOP_CO": "0.0",
                "MALE_F55T59_LVPOP_CO": "0.0",
                "MALE_F60T64_LVPOP_CO": "0.0",
                "MALE_F65T69_LVPOP_CO": "0.0",
                "MALE_F70T74_LVPOP_CO": "0.0",
                "FEMALE_F0T9_LVPOP_CO": "480.0",
                "FEMALE_F10T14_LVPOP_CO": "590.0",
                "FEMALE_F15T19_LVPOP_CO": "0.0",
                "FEMALE_F20T24_LVPOP_CO": "0.0",
                "FEMALE_F25T29_LVPOP_CO": "0.0",
                "FEMALE_F30T34_LVPOP_CO": "0.0",
                "FEMALE_F35T39_LVPOP_CO": "0.0",
                "FEMALE_F40T44_LVPOP_CO": "0.0",
                "FEMALE_F45T49_LVPOP_CO": "0.0",
                "FEMALE_F50T54_LVPOP_CO": "0.0",
                "FEMALE_F55T59_LVPOP_CO": "0.0",
                "FEMALE_F60T64_LVPOP_CO": "0.0",
                "FEMALE_F65T69_LVPOP_CO": "0.0",
                "FEMALE_F70T74_LVPOP_CO": "0.0",
            }
        ],
    }
}

MOCK_SUBWAY_RESPONSE = {
    "CardSubwayStatsNew": {
        "list_total_count": 1,
        "row": [
            {
                "SUBWAY_STATION_NAME": "합정",
                "RIDE_PASGR_NUM": "30000",
                "ALIGHT_PASGR_NUM": "28000",
            }
        ],
    }
}


@pytest.mark.asyncio
async def test_seoul_opendata_parse_population():
    """SeoulOpendataClient.get_living_population 응답 파싱 검증"""
    client = SeoulOpendataClient(api_key="TEST_KEY")

    with patch(
        "httpx.AsyncClient.request",
        new_callable=AsyncMock,
        return_value=_mock_response(json_data=MOCK_LIVING_POPULATION_RESPONSE),
    ):
        result = await client.get_living_population(
            district_code="11440", date="20260101", start=1, end=5
        )

    assert result["total_population"] == 12345.67

    # 남성 연령대 파싱 검증
    assert "male" in result
    assert result["male"]["F0T9"] == 500.0
    assert result["male"]["F10T14"] == 600.0

    # 여성 연령대 파싱 검증
    assert "female" in result
    assert result["female"]["F0T9"] == 480.0
    assert result["female"]["F10T14"] == 590.0


@pytest.mark.asyncio
async def test_seoul_opendata_parse_subway():
    """SeoulOpendataClient.get_subway_traffic 응답 파싱 검증"""
    client = SeoulOpendataClient(api_key="TEST_KEY")

    with patch(
        "httpx.AsyncClient.request",
        new_callable=AsyncMock,
        return_value=_mock_response(json_data=MOCK_SUBWAY_RESPONSE),
    ):
        result = await client.get_subway_traffic(station_name="합정")

    assert result["station"] == "합정"
    assert result["total_ride"] == 30000
    assert result["total_alight"] == 28000
