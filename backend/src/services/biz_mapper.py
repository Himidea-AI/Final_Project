"""
사업자등록번호 → 프랜차이즈 브랜드 매핑 서비스

1. 국세청 API → 사업자등록번호 유효성 검증
2. ftc_brand_franchise 테이블 → 기업명으로 브랜드 검색 (DB 조회, API 호출 없음)
3. store_info 테이블 → 마포구 내 해당 브랜드 점포 수 카운트
"""

import os
from difflib import SequenceMatcher

import httpx
from sqlalchemy import create_engine, text
from tenacity import retry, stop_after_attempt, wait_exponential

# DB 접속 — 환경변수 우선, 없으면 docker-compose 기본값
_pw = os.environ.get("POSTGRES_PASSWORD", "postgres")

try:
    import psycopg  # noqa: F401

    _driver = "postgresql+psycopg"
except ImportError:
    _driver = "postgresql"

DB_URL = os.environ.get(
    "POSTGRES_URL",
    f"{_driver}://postgres:{_pw}@localhost:5432/mapo_simulator",
)


class BizMapper:
    """사업자등록번호 기반 프랜차이즈 매핑 클라이언트"""

    def __init__(
        self,
        nts_api_key: str | None = None,
        db_url: str | None = None,
    ):
        self._nts_key = nts_api_key or os.environ.get("NTS_API_KEY", "")
        self._db_url = db_url or DB_URL
        self._timeout = 15

    # ------------------------------------------------------------------
    # 1. 국세청 사업자등록 상태 조회
    # ------------------------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def verify_biz_number(self, biz_number: str) -> dict:
        """
        사업자등록번호 유효성 검증.

        Returns:
            dict: status(상태), tax_type(과세유형), valid(유효 여부)
        """
        clean = biz_number.replace("-", "")
        url = f"https://api.odcloud.kr/api/nts-businessman/v1/status?serviceKey={self._nts_key}"

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json={"b_no": [clean]})
            resp.raise_for_status()

        data = resp.json().get("data", [{}])[0]
        b_stt = data.get("b_stt", "")
        tax_type = data.get("tax_type", "")

        valid = "계속사업자" in b_stt
        return {
            "biz_number": biz_number,
            "status": b_stt,
            "tax_type": tax_type,
            "valid": valid,
        }

    # ------------------------------------------------------------------
    # 2. ftc_brand_franchise 테이블 — 기업명으로 브랜드 검색
    # ------------------------------------------------------------------

    def search_brand_by_company(self, company_name: str) -> list[dict]:
        """
        기업명(법인명)으로 ftc_brand_franchise 테이블에서 브랜드를 검색.

        ILIKE로 DB에서 후보를 가져온 뒤, 점수 기반 정렬.
        2024년 데이터 우선, 없으면 2023년.
        """
        engine = create_engine(self._db_url, echo=False)
        try:
            with engine.connect() as conn:
                # 법인명 + 브랜드명 모두 ILIKE 검색
                rows = conn.execute(
                    text(
                        "SELECT * FROM ftc_brand_franchise "
                        "WHERE (corp_name ILIKE :pattern OR brand_name ILIKE :pattern) "
                        "AND year = '2024' "
                        "ORDER BY franchise_count DESC "
                        "LIMIT 20"
                    ),
                    {"pattern": f"%{company_name}%"},
                ).fetchall()

                # 2024 결과 없으면 2023
                if not rows:
                    rows = conn.execute(
                        text(
                            "SELECT * FROM ftc_brand_franchise "
                            "WHERE (corp_name ILIKE :pattern OR brand_name ILIKE :pattern) "
                            "AND year = '2023' "
                            "ORDER BY franchise_count DESC "
                            "LIMIT 20"
                        ),
                        {"pattern": f"%{company_name}%"},
                    ).fetchall()
        finally:
            engine.dispose()

        if not rows:
            return []

        # 점수 기반 정렬
        query = company_name.lower().strip()
        scored = []
        for row in rows:
            row_dict = dict(row._mapping)
            corp = (row_dict.get("corp_name") or "").lower()
            brand = (row_dict.get("brand_name") or "").lower()
            score = self._match_score(query, corp, brand)
            if score > 0:
                scored.append((score, row_dict))

        scored.sort(key=lambda x: (-x[0], -x[1].get("franchise_count", 0)))
        return [item for _, item in scored]

    @staticmethod
    def _match_score(query: str, corp: str, brand: str) -> float:
        """매칭 점수 반환. 0이면 불일치."""
        q = query.replace("(주)", "").replace("(유)", "").replace("㈜", "").strip().lower()
        c = corp.replace("(주)", "").replace("(유)", "").replace("㈜", "").strip().lower()
        b = brand.lower()

        # 법인명 완전 일치
        if q and c and q == c:
            return 1.0
        # 법인명 완전 포함 (3글자 이상)
        if q and c and len(q) >= 3 and (q in c or c in q):
            return 0.95
        # 법인명 유사도
        corp_ratio = SequenceMatcher(None, q, c).ratio() if q and c else 0
        if corp_ratio >= 0.75:
            return 0.8 + corp_ratio * 0.2

        # 브랜드명 완전 일치
        if q and b and q == b:
            return 0.9
        # 브랜드명 완전 포함 (3글자 이상)
        if q and b and len(q) >= 3 and (q in b or b in q):
            return 0.85
        # 브랜드명 유사도
        brand_ratio = SequenceMatcher(None, q, b).ratio() if q and b else 0
        if brand_ratio >= 0.75:
            return 0.5 + brand_ratio * 0.2

        return 0

    # ------------------------------------------------------------------
    # 3. store_info — 마포구 내 브랜드 점포 수
    # ------------------------------------------------------------------

    def count_mapo_stores(self, brand_name: str) -> int:
        """store_info 테이블에서 브랜드명과 매칭되는 마포구 점포 수 카운트."""
        engine = create_engine(self._db_url, echo=False)
        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text(
                        "SELECT COUNT(*) FROM store_info "
                        "WHERE store_name ILIKE :pattern"
                    ),
                    {"pattern": f"%{brand_name}%"},
                )
                return result.scalar() or 0
        finally:
            engine.dispose()

    # ------------------------------------------------------------------
    # 통합 매핑
    # ------------------------------------------------------------------

    async def map_franchise(self, biz_number: str, company_name: str) -> dict:
        """
        사업자등록번호 + 기업명으로 프랜차이즈 정보를 매핑.

        Returns:
            dict: 검증 결과 + 브랜드 정보 + 마포구 점포 수
        """
        # 1. 사업자번호 검증
        verification = await self.verify_biz_number(biz_number)

        # 2. DB에서 브랜드 검색
        brands = self.search_brand_by_company(company_name)

        # 3. 각 브랜드의 마포구 점포 수 카운트
        for brand in brands:
            brand["mapo_store_count"] = self.count_mapo_stores(brand["brand_name"])

        return {
            "verification": verification,
            "brands": brands,
            "matched_count": len(brands),
        }
