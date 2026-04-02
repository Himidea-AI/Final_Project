"""
서울 열린데이터광장 API — 생활인구(KT 통신 기반), 지하철 승하차 데이터 조회

주의: 서울시 자체 유동인구조사는 2015년 중단됨.
"서울 생활인구" 데이터(KT 통신 기반, 행정동 단위)를 사용해야 함.
API 코드: OA-14991 (서울 생활인구 - 행정동)
"""
from src.services.base_client import BaseAPIClient


class SeoulOpendataClient(BaseAPIClient):
    """서울 열린데이터광장 API 클라이언트"""

    # 서울 생활인구 API 코드
    LIVING_POPULATION_API = "OA-14991"

    def __init__(self, api_key: str):
        super().__init__(base_url="http://openapi.seoul.go.kr:8088", api_key=api_key)

    async def get_living_population(self, district: str, date: str = "") -> dict:
        """
        서울 생활인구 데이터 조회 (OA-14991)

        KT 통신 데이터 기반 행정동별 생활인구.
        서울시 자체 유동인구조사(2015년 중단) 대신 사용.

        Args:
            district: 행정동명
            date: 조회 날짜 (YYYYMMDD, 빈 값이면 최신)

        Returns:
            dict: 시간대별 생활인구, 평일/주말 패턴, 연령대별 분포
        """
        # TODO: /{api_key}/json/SPOP_LOCAL_RESD_DONG/{start}/{end} 호출
        # TODO: 행정동 코드로 필터링
        # TODO: 시간대별(0~23시) 생활인구 집계
        pass

    async def get_subway_traffic(self, station_name: str) -> dict:
        """
        지하철 승하차 데이터 조회

        Args:
            station_name: 역명

        Returns:
            dict: 일평균 승하차, 시간대별 분포
        """
        # TODO: 역별 월간 승하차 데이터 조회
        pass
