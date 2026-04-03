"""
공정위 가맹사업 정보공개서 API (franchise.ftc.go.kr)

엔드포인트 구조:
  - 목록조회: GET /api/search.do?type=list&yr=YYYY&serviceKey=...
  - 목차조회: GET /api/search.do?type=title&jngIfrmpSn=...&serviceKey=...
  - 본문조회: GET /api/search.do?type=content&jngIfrmpSn=...&serviceKey=...

주의:
  - 모든 요청에 브라우저 헤더(User-Agent, Referer) 필수 — 없으면 406 반환
  - serviceKey는 URL 인코딩된 채로 쿼리스트링에 직접 포함 (httpx params 미사용)
  - 본문 XML 내부에 HTML이 중첩된 복잡한 구조 — 정규식으로 수치 추출
"""
import re
from urllib.parse import unquote

import httpx
from lxml import etree
from tenacity import retry, stop_after_attempt, wait_exponential

BASE_URL = "https://franchise.ftc.go.kr"
# 서버가 브라우저가 아닌 요청을 차단(406)하므로 필수
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://franchise.ftc.go.kr/",
    "Accept": "application/xml, text/xml, */*",
}


class FtcFranchiseClient:
    """공정위 가맹사업 정보공개서 API 클라이언트"""

    def __init__(self, api_key: str):
        # 환경변수에 URL 인코딩된 키가 들어올 수 있으므로 디코딩
        self._api_key = unquote(api_key)
        self._timeout = 15

    def _build_url(self, params: dict) -> str:
        """serviceKey를 포함한 URL 직접 조립 — httpx params 사용 시 이중 인코딩 발생"""
        query = "&".join(f"{k}={v}" for k, v in params.items())
        # serviceKey는 마지막에 원본 형태로 추가
        return f"{BASE_URL}/api/search.do?{query}&serviceKey={self._api_key}"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def _get(self, url: str) -> bytes:
        """브라우저 헤더를 포함한 GET 요청"""
        async with httpx.AsyncClient(timeout=self._timeout, headers=_BROWSER_HEADERS) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content

    async def search_brand_list(self, brand_name: str, yr: str | None = None) -> list[dict]:
        """
        브랜드 목록 조회 — 연도별 전체 목록에서 brand_name으로 필터링

        Args:
            brand_name: 브랜드명 (부분 일치, 빈 문자열이면 전체 반환)
            yr: 정보공개서 연도. None이면 최신 연도부터 순서대로 폴백 검색

        Returns:
            list[dict]: 매칭된 브랜드 목록
                - jng_ifrmp_sn: 정보공개서 일련번호 (상세 조회 시 사용)
                - brand_name: 브랜드명
                - corp_name: 가맹본부 법인명
                - registration_no: 정보공개서 등록번호
                - viewer_url: 공개본 뷰어 URL
                - year: 조회 연도
        """
        # yr 미지정 시 최신 연도부터 순차 폴백
        years = [yr] if yr else ["2024", "2023", "2022"]

        for target_yr in years:
            url = self._build_url({"type": "list", "yr": target_yr})
            content = await self._get(url)
            root = etree.fromstring(content)

            results = []
            for item in root.findall(".//item"):
                b_name = item.findtext("brandNm") or ""
                if brand_name.lower() in b_name.lower():
                    results.append({
                        "jng_ifrmp_sn": item.findtext("jngIfrmpSn") or "",
                        "brand_name": b_name,
                        "corp_name": item.findtext("corpNm") or "",
                        "registration_no": item.findtext("jngIfrmpRgsno") or "",
                        "viewer_url": item.findtext("viwerUrl") or "",
                        "year": target_yr,
                    })

            if results:
                return results

        return []

    async def get_table_of_contents(self, jng_ifrmp_sn: str) -> list[dict]:
        """
        정보공개서 목차 조회

        Args:
            jng_ifrmp_sn: 정보공개서 일련번호

        Returns:
            list[dict]: 목차 항목 (attrb_mnno, level, title)
        """
        url = self._build_url({"type": "title", "jngIfrmpSn": jng_ifrmp_sn})
        content = await self._get(url)
        root = etree.fromstring(content)

        return [
            {
                "attrb_mnno": toc.get("attrbMnno", ""),
                "level": toc.get("level", ""),
                "title": toc.findtext("title") or "",
            }
            for toc in root.findall(".//tocObj")
        ]

    async def get_content_xml(self, jng_ifrmp_sn: str) -> str:
        """
        정보공개서 본문 XML 원문 조회

        Args:
            jng_ifrmp_sn: 정보공개서 일련번호

        Returns:
            str: 본문 XML 문자열
        """
        url = self._build_url({"type": "content", "jngIfrmpSn": jng_ifrmp_sn})
        content = await self._get(url)
        return content.decode("utf-8")

    def parse_content_xml(self, xml_content: str) -> dict:
        """
        정보공개서 본문 XML 파싱 — 핵심 수치 추출

        본문 XML은 HTML이 중첩된 복잡한 구조로,
        정규식으로 주요 수치를 추출합니다.

        Args:
            xml_content: get_content_xml() 반환값

        Returns:
            dict: 추출된 핵심 데이터
        """
        def _find_number(pattern: str) -> int:
            """패턴 뒤에 오는 숫자 추출"""
            match = re.search(pattern + r"[^0-9]*([0-9,]+)", xml_content)
            if match:
                return int(match.group(1).replace(",", ""))
            return 0

        def _find_text(pattern: str, length: int = 100) -> str:
            """패턴 뒤 텍스트 추출"""
            match = re.search(pattern + r"(.{1," + str(length) + r"})", xml_content)
            return match.group(1).strip() if match else ""

        return {
            # 가맹점 수 현황
            "store_count_total": _find_number(r"가맹점\s*수"),
            "store_count_new": _find_number(r"신규\s*개점"),
            "store_count_close": _find_number(r"폐\s*점"),
            "store_count_terminate": _find_number(r"계약\s*해지"),

            # 매출 정보
            "avg_sales_amount": _find_number(r"평균\s*매출액"),

            # 가맹금
            "franchise_fee": _find_number(r"가입\s*비"),
            "education_fee": _find_number(r"교육\s*비"),
            "deposit": _find_number(r"보\s*증\s*금"),

            # 영업지역
            "territory_condition": _find_text(r"영업지역"),
        }

    async def get_brand_detail(self, brand_name: str, yr: str | None = None) -> dict:
        """
        브랜드 상세 정보 통합 조회 — 목록 검색 + 본문 파싱

        Args:
            brand_name: 브랜드명
            yr: 정보공개서 연도. None이면 자동 폴백

        Returns:
            dict: 브랜드 기본정보 + 파싱된 상세 수치
        """
        brand_list = await self.search_brand_list(brand_name, yr=yr)
        if not brand_list:
            return {}

        brand = brand_list[0]
        xml_content = await self.get_content_xml(brand["jng_ifrmp_sn"])
        detail = self.parse_content_xml(xml_content)

        total = detail["store_count_total"]
        churn = detail["store_count_terminate"] + detail["store_count_close"]
        churn_rate = round(churn / total, 4) if total > 0 else 0.0

        return {
            **brand,
            **detail,
            "churn_rate": churn_rate,
        }

    async def get_franchise_stores(self, brand_name: str, region: str = "마포구") -> dict:
        """
        브랜드의 가맹점 현황 조회 — 정보공개서 본문에서 지역 필터링

        Args:
            brand_name: 브랜드명
            region: 지역명 (기본값: 마포구)

        Returns:
            dict: 브랜드명, 지역, 가맹점 수, 뷰어 URL
        """
        brand_list = await self.search_brand_list(brand_name)
        if not brand_list:
            return {"brand_name": brand_name, "region": region, "store_count": 0, "stores": []}

        brand = brand_list[0]
        xml_content = await self.get_content_xml(brand["jng_ifrmp_sn"])

        # 본문에서 지역명 주변 텍스트로 점포 수 추정
        region_count = len(re.findall(re.escape(region), xml_content))

        return {
            "brand_name": brand["brand_name"],
            "corp_name": brand["corp_name"],
            "region": region,
            "region_mentions": region_count,  # 지역 언급 횟수 (점포 수 근사치)
            "viewer_url": brand["viewer_url"],
            "year": brand["year"],
        }
