"""
서울 열린데이터광장 API — 생활인구(KT 통신 기반), 지하철 승하차 데이터 조회

주의: 서울시 자체 유동인구조사는 2015년 중단됨.
"서울 생활인구" 데이터(KT 통신 기반, 행정동 단위)를 사용해야 함.
API 코드: OA-14991 (서울 생활인구 - 행정동)
"""
from src.services.base_client import BaseAPIClient

# 생활인구 API 연령대 구간 목록
AGE_RANGES = [
    "F0T9", "F10T14", "F15T19", "F20T24", "F25T29",
    "F30T34", "F35T39", "F40T44", "F45T49", "F50T54",
    "F55T59", "F60T64", "F65T69", "F70T74",
]


class SeoulOpendataClient(BaseAPIClient):
    """서울 열린데이터광장 API 클라이언트"""

    # 서울 생활인구 API 코드
    LIVING_POPULATION_API = "SPOP_LOCAL_RESD_DONG"

    # 지하철 승하차 API 코드
    SUBWAY_API = "CardSubwayStatsNew"

    def __init__(self, api_key: str):
        super().__init__(base_url="http://openapi.seoul.go.kr:8088", api_key=api_key)

    async def get_living_population(
        self,
        district_code: str,
        date: str = "",
        start: int = 1,
        end: int = 5,
    ) -> dict:
        """
        서울 생활인구 데이터 조회 (SPOP_LOCAL_RESD_DONG)

        KT 통신 데이터 기반 행정동별 생활인구.
        서울시 자체 유동인구조사(2015년 중단) 대신 사용.

        Args:
            district_code: 행정동 코드 (ADSTRD_CODE_SE)
            date: 조회 날짜 (YYYYMMDD, 빈 값이면 최신)
            start: 페이징 시작 인덱스
            end: 페이징 종료 인덱스

        Returns:
            dict: {
                "total_population": float,
                "male": {age_range: float, ...},
                "female": {age_range: float, ...},
            }
        """
        endpoint = f"/{self.api_key}/json/{self.LIVING_POPULATION_API}/{start}/{end}"
        raw = await self.get(endpoint)

        rows = raw.get(self.LIVING_POPULATION_API, {}).get("row", [])

        # 행정동 코드와 날짜로 필터링 (값이 있을 때만)
        if district_code:
            rows = [r for r in rows if r.get("ADSTRD_CODE_SE") == district_code]
        if date:
            rows = [r for r in rows if r.get("STDR_DE_ID") == date]

        if not rows:
            return {"total_population": 0.0, "male": {}, "female": {}}

        # 여러 행이 있을 경우 첫 번째 행 사용 (시간대 구분 없이 단일 집계)
        row = rows[0]

        total_population = float(row.get("TOT_LVPOP_CO", 0))

        male = {
            age: float(row.get(f"MALE_{age}_LVPOP_CO", 0))
            for age in AGE_RANGES
        }
        female = {
            age: float(row.get(f"FEMALE_{age}_LVPOP_CO", 0))
            for age in AGE_RANGES
        }

        return {
            "total_population": total_population,
            "male": male,
            "female": female,
        }

    async def get_subway_traffic(self, station_name: str) -> dict:
        """
        지하철 승하차 데이터 조회 (CardSubwayStatsNew)

        Args:
            station_name: 역명

        Returns:
            dict: {
                "station": str,
                "total_ride": int,
                "total_alight": int,
            }
        """
        endpoint = f"/{self.api_key}/json/{self.SUBWAY_API}/1/5"
        raw = await self.get(endpoint)

        rows = raw.get(self.SUBWAY_API, {}).get("row", [])

        # 역명으로 필터링
        matched = [r for r in rows if r.get("SUBWAY_STATION_NAME") == station_name]

        if not matched:
            return {"station": station_name, "total_ride": 0, "total_alight": 0}

        row = matched[0]
        return {
            "station": row.get("SUBWAY_STATION_NAME", station_name),
            "total_ride": int(float(row.get("RIDE_PASGR_NUM", 0))),
            "total_alight": int(float(row.get("ALIGHT_PASGR_NUM", 0))),
        }
