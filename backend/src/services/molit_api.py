"""
국토교통부 실거래가 API — 상업용 부동산 매매 실거래가 데이터 조회
Note: 임대차(rental) API는 data.go.kr에 존재하지 않으므로 매매(trade)만 제공.
"""
from datetime import datetime, timedelta
from typing import Optional

from src.services.base_client import BaseAPIClient


class MolitAPIClient(BaseAPIClient):
    """국토교통부 실거래가 API 클라이언트"""

    def __init__(self, api_key: str):
        super().__init__(base_url="https://apis.data.go.kr/1613000", api_key=api_key)

    async def get_commercial_trade(self, sgg_cd: str, deal_ymd: str) -> dict:
        """상업용 부동산 매매 실거래가 조회

        Args:
            sgg_cd: 시군구코드 (예: "11440")
            deal_ymd: 거래년월 YYYYMM (예: "202603")

        Returns:
            {
                "total_count": int,
                "items": [
                    {
                        "deal_amount": int,         # 만원 단위 정수
                        "building_purpose": str,    # 건물 주 용도
                        "sgg_cd": str,              # 시군구코드
                        "district_name": str,       # 읍면동명
                        "deal_year": str,
                        "deal_month": str,
                        "area": float,              # 전용면적(㎡)
                    }
                ]
            }
        """
        params = {
            "ServiceKey": self.api_key,
            "LAWD_CD": sgg_cd,
            "DEAL_YMD": deal_ymd,
            "type": "json",
            "numOfRows": 1000,
        }

        raw = await self.get(
            "/RTMSDataSvcNrgTrade/getRTMSDataSvcSHTrade",
            params=params,
        )

        body = raw.get("response", {}).get("body", {})
        total_count = int(body.get("totalCount", 0))

        # items 필드는 dict({"item": [...]}) / list / 단일 dict 등 세 가지 형태
        items_field = body.get("items", {})
        if isinstance(items_field, dict):
            raw_items = items_field.get("item", [])
        elif isinstance(items_field, list):
            raw_items = items_field
        else:
            raw_items = []

        # 단일 건이면 dict로 올 수 있음 → list로 통일
        if isinstance(raw_items, dict):
            raw_items = [raw_items]

        parsed = []
        for item in raw_items:
            # dealAmount: "150,000" → 150000 (만원)
            deal_amount_str = str(item.get("dealAmount", "0")).replace(",", "").strip()
            try:
                deal_amount = int(deal_amount_str)
            except ValueError:
                deal_amount = 0

            try:
                area = float(item.get("excluUseAr", 0))
            except (TypeError, ValueError):
                area = 0.0

            parsed.append({
                "deal_amount": deal_amount,
                "building_purpose": str(item.get("buildingMainPurps", "")),
                "sgg_cd": str(item.get("sggCd", "")),
                "district_name": str(item.get("umdNm", "")),
                "deal_year": str(item.get("dealYear", "")),
                "deal_month": str(item.get("dealMonth", "")),
                "area": area,
            })

        return {"total_count": total_count, "items": parsed}

    async def get_rent_trend(self, sgg_cd: str, months: int = 12) -> list:
        """최근 N개월 상업용 매매 실거래가 평균 추이 조회

        Note: API에 임대차(rental) 엔드포인트가 없으므로 매매 데이터로 추이를 계산.

        Args:
            sgg_cd: 시군구코드
            months: 조회할 개월 수 (기본 12)

        Returns:
            [{"year_month": "YYYYMM", "avg_deal_amount": int}, ...]
        """
        today = datetime.today().replace(day=1)
        trend = []

        for i in range(months - 1, -1, -1):
            # 현재 달로부터 i달 전 계산
            target = today - timedelta(days=i * 30)
            year_month = target.strftime("%Y%m")

            result = await self.get_commercial_trade(sgg_cd=sgg_cd, deal_ymd=year_month)
            items = result.get("items", [])

            if items:
                avg = int(sum(it["deal_amount"] for it in items) / len(items))
            else:
                avg = 0

            trend.append({"year_month": year_month, "avg_deal_amount": avg})

        return trend
