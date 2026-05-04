"""사업자번호 + 업종 → 같은 corp 의 해당 업종 자동 brand 매핑.

다업종 법인 (예: (주)더본코리아 = 빽다방·홍콩반점·빽보이피자·새마을식당...) 의 경우
회원가입 시 ``biz_brand_mapping`` 에 top frcsCnt brand 1개만 저장됨.
시뮬레이션 시 사용자가 다른 업종 (예: 중식) 선택하면 같은 corp 의 해당 업종
가장 큰 brand (홍콩반점0410) 로 자동 resolve.

운영 외 업종 선택 시 ``INDUSTRY_NOT_OPERATED`` 에러 + 운영 가능 업종 list 반환.

설계:
- ``users.company_name`` (회원가입 시 기록) 기준 ``ftc_brand_franchise.corpNm`` 매칭
- corpNm 표기 변형 흡수 — ILIKE + corp 핵심어 추출 (괄호/특수문자 제거)
- 매칭 brand 중 ``frcsCnt`` 큰 것 1개 선택
- 운영 외 업종 → 거부 (사용자에게 운영 업종 list 안내)

사용처: ``main.py`` 시뮬 endpoint 호출 직후, 시뮬 input.brand_name override.
"""

from __future__ import annotations

import logging
import re

import sqlalchemy as sa

from src.config.settings import settings

logger = logging.getLogger(__name__)


_engine: sa.Engine | None = None


def _get_engine() -> sa.Engine:
    global _engine
    if _engine is None:
        _engine = sa.create_engine(settings.postgres_url)
    return _engine


# corpNm 핵심어 추출용 — '(주)', '㈜', '주식회사' 등 법인 prefix/suffix 제거
_CORP_NOISE_RE = re.compile(r"\(주\)|㈜|주식회사|\([^)]*\)|\s+")


def _normalize_corp(name: str) -> str:
    """corpNm 정규화 — 법인 표기 noise 제거 후 핵심어 추출."""
    if not name:
        return ""
    return _CORP_NOISE_RE.sub("", name).strip()


def get_corp_industries(biz_number: str) -> dict:
    """사업자번호 → corp 의 운영 brand+업종 list.

    Args:
        biz_number: 사업자등록번호 (하이픈 제거).

    Returns:
        ``{"company_name": ..., "brands": [...], "industries": [...]}`` 또는
        ``{"error": "USER_NOT_FOUND" | "CORP_NOT_IN_FTC", ...}``.
    """
    engine = _get_engine()
    with engine.connect() as c:
        user = c.execute(
            sa.text("SELECT company_name FROM users WHERE biz_number = :biz"),
            {"biz": biz_number},
        ).first()
        if not user:
            return {"error": "USER_NOT_FOUND", "biz_number": biz_number}

        company_name = user._mapping["company_name"]
        norm = _normalize_corp(company_name)
        if not norm:
            return {"error": "INVALID_COMPANY_NAME", "company_name": company_name}

        # ftc_brand_franchise 에서 corpNm 매칭 (정규화 ILIKE)
        # frcsCnt 큰 row 부터 정렬 — 같은 brand 의 다년 데이터는 max 사용
        rows = c.execute(
            sa.text(
                """
                SELECT "brandNm", "indutyMlsfcNm", MAX("frcsCnt") AS stores
                FROM ftc_brand_franchise
                WHERE "corpNm" IS NOT NULL
                  AND REGEXP_REPLACE("corpNm", '\\(주\\)|㈜|주식회사|\\([^)]*\\)|\\s+', '', 'g') ILIKE :norm
                GROUP BY "brandNm", "indutyMlsfcNm"
                ORDER BY stores DESC NULLS LAST
                """
            ),
            {"norm": f"%{norm}%"},
        ).fetchall()

    if not rows:
        return {
            "error": "CORP_NOT_IN_FTC",
            "company_name": company_name,
            "message": f"{company_name} 은(는) FTC 가맹사업 정보공개서에 등록되지 않은 corp 입니다.",
        }

    brands = [
        {"name": r._mapping["brandNm"], "industry": r._mapping["indutyMlsfcNm"], "stores": r._mapping["stores"] or 0}
        for r in rows
    ]
    industries = sorted({b["industry"] for b in brands if b["industry"]})

    return {
        "company_name": company_name,
        "brands": brands,
        "industries": industries,
    }


def resolve_brand_for_industry(biz_number: str, industry: str) -> dict:
    """사업자번호 + 업종 → 같은 corp 의 해당 업종 가장 큰 brand 자동 선택.

    Args:
        biz_number: 사업자등록번호.
        industry: 업종명 (FTC indutyMlsfcNm 표기 — 한식/중식/일식/...).

    Returns:
        성공: ``{"brand_name": ..., "industry": ..., "stores": int,
                 "alternatives": [...], "company_name": ...}``.
        실패: ``{"error": "INDUSTRY_NOT_OPERATED" | "USER_NOT_FOUND" | "CORP_NOT_IN_FTC",
                 "operated_industries": [...], ...}``.
    """
    portfolio = get_corp_industries(biz_number)
    if "error" in portfolio:
        return portfolio

    matched = [b for b in portfolio["brands"] if b["industry"] == industry]
    if not matched:
        return {
            "error": "INDUSTRY_NOT_OPERATED",
            "company_name": portfolio["company_name"],
            "requested_industry": industry,
            "operated_industries": portfolio["industries"],
            "message": (
                f"'{industry}' 업종은 {portfolio['company_name']} 운영 brand 에 없습니다. "
                f"운영 가능 업종: {', '.join(portfolio['industries'])}"
            ),
        }

    # frcsCnt 내림차순 정렬됨 (get_corp_industries 가 보장) — 첫 항목 = top brand
    top = matched[0]
    return {
        "brand_name": top["name"],
        "industry": top["industry"],
        "stores": top["stores"],
        "alternatives": [b["name"] for b in matched[1:]],
        "company_name": portfolio["company_name"],
    }
