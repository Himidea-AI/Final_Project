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
from difflib import SequenceMatcher
from urllib.parse import unquote

import httpx
from lxml import etree
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential

# FTC 브랜드 업종 키워드 → 골목상권 업종 코드 매핑
INDUSTRY_KEYWORD_MAP: dict[str, str] = {
    # 한식 (CS100001)
    "한식": "CS100001",
    "국밥": "CS100001",
    "설렁탕": "CS100001",
    "갈비": "CS100001",
    "삼겹살": "CS100001",
    "냉면": "CS100001",
    "라면": "CS100001",
    "순대": "CS100001",
    "감자탕": "CS100001",
    "해장국": "CS100001",
    "육개장": "CS100001",
    "보쌈": "CS100001",
    "족발": "CS100001",
    "곱창": "CS100001",
    "숯불": "CS100001",
    "불고기": "CS100001",
    # 중식 (CS100002)
    "중식": "CS100002",
    "중국": "CS100002",
    "짜장": "CS100002",
    "짬뽕": "CS100002",
    # 일식 (CS100003)
    "일식": "CS100003",
    "초밥": "CS100003",
    "스시": "CS100003",
    "돈가스": "CS100003",
    "라멘": "CS100003",
    "우동": "CS100003",
    # 양식 (CS100004)
    "양식": "CS100004",
    "피자": "CS100004",
    "파스타": "CS100004",
    "스테이크": "CS100004",
    # 제과/베이커리 (CS100005)
    "제과": "CS100005",
    "베이커리": "CS100005",
    "빵": "CS100005",
    "도넛": "CS100005",
    "와플": "CS100005",
    # 패스트푸드 (CS100006)
    "패스트푸드": "CS100006",
    "햄버거": "CS100006",
    "버거": "CS100006",
    "샌드위치": "CS100006",
    # 치킨 (CS100007)
    "치킨": "CS100007",
    "닭강정": "CS100007",
    # 분식 (CS100008)
    "분식": "CS100008",
    "떡볶이": "CS100008",
    "김밥": "CS100008",
    "튀김": "CS100008",
    # 호프/주점 (CS100009)
    "호프": "CS100009",
    "주점": "CS100009",
    "맥주": "CS100009",
    "포차": "CS100009",
    # 카페/음료 (CS100010)
    "커피": "CS100010",
    "카페": "CS100010",
    "음료": "CS100010",
    "버블티": "CS100010",
    "쥬스": "CS100010",
    "주스": "CS100010",
    "smoothie": "CS100010",
    "스무디": "CS100010",
    "디저트": "CS100010",
    "아이스크림": "CS100010",
    "빙수": "CS100010",
}


def _fuzzy_match(query: str, brand: str, threshold: float = 0.65) -> bool:
    """
    브랜드명 퍼지 매칭 — 3단계 순서로 확인.

    1. 직접 포함: "메가커피" in "메가커피" → True
    2. 2글자 토큰 분리: "메가커피" → ["메가","커피"] 모두 포함 여부
       예) "메가MGC커피"에 "메가"와 "커피" 둘 다 있으면 매칭
    3. difflib 유사도: 0.65 이상이면 매칭

    Args:
        query: 사용자 입력 브랜드명
        brand: API 반환 브랜드명
        threshold: difflib 유사도 임계값 (기본 0.65)
    """
    q, b = query.lower(), brand.lower()

    if q in b:
        return True

    # 2글자 한글 토큰 분리 매칭
    tokens = [q[i : i + 2] for i in range(0, len(q) - 1, 2)]
    if len(tokens) >= 2 and all(t in b for t in tokens):
        return True

    return SequenceMatcher(None, q, b).ratio() >= threshold


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
                if _fuzzy_match(brand_name, b_name):
                    results.append(
                        {
                            "jng_ifrmp_sn": item.findtext("jngIfrmpSn") or "",
                            "brand_name": b_name,
                            "corp_name": item.findtext("corpNm") or "",
                            "registration_no": item.findtext("jngIfrmpRgsno") or "",
                            "viewer_url": item.findtext("viwerUrl") or "",
                            "year": target_yr,
                        }
                    )

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

    # ------------------------------------------------------------------
    # 브랜드 vs 업종 비교 분석
    # ------------------------------------------------------------------

    @staticmethod
    def match_industry_code(brand_name: str) -> str | None:
        """
        브랜드명에서 업종 키워드를 찾아 골목상권 업종 코드를 반환.

        Args:
            brand_name: FTC 브랜드명 (예: "메가MGC커피")

        Returns:
            str | None: 매칭된 업종 코드 (예: "CS100009"), 없으면 None
        """
        name_lower = brand_name.lower()
        for keyword, code in INDUSTRY_KEYWORD_MAP.items():
            if keyword in name_lower:
                return code
        return None

    async def compare_brand_to_district(
        self,
        brand_name: str,
        dong_name: str,
        session: AsyncSession,
        yr: str | None = None,
    ) -> dict:
        """
        브랜드 매출과 해당 행정동의 업종 평균 매출을 비교.

        FTC 정보공개서의 브랜드 연평균 매출(전국)과
        district_sales 테이블의 실제 분기별 업종 매출(로컬)을 나란히 제공.

        Args:
            brand_name: 브랜드명
            dong_name: 행정동명 (예: "망원동")
            session: SQLAlchemy AsyncSession
            yr: 정보공개서 연도 (None이면 자동 폴백)

        Returns:
            dict: 브랜드 정보 + 업종 분기별 매출 + 포지션 비교
        """
        from src.database.models import DistrictSales, StoreQuarterly

        # 1) FTC 브랜드 상세 조회
        brand_detail = await self.get_brand_detail(brand_name, yr=yr)
        if not brand_detail:
            return {"error": f"브랜드 '{brand_name}'을(를) 찾을 수 없습니다."}

        # 2) 업종 코드 매칭
        industry_code = self.match_industry_code(brand_detail["brand_name"])
        if not industry_code:
            return {
                **brand_detail,
                "error": "업종 코드를 매칭할 수 없습니다. 업종 키워드를 확인하세요.",
            }

        # 3) 해당 동의 업종 분기별 매출 + 점포 수 조회 (최근 4분기)
        stmt = (
            select(
                DistrictSales.quarter,
                DistrictSales.industry_name,
                DistrictSales.monthly_sales,
                DistrictSales.monthly_count,
                StoreQuarterly.store_count,
                StoreQuarterly.franchise_count,
            )
            .join(
                StoreQuarterly,
                (DistrictSales.quarter == StoreQuarterly.quarter)
                & (DistrictSales.dong_code == StoreQuarterly.dong_code)
                & (DistrictSales.industry_code == StoreQuarterly.industry_code),
            )
            .where(
                DistrictSales.dong_name == dong_name,
                DistrictSales.industry_code == industry_code,
            )
            .order_by(DistrictSales.quarter.desc())
            .limit(4)
        )
        result = await session.execute(stmt)
        rows = result.fetchall()

        if not rows:
            return {
                **brand_detail,
                "industry_code": industry_code,
                "error": f"'{dong_name}'에서 해당 업종의 매출 데이터를 찾을 수 없습니다.",
            }

        # 4) 분기별 점포당 매출 계산
        quarterly_sales = []
        for row in rows:
            per_store = row.monthly_sales // row.store_count if row.store_count > 0 else 0
            quarterly_sales.append(
                {
                    "quarter": row.quarter,
                    "monthly_sales": row.monthly_sales,
                    "monthly_count": row.monthly_count,
                    "store_count": row.store_count,
                    "franchise_count": row.franchise_count,
                    "per_store_monthly_sales": per_store,
                }
            )

        # 5) 점포당 월매출 평균 (최근 4분기)
        per_store_values = [q["per_store_monthly_sales"] for q in quarterly_sales if q["per_store_monthly_sales"] > 0]
        avg_per_store_monthly = int(sum(per_store_values) / len(per_store_values)) if per_store_values else 0

        # 6) 브랜드 월매출 (FTC 연매출 ÷ 12)
        brand_annual = brand_detail.get("avg_sales_amount", 0)
        brand_monthly = brand_annual // 12 if brand_annual else 0

        # 7) 포지션 비교 (브랜드 월매출 vs 점포당 월매출)
        if avg_per_store_monthly > 0 and brand_monthly > 0:
            position_ratio = round(brand_monthly / avg_per_store_monthly * 100, 1)
        else:
            position_ratio = 0.0

        return {
            "brand": {
                "name": brand_detail["brand_name"],
                "corp_name": brand_detail["corp_name"],
                "year": brand_detail["year"],
                "annual_avg_sales": brand_annual,
                "monthly_avg_sales": brand_monthly,
                "store_count": brand_detail.get("store_count_total", 0),
                "churn_rate": brand_detail.get("churn_rate", 0),
            },
            "district": {
                "dong_name": dong_name,
                "industry_code": industry_code,
                "industry_name": rows[0].industry_name,
                "avg_per_store_monthly_sales": avg_per_store_monthly,
                "quarterly_sales": quarterly_sales,
            },
            "comparison": {
                "position_ratio": position_ratio,
                "summary": (
                    f"{dong_name} {rows[0].industry_name} 점포당 월평균 매출은 "
                    f"{avg_per_store_monthly:,}원이며, {brand_detail['brand_name']}의 "
                    f"전국 가맹점 평균 월매출 {brand_monthly:,}원은 "
                    f"이 상권 대비 {position_ratio}% 수준입니다."
                ),
            },
        }
