"""
서울 상권분석서비스(우리마을가게) API — 상권 현황, 폐업률, 생존율, 추정매출 조회

카드사 빅데이터 직접 접근은 기업 제휴 없이 불가하므로,
이 API에서 제공하는 "카드사 결제금액 기반 추정 매출" 데이터를 활용.

Base URL: http://openapi.seoul.go.kr:8088
Auth: API key in URL path.
"""
from src.services.base_client import BaseAPIClient


class GolmokAPIClient(BaseAPIClient):
    """서울 상권분석서비스 API 클라이언트"""

    def __init__(self, api_key: str):
        super().__init__(base_url="http://openapi.seoul.go.kr:8088", api_key=api_key)

    async def get_estimated_sales(
        self, trdar_cd: str, svc_induty_cd: str, start: int = 1, end: int = 100
    ) -> dict:
        """
        추정매출 조회 — 카드사 결제금액 기반 추정 매출

        Endpoint: /{api_key}/json/VwsmTrdarSelng/{start}/{end}
        Params: TRDAR_CD, SVC_INDUTY_CD

        Returns:
            dict: year, quarter, commercial_code, monthly_sales, monthly_count,
                  weekday_sales, weekend_sales
        """
        endpoint = f"/{self.api_key}/json/VwsmTrdarSelng/{start}/{end}"
        params = {
            "TRDAR_CD": trdar_cd,
            "SVC_INDUTY_CD": svc_induty_cd,
        }
        raw = await self.get(endpoint, params=params)

        rows = raw.get("VwsmTrdarSelng", {}).get("row", [])
        if not rows:
            return {
                "year": "",
                "quarter": "",
                "commercial_code": trdar_cd,
                "monthly_sales": 0,
                "monthly_count": 0,
                "weekday_sales": 0,
                "weekend_sales": 0,
            }

        row = rows[0]
        return {
            "year": row.get("STDR_YR_CD", ""),
            "quarter": row.get("STDR_QU_CD", ""),
            "commercial_code": row.get("TRDAR_CD", trdar_cd),
            "monthly_sales": int(row.get("THSMON_SELNG_AMT", 0)),
            "monthly_count": int(row.get("THSMON_SELNG_CO", 0)),
            "weekday_sales": int(row.get("MDW_SELNG_AMT", 0)),
            "weekend_sales": int(row.get("WKN_SELNG_AMT", 0)),
        }

    async def get_store_count(
        self, trdar_cd: str, svc_induty_cd: str, start: int = 1, end: int = 100
    ) -> dict:
        """
        점포 수 조회 — 업종별 점포 현황

        Endpoint: /{api_key}/json/VwsmTrdarStorQq/{start}/{end}

        Returns:
            dict: total_stores, franchise_stores, open_count, close_count
        """
        endpoint = f"/{self.api_key}/json/VwsmTrdarStorQq/{start}/{end}"
        params = {
            "TRDAR_CD": trdar_cd,
            "SVC_INDUTY_CD": svc_induty_cd,
        }
        raw = await self.get(endpoint, params=params)

        rows = raw.get("VwsmTrdarStorQq", {}).get("row", [])
        if not rows:
            return {
                "total_stores": 0,
                "franchise_stores": 0,
                "open_count": 0,
                "close_count": 0,
            }

        row = rows[0]
        return {
            "total_stores": int(row.get("STOR_CO", 0)),
            "franchise_stores": int(row.get("FRC_STOR_CO", 0)),
            "open_count": int(row.get("OPBIZ_STOR_CO", 0)),
            "close_count": int(row.get("CLSBIZ_STOR_CO", 0)),
        }

    async def get_commercial_area_info(
        self, trdar_cd: str, start: int = 1, end: int = 100
    ) -> dict:
        """
        상권 현황 조회

        Endpoint: /{api_key}/json/VwsmTrdarW/{start}/{end}

        Returns:
            dict: commercial_code, commercial_name, area_size
        """
        endpoint = f"/{self.api_key}/json/VwsmTrdarW/{start}/{end}"
        params = {
            "TRDAR_CD": trdar_cd,
        }
        raw = await self.get(endpoint, params=params)

        rows = raw.get("VwsmTrdarW", {}).get("row", [])
        if not rows:
            return {
                "commercial_code": trdar_cd,
                "commercial_name": "",
                "area_size": 0,
            }

        row = rows[0]
        return {
            "commercial_code": row.get("TRDAR_CD", trdar_cd),
            "commercial_name": row.get("TRDAR_NM", ""),
            "area_size": float(row.get("TRDAR_AREA_SIZE", 0)),
        }

    async def get_closure_survival_rate(
        self, trdar_cd: str, svc_induty_cd: str, start: int = 1, end: int = 100
    ) -> dict:
        """
        폐업률/생존율 조회

        Uses same VwsmTrdarStorQq endpoint as get_store_count.

        Returns:
            dict: open_count, close_count, closure_rate (close/(open+close)*100)
        """
        endpoint = f"/{self.api_key}/json/VwsmTrdarStorQq/{start}/{end}"
        params = {
            "TRDAR_CD": trdar_cd,
            "SVC_INDUTY_CD": svc_induty_cd,
        }
        raw = await self.get(endpoint, params=params)

        rows = raw.get("VwsmTrdarStorQq", {}).get("row", [])
        if not rows:
            return {
                "open_count": 0,
                "close_count": 0,
                "closure_rate": 0.0,
            }

        row = rows[0]
        open_count = int(row.get("OPBIZ_STOR_CO", 0))
        close_count = int(row.get("CLSBIZ_STOR_CO", 0))
        total = open_count + close_count
        closure_rate = (close_count / total * 100) if total > 0 else 0.0

        return {
            "open_count": open_count,
            "close_count": close_count,
            "closure_rate": round(closure_rate, 2),
        }
