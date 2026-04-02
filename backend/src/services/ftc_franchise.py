"""
공정위 가맹사업 정보공개서 — 목록 API + XML 파싱

주의: API는 정보공개서 "목록 조회"만 제공.
브랜드별 매출, 가맹점 수 등 상세 데이터는 XML 파일을 별도로 다운받아 파싱해야 함.
"""
from lxml import etree

from src.services.base_client import BaseAPIClient


class FtcFranchiseClient(BaseAPIClient):
    """공정위 가맹사업 정보공개서 API + XML 파서"""

    def __init__(self, api_key: str):
        super().__init__(base_url="https://apis.data.go.kr/1130000", api_key=api_key)

    async def search_brand_list(self, brand_name: str) -> list[dict]:
        """
        정보공개서 목록 검색 (API)

        API는 목록 조회만 지원. 상세 데이터는 XML 파일 다운로드 필요.

        Args:
            brand_name: 브랜드명 (검색어)

        Returns:
            list[dict]: 브랜드 목록 (브랜드명, 정보공개서 등록번호, XML 다운로드 URL)
        """
        # TODO: 정보공개서 목록 API 호출
        # TODO: 브랜드명으로 필터링
        # TODO: 등록번호 + XML URL 추출
        pass

    async def download_disclosure_xml(self, registration_id: str) -> str:
        """
        정보공개서 XML 파일 다운로드

        Args:
            registration_id: 정보공개서 등록번호

        Returns:
            str: XML 문자열
        """
        # TODO: 등록번호로 XML 파일 다운로드 URL 구성
        # TODO: XML 파일 다운로드
        pass

    def parse_disclosure_xml(self, xml_content: str) -> dict:
        """
        정보공개서 XML 파싱 — 상세 데이터 추출

        XML에서 추출하는 데이터:
        - 가맹점 평균 매출액
        - 가맹점 수 (신규/해지/양도/폐점)
        - 영업지역 설정 기준
        - 가맹금 내역
        - 광고/판촉 분담금

        Args:
            xml_content: 다운로드한 XML 문자열

        Returns:
            dict: 파싱된 상세 데이터
        """
        # TODO: etree.fromstring()으로 XML 파싱
        # TODO: 가맹점 매출 정보 추출
        # TODO: 가맹점 수 현황 (신규 개점, 계약 해지, 계약 양도, 폐점)
        # TODO: 영업지역 설정 관련 정보 추출
        pass

    async def get_brand_detail(self, brand_name: str) -> dict:
        """
        브랜드 상세 정보 조회 — 목록 API + XML 파싱 통합

        Args:
            brand_name: 브랜드명

        Returns:
            dict: 종합 브랜드 정보 (매출, 가맹점 수, 해지율, 영업지역)
        """
        # TODO: search_brand_list()로 등록번호 조회
        # TODO: download_disclosure_xml()로 XML 다운로드
        # TODO: parse_disclosure_xml()로 상세 데이터 파싱
        # TODO: 결과 종합
        pass

    async def get_franchise_stores(self, brand_name: str, region: str = "마포구") -> dict:
        """
        가맹점 현황 조회 — 특정 지역 내 기존 가맹점

        Args:
            brand_name: 브랜드명
            region: 지역명

        Returns:
            dict: 지역 내 가맹점 목록, 점포 수
        """
        # TODO: XML 데이터에서 지역별 가맹점 필터링
        pass
