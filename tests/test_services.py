"""
API 클라이언트 검증 — 외부 API 연동 테스트
모든 테스트는 외부 API를 호출하지 않고 httpx mock으로 검증.
"""
import pytest
import httpx
from unittest.mock import AsyncMock, patch

from src.services.base_client import BaseAPIClient


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
