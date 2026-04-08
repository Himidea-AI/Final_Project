"""
통계청 SGIS API — 주거인구, 연령별 분포, 가구구성 데이터 조회

주의: SGIS는 OAuth2 인증이 필요.
consumer_key + consumer_secret으로 access_token을 먼저 발급받아야 함.
토큰 유효시간은 1시간.
"""
from typing import List

from src.services.base_client import BaseAPIClient


class SgisAPIClient(BaseAPIClient):
    """통계청 SGIS API 클라이언트 (OAuth2 인증)"""

    def __init__(self, consumer_key: str, consumer_secret: str):
        super().__init__(base_url="https://sgis.kostat.go.kr/OpenAPI3")
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self._access_token: str = ""

    async def authenticate(self) -> str:
        """
        OAuth2 액세스 토큰 발급

        Returns:
            str: access_token (유효시간 1시간)
        """
        data = await self.get(
            "/auth/authentication.json",
            params={
                "consumer_key": self.consumer_key,
                "consumer_secret": self.consumer_secret,
            },
        )
        token = data["result"]["accessToken"]
        self._access_token = token
        return token

    async def _ensure_token(self) -> None:
        """토큰이 없으면 자동 발급"""
        if not self._access_token:
            await self.authenticate()

    async def get_resident_population(self, adm_cd: str, year: str = "") -> List[dict]:
        """
        주거인구 조회

        Args:
            adm_cd: 행정동 코드
            year: 기준 연도 (선택)

        Returns:
            list: 주거인구 결과 리스트
        """
        await self._ensure_token()
        params = {
            "accessToken": self._access_token,
            "adm_cd": adm_cd,
        }
        if year:
            params["year"] = year
        data = await self.get("/stats/population.json", params=params)
        return data.get("result", [])

    async def get_age_distribution(self, adm_cd: str, year: str = "") -> List[dict]:
        """
        연령별 인구 분포 조회

        Args:
            adm_cd: 행정동 코드
            year: 기준 연도 (선택)

        Returns:
            list: 연령별 인구 결과 리스트
        """
        await self._ensure_token()
        params = {
            "accessToken": self._access_token,
            "adm_cd": adm_cd,
        }
        if year:
            params["year"] = year
        data = await self.get("/stats/agePopulation.json", params=params)
        return data.get("result", [])

    async def get_household_composition(self, adm_cd: str, year: str = "") -> List[dict]:
        """
        가구구성 조회

        Args:
            adm_cd: 행정동 코드
            year: 기준 연도 (선택)

        Returns:
            list: 가구구성 결과 리스트
        """
        await self._ensure_token()
        params = {
            "accessToken": self._access_token,
            "adm_cd": adm_cd,
        }
        if year:
            params["year"] = year
        data = await self.get("/stats/household.json", params=params)
        return data.get("result", [])
