"""
공통 API 클라이언트 — 모든 외부 API 서비스의 베이스 클래스
retry, rate limit, 에러 핸들링, 로깅 공통 처리
"""
from datetime import datetime
from typing import Any, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential


class BaseAPIClient:
    """외부 API 호출을 위한 베이스 클라이언트"""

    def __init__(self, base_url: str, api_key: Optional[str] = None, timeout: int = 10):
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout

    def _log(self, status: str, message: str) -> None:
        """표준 로그 포맷 출력"""
        print(f"[{datetime.now()}] [{self.__class__.__name__}] [{status}] - {message}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def _request(self, method: str, endpoint: str, params: Optional[dict] = None) -> dict:
        """
        HTTP 요청 공통 메서드 — 3회 재시도 + 지수 백오프
        """
        url = f"{self.base_url}{endpoint}"
        self._log("TOOL_CALL", f"{method.upper()} {url}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(method, url, params=params)
            response.raise_for_status()
            self._log("SUCCESS", f"Status {response.status_code}")
            return response.json()

    async def get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """GET 요청"""
        return await self._request("GET", endpoint, params=params)
