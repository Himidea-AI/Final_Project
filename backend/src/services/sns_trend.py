"""
Naver DataLab 트렌드 API — 키워드 검색량 추이 기반 상권 트렌드 분석

Instagram/블로그 크롤링 대신 Naver DataLab API를 사용.
"망원동 카페", "연남동 맛집" 등 키워드 검색량 추이를 조회하여 힙지수 산출.
Naver Developers에서 무료 API 키 발급 가능.
"""

from datetime import date, timedelta

import httpx

from .base_client import BaseAPIClient


class NaverTrendClient(BaseAPIClient):
    """Naver DataLab 트렌드 API 클라이언트"""

    def __init__(self, client_id: str, client_secret: str):
        super().__init__(base_url="https://openapi.naver.com/v1/datalab")
        self.client_id = client_id
        self.client_secret = client_secret

    def _get_headers(self) -> dict:
        """Naver API 인증 헤더"""
        return {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
            "Content-Type": "application/json",
        }

    async def get_search_trend(
        self,
        keywords: list[str],
        start_date: str,
        end_date: str,
        time_unit: str = "month",
    ) -> dict:
        """
        키워드 검색량 추이 조회

        Args:
            keywords: 검색 키워드 리스트 (예: ["망원동 카페", "연남동 맛집"])
            start_date: 시작일 (YYYY-MM-DD)
            end_date: 종료일 (YYYY-MM-DD)
            time_unit: 집계 단위 (date/week/month)

        Returns:
            dict: 기간별 상대 검색량 (0~100)
        """
        url = f"{self.base_url}/search"
        body = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": time_unit,
            "keywordGroups": [{"groupName": kw, "keywords": [kw]} for kw in keywords],
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=body, headers=self._get_headers())
            response.raise_for_status()
            return response.json()

    async def get_district_trend(self, district: str, business_type: str) -> dict:
        """
        행정동+업종 키워드 트렌드 조회

        Args:
            district: 행정동명 (예: "망원동")
            business_type: 업종 키워드 (예: "카페")

        Returns:
            dict: 최근 12개월 검색량 추이, 전월 대비 증감률
        """
        keyword = f"{district} {business_type}"

        end = date.today()
        start = end - timedelta(days=365)
        start_date = start.strftime("%Y-%m-%d")
        end_date = end.strftime("%Y-%m-%d")

        response = await self.get_search_trend(
            keywords=[keyword],
            start_date=start_date,
            end_date=end_date,
            time_unit="month",
        )

        trend_data = []
        if response.get("results"):
            trend_data = response["results"][0].get("data", [])

        growth_rate = 0.0
        if len(trend_data) >= 2:
            last_ratio = trend_data[-1]["ratio"]
            prev_ratio = trend_data[-2]["ratio"]
            if prev_ratio != 0:
                growth_rate = (last_ratio - prev_ratio) / prev_ratio * 100

        return {
            "keyword": keyword,
            "trend_data": trend_data,
            "growth_rate": round(growth_rate, 2),
        }

    async def calculate_hipness_score(self, district: str) -> float:
        """
        힙지수 계산 — 검색량 트렌드 기반

        Args:
            district: 행정동명

        Returns:
            float: 0~100 힙지수 (검색량 증가율 + 절대량 종합)
        """
        base_keywords = ["맛집", "카페", "핫플", "데이트"]
        keywords = [f"{district} {kw}" for kw in base_keywords]

        end = date.today()
        start = end - timedelta(days=365)
        start_date = start.strftime("%Y-%m-%d")
        end_date = end.strftime("%Y-%m-%d")

        response = await self.get_search_trend(
            keywords=keywords,
            start_date=start_date,
            end_date=end_date,
            time_unit="month",
        )

        scores = []
        for result in response.get("results", []):
            data = result.get("data", [])
            if not data:
                continue

            latest_ratio = data[-1]["ratio"]

            growth = 0.0
            if len(data) >= 2:
                prev_ratio = data[-2]["ratio"]
                if prev_ratio != 0:
                    growth = (data[-1]["ratio"] - prev_ratio) / prev_ratio * 100

            clamped_growth = max(0.0, min(100.0, growth + 50))
            score = latest_ratio * 0.5 + clamped_growth * 0.5
            scores.append(score)

        if not scores:
            return 0.0

        return round(sum(scores) / len(scores), 2)
