"""
API 클라이언트 검증 — 외부 API 연동 테스트
모든 테스트는 외부 API를 호출하지 않고 httpx mock으로 검증.
"""
import pytest
import httpx
from unittest.mock import AsyncMock, patch

from src.services.base_client import BaseAPIClient
from src.services.seoul_opendata import SeoulOpendataClient
from src.services.sgis_api import SgisAPIClient
from src.services.semas_api import SemasAPIClient
from src.services.golmok_api import GolmokAPIClient
from src.services.molit_api import MolitAPIClient
from src.services.sns_trend import NaverTrendClient


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


# ---------------------------------------------------------------------------
# SgisAPIClient 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sgis_authenticate():
    """SgisAPIClient.authenticate OAuth2 토큰 발급 검증"""
    client = SgisAPIClient(consumer_key="test_key", consumer_secret="test_secret")
    mock = _mock_response(
        json_data={"errMsg": "Success", "errCd": 0, "result": {"accessToken": "mock_token_12345"}}
    )
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock):
        token = await client.authenticate()
        assert token == "mock_token_12345"
        assert client._access_token == "mock_token_12345"


@pytest.mark.asyncio
async def test_sgis_get_resident_population():
    """SgisAPIClient.get_resident_population 응답 파싱 검증"""
    client = SgisAPIClient(consumer_key="test_key", consumer_secret="test_secret")
    client._access_token = "mock_token"
    mock = _mock_response(
        json_data={
            "errMsg": "Success",
            "errCd": 0,
            "result": [{"adm_cd": "11440101", "population": 15000}],
        }
    )
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock):
        result = await client.get_resident_population(adm_cd="11440101")
        assert result[0]["population"] == 15000


# ---------------------------------------------------------------------------
# SemasAPIClient 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_semas_get_business_density():
    client = SemasAPIClient(api_key="test_key")
    mock = _mock_response(json_data={
        "body": {
            "items": [{"adongNm": "망원1동", "storCnt": 150, "bsnsCdNm": "커피전문점/카페"}],
            "totalCount": 1,
        }
    })
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock):
        result = await client.get_business_density(adong_cd="11440101", business_code="Q01A01")
        assert result["total_count"] == 1
        assert result["items"][0]["store_count"] == 150


# ---------------------------------------------------------------------------
# GolmokAPIClient 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_golmok_get_estimated_sales():
    client = GolmokAPIClient(api_key="test_key")
    mock = _mock_response(json_data={
        "VwsmTrdarSelng": {
            "list_total_count": 1,
            "row": [{
                "STDR_YR_CD": "2025", "STDR_QU_CD": "4", "TRDAR_CD": "1001",
                "SVC_INDUTY_CD": "CS100001", "THSMON_SELNG_AMT": 50000000,
                "THSMON_SELNG_CO": 3000, "MDW_SELNG_AMT": 8000000, "WKN_SELNG_AMT": 4000000,
            }],
        }
    })
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock):
        result = await client.get_estimated_sales(trdar_cd="1001", svc_induty_cd="CS100001")
        assert result["monthly_sales"] == 50000000
        assert result["weekday_sales"] == 8000000


# ---------------------------------------------------------------------------
# MolitAPIClient 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_molit_get_commercial_trade():
    client = MolitAPIClient(api_key="test_key")
    mock = _mock_response(json_data={
        "response": {
            "header": {"resultCode": "00"},
            "body": {
                "items": {"item": [{"dealAmount": "150,000", "buildingMainPurps": "제1종근린생활시설", "sggCd": "11440", "umdNm": "서교동", "dealYear": "2026", "dealMonth": "3", "excluUseAr": 45.5}]},
                "totalCount": 1,
            }
        }
    })
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock):
        result = await client.get_commercial_trade(sgg_cd="11440", deal_ymd="202603")
        assert len(result["items"]) == 1
        assert result["items"][0]["deal_amount"] == 150000


# ---------------------------------------------------------------------------
# NaverTrendClient 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_naver_get_search_trend():
    client = NaverTrendClient(client_id="test_id", client_secret="test_secret")
    mock = _mock_response(json_data={
        "startDate": "2025-04-01", "endDate": "2026-04-01", "timeUnit": "month",
        "results": [{"title": "망원동 카페", "keywords": ["망원동 카페"], "data": [{"period": "2026-03-01", "ratio": 85.5}, {"period": "2026-02-01", "ratio": 78.2}]}],
    })
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock):
        result = await client.get_search_trend(keywords=["망원동 카페"], start_date="2025-04-01", end_date="2026-04-01")
        assert result["results"][0]["title"] == "망원동 카페"
        assert result["results"][0]["data"][0]["ratio"] == 85.5
