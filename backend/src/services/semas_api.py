"""
소상공인시장진흥공단 API — 업종밀도, 평균매출, 폐업률 데이터 조회
"""
from src.services.base_client import BaseAPIClient


def _extract_items(raw_items) -> list:
    """
    API 응답의 items 필드를 정규화.
    items가 dict with 'item' key, list, or single dict 모두 처리.
    """
    if isinstance(raw_items, list):
        return raw_items
    if isinstance(raw_items, dict):
        if "item" in raw_items:
            inner = raw_items["item"]
            if isinstance(inner, list):
                return inner
            return [inner]
        return [raw_items]
    return []


class SemasAPIClient(BaseAPIClient):
    """소상공인시장진흥공단 API 클라이언트"""

    def __init__(self, api_key: str):
        super().__init__(base_url="https://apis.data.go.kr/B553077", api_key=api_key)

    def _base_params(self) -> dict:
        """공통 쿼리 파라미터"""
        return {
            "ServiceKey": self.api_key,
            "type": "json",
            "numOfRows": 1000,
        }

    async def get_business_density(self, adong_cd: str, business_code: str) -> dict:
        """업종밀도 조회 — 행정동별 업종 점포 수"""
        params = self._base_params()
        params["adongCd"] = adong_cd
        params["indsLclsCd"] = business_code[:3]

        raw = await self.get(
            "/api/DataInqireService/getStoreInfoInUpjong", params=params
        )
        body = raw.get("body", {})
        total_count = body.get("totalCount", 0)
        raw_items = body.get("items", [])
        items = _extract_items(raw_items)

        return {
            "total_count": int(total_count),
            "items": [
                {
                    "district_name": item.get("adongNm", ""),
                    "store_count": int(item.get("storCnt", 0)),
                    "business_name": item.get("bsnsCdNm", ""),
                }
                for item in items
            ],
        }

    async def get_avg_revenue(self, adong_cd: str, business_code: str) -> dict:
        """평균매출 조회 — 행정동별 업종 평균 매출"""
        params = self._base_params()
        params["adongCd"] = adong_cd
        params["indsLclsCd"] = business_code[:3]

        raw = await self.get(
            "/api/DataInqireService/getStoreInfoInRevenue", params=params
        )
        body = raw.get("body", {})
        total_count = body.get("totalCount", 0)
        raw_items = body.get("items", [])
        items = _extract_items(raw_items)

        return {
            "total_count": int(total_count),
            "items": [
                {
                    "district_name": item.get("adongNm", ""),
                    "avg_monthly_revenue": int(item.get("avgMthSalesAmt", 0)),
                }
                for item in items
            ],
        }

    async def get_closure_rate(self, adong_cd: str, business_code: str) -> dict:
        """폐업률 조회 — 행정동별 업종 폐업 현황"""
        params = self._base_params()
        params["adongCd"] = adong_cd
        params["indsLclsCd"] = business_code[:3]

        raw = await self.get(
            "/api/DataInqireService/getStoreInfoInClose", params=params
        )
        body = raw.get("body", {})
        total_count = body.get("totalCount", 0)
        raw_items = body.get("items", [])
        items = _extract_items(raw_items)

        return {
            "total_count": int(total_count),
            "items": [
                {
                    "district_name": item.get("adongNm", ""),
                    "closure_count": int(item.get("clsbizCnt", 0)),
                    "closure_rate": float(item.get("clsbizRt", 0.0)),
                }
                for item in items
            ],
        }
