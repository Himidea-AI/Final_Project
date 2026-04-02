"""
국토교통부 실거래가 API — 상가 임대료 추이 데이터 조회
"""
from src.services.base_client import BaseAPIClient


class MolitAPIClient(BaseAPIClient):
    """국토교통부 실거래가 API 클라이언트"""

    def __init__(self, api_key: str):
        super().__init__(base_url="https://apis.data.go.kr/1613000", api_key=api_key)

    async def get_commercial_rent(self, district: str, year_month: str = "") -> dict:
        """상가 임대료 실거래가 조회"""
        # TODO: 행정동별 상가 임대 실거래가 조회
        pass

    async def get_rent_trend(self, district: str, months: int = 12) -> dict:
        """임대료 추이 조회"""
        # TODO: 최근 N개월 임대료 변화 추이
        pass
