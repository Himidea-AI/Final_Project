"""
소상공인시장진흥공단 API — 업종밀도, 평균매출, 폐업률 데이터 조회
"""
from src.services.base_client import BaseAPIClient


class SemasAPIClient(BaseAPIClient):
    """소상공인시장진흥공단 API 클라이언트"""

    def __init__(self, api_key: str):
        super().__init__(base_url="https://apis.data.go.kr/B553077", api_key=api_key)

    async def get_business_density(self, district: str, business_type: str) -> dict:
        """업종밀도 조회"""
        # TODO: 행정동별 업종 점포 수 조회
        pass

    async def get_avg_revenue(self, district: str, business_type: str) -> dict:
        """평균매출 조회"""
        # TODO: 행정동별 업종 평균 매출 조회
        pass

    async def get_closure_rate(self, district: str, business_type: str) -> dict:
        """폐업률 조회"""
        # TODO: 행정동별 업종 폐업률 조회
        pass
