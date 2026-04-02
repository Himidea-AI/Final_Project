"""
서울 상권분석서비스(우리마을가게) API — 상권 현황, 폐업률, 생존율, 추정매출 조회

카드사 빅데이터 직접 접근은 기업 제휴 없이 불가하므로,
이 API에서 제공하는 "카드사 결제금액 기반 추정 매출" 데이터를 활용.
"""
from src.services.base_client import BaseAPIClient


class GolmokAPIClient(BaseAPIClient):
    """서울 상권분석서비스 API 클라이언트"""

    def __init__(self, api_key: str):
        super().__init__(base_url="https://golmok.seoul.go.kr/api", api_key=api_key)

    async def get_commercial_area_info(self, district: str) -> dict:
        """상권 현황 조회"""
        # TODO: 행정동별 상권 현황 데이터 조회
        pass

    async def get_estimated_sales(self, district: str, business_type: str) -> dict:
        """
        추정매출 조회 — 카드사 결제금액 기반 추정 매출

        카드사 빅데이터 직접 접근 대신 이 API를 사용.
        시간대별/요일별/연령대별 추정 매출 제공.

        Args:
            district: 행정동명
            business_type: 업종 코드

        Returns:
            dict: 월 추정매출, 시간대별 매출 비중, 요일별 매출 비중
        """
        # TODO: 추정매출 엔드포인트 호출
        # TODO: 시간대별/요일별/성별/연령대별 매출 분포 파싱
        pass

    async def get_closure_survival_rate(self, district: str, business_type: str) -> dict:
        """
        폐업률/생존율 조회

        Args:
            district: 행정동명
            business_type: 업종 코드

        Returns:
            dict: 폐업률, 1년/3년/5년 생존율, 개업 대비 폐업 비율
        """
        # TODO: 폐업/생존 관련 엔드포인트 호출
        pass

    async def get_store_count(self, district: str, business_type: str) -> dict:
        """
        점포 수 조회 — 업종별 점포 현황

        Returns:
            dict: 총 점포 수, 개업/폐업 수, 프랜차이즈 비율
        """
        # TODO: 점포 수 엔드포인트 호출
        pass
