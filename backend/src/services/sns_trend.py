"""
Naver DataLab 트렌드 API — 키워드 검색량 추이 기반 상권 트렌드 분석

Instagram/블로그 크롤링 대신 Naver DataLab API를 사용.
"망원동 카페", "연남동 맛집" 등 키워드 검색량 추이를 조회하여 힙지수 산출.
Naver Developers에서 무료 API 키 발급 가능.
"""
from src.services.base_client import BaseAPIClient


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
        # TODO: POST /search 엔드포인트 호출
        # TODO: keywordGroups 파라미터 구성
        # TODO: 응답에서 period별 ratio 추출
        pass

    async def get_district_trend(self, district: str, business_type: str) -> dict:
        """
        행정동+업종 키워드 트렌드 조회

        Args:
            district: 행정동명 (예: "망원동")
            business_type: 업종 키워드 (예: "카페")

        Returns:
            dict: 최근 12개월 검색량 추이, 전월 대비 증감률
        """
        # TODO: "{동명} {업종}" 형태로 키워드 구성
        # TODO: 최근 12개월 데이터 조회
        # TODO: 전월 대비 증감률 계산
        pass

    async def calculate_hipness_score(self, district: str) -> float:
        """
        힙지수 계산 — 검색량 트렌드 기반

        Args:
            district: 행정동명

        Returns:
            float: 0~100 힙지수 (검색량 증가율 + 절대량 종합)
        """
        # TODO: 복수 키워드 트렌드 조회 (맛집, 카페, 핫플 등)
        # TODO: 검색량 절대 수준 + 증감률 가중 합산
        # TODO: 0~100 점수 정규화
        pass
