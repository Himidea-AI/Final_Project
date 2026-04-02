"""
통계청 SGIS API — 주거인구, 연령별 분포, 가구구성 데이터 조회

주의: SGIS는 OAuth2 인증이 필요.
consumer_key + consumer_secret으로 access_token을 먼저 발급받아야 함.
토큰 유효시간은 1시간.
"""
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
        # TODO: /auth/authentication.json 호출
        # TODO: consumer_key + consumer_secret 파라미터 전송
        # TODO: 응답에서 accessToken 추출
        # TODO: self._access_token에 저장
        pass

    async def _ensure_token(self) -> None:
        """토큰이 없으면 자동 발급"""
        if not self._access_token:
            await self.authenticate()

    async def get_resident_population(self, district: str) -> dict:
        """주거인구 조회"""
        await self._ensure_token()
        # TODO: /population/population.json 호출 (accessToken 포함)
        # TODO: 행정동 코드로 필터링
        pass

    async def get_age_distribution(self, district: str) -> dict:
        """연령별 인구 분포 조회"""
        await self._ensure_token()
        # TODO: 10세 단위 연령별 인구 조회
        pass

    async def get_household_composition(self, district: str) -> dict:
        """가구구성 조회"""
        await self._ensure_token()
        # TODO: 가구 유형별 데이터 조회
        pass
