"""슈퍼어드민 전용 brand picker.

엔드포인트:
- GET /admin/brands — 시뮬 가능 업종 (CS100001~CS100010) 의 brand 통합 목록.
  소스: ftc_brand_franchise + biz_brand_mapping (회원가입 본부 매핑) UNION.
  검색: brand_name ILIKE :q OR corp_name ILIKE :q.
  필터: industry (canonical key, 예: "한식")
  페이징: page (1+), size (1~200, 기본 50)

권한: role == "superadmin" 만 허용. 다른 역할은 403.

응답:
{
  "total": int,
  "page": int,
  "size": int,
  "supported_industries": list[{key, label, cs_code}],   # 시뮬 가능 업종 10종
  "items": list[BrandItem]
}
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import text

from src.config.business_type_mapping import BUSINESS_TYPE_MAPPING
from src.database.sync_engine import get_sync_engine
from src.services.jwt_auth import UserContext, get_current_user

router = APIRouter(prefix="/admin", tags=["admin-brands"])


def _db_url() -> str:
    from src.config.settings import settings

    return settings.postgres_url


def require_superadmin(user: UserContext = Depends(get_current_user)) -> UserContext:
    """role == 'superadmin' 강제. master/manager 모두 403."""
    if user.role != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="superadmin 전용 엔드포인트입니다.",
        )
    return user


class BrandItem(BaseModel):
    brand_name: str
    corp_name: Optional[str] = None
    biz_number: Optional[str] = None
    business_type: str  # canonical key (예: "한식")
    cs_code: str  # CS100001 ~ CS100010
    industry_medium: Optional[str] = None  # FTC 원본 indutyMlsfcNm
    franchise_count: Optional[int] = None
    avg_sales: Optional[int] = None
    source: str  # "ftc" | "biz_brand_mapping"


def _industry_match_clause(industry_key: str | None) -> tuple[str, dict[str, Any]]:
    """canonical key (예: '한식') → ftc_brand_franchise.indutyMlsfcNm ILIKE 절.

    None 이면 모든 시뮬 가능 업종 (10종 ftc_keywords 합집합).
    """
    if industry_key:
        entry = BUSINESS_TYPE_MAPPING.get(industry_key)
        if not entry:
            raise HTTPException(
                status_code=400,
                detail=f"지원하지 않는 업종 key: {industry_key}",
            )
        keywords = entry["ftc_keywords"]
    else:
        keywords = []
        for entry in BUSINESS_TYPE_MAPPING.values():
            keywords.extend(entry["ftc_keywords"])

    placeholders = []
    params: dict[str, Any] = {}
    for i, kw in enumerate(keywords):
        ph = f"ftc_kw_{i}"
        placeholders.append(f"COALESCE(\"indutyMlsfcNm\", '') ILIKE :{ph}")
        params[ph] = f"%{kw}%"
    return "(" + " OR ".join(placeholders) + ")", params


def _resolve_business_type(industry_medium: str | None) -> tuple[str, str] | None:
    """FTC indutyMlsfcNm → canonical key + cs_code 매핑.

    여러 업종 키워드가 같은 indutyMlsfcNm 에 매칭될 수 있으므로
    가장 먼저 매칭되는 entry 를 사용.
    """
    if not industry_medium:
        return None
    haystack = industry_medium.lower()
    for key, entry in BUSINESS_TYPE_MAPPING.items():
        for kw in entry["ftc_keywords"]:
            if kw.lower() in haystack:
                return key, entry["cs_code"]
    return None


@router.get("/brands")
def list_admin_brands(
    q: Optional[str] = Query(default=None, description="brand_name 또는 corp_name 부분 일치"),
    industry: Optional[str] = Query(
        default=None,
        description="canonical 업종 key (예: 한식, 커피). 미지정 시 시뮬 가능 10종 전체",
    ),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    _user: UserContext = Depends(require_superadmin),
) -> dict[str, Any]:
    """시뮬 가능 업종의 brand 통합 목록 (FTC + biz_brand_mapping)."""

    industry_clause, industry_params = _industry_match_clause(industry)

    where_search = ""
    search_params: dict[str, Any] = {}
    if q and q.strip():
        where_search = " AND (b.brand_name ILIKE :q_pat OR COALESCE(b.corp_name, '') ILIKE :q_pat)"
        search_params["q_pat"] = f"%{q.strip()}%"

    # FTC + biz_brand_mapping UNION:
    # - ftc_brand_franchise: 정보공개서 16K+ brand 본문
    # - biz_brand_mapping: 회원가입 본부의 가맹본부 매핑 (SPOTTER 사용 본부)
    # 같은 brand_name 이 양쪽에 있을 수 있어 MAX/COALESCE 로 우선순위:
    # franchise_count·avg_sales 는 ftc 우선, biz_number 는 biz_brand_mapping 만 보유
    base_sql = f"""
        WITH ftc AS (
            SELECT
                "brandNm" AS brand_name,
                "corpNm" AS corp_name,
                NULL::text AS biz_number,
                "indutyMlsfcNm" AS industry_medium,
                "frcsCnt" AS franchise_count,
                "avrgSlsAmt" AS avg_sales,
                'ftc' AS source
            FROM ftc_brand_franchise
            WHERE {industry_clause}
              AND "brandNm" IS NOT NULL
        ),
        biz AS (
            SELECT
                brand_name,
                company_name AS corp_name,
                biz_number,
                industry_medium,
                franchise_count,
                avg_sales,
                'biz_brand_mapping' AS source
            FROM biz_brand_mapping
            WHERE brand_name IS NOT NULL
        ),
        combined AS (
            SELECT * FROM ftc
            UNION ALL
            SELECT * FROM biz
        ),
        deduped AS (
            SELECT DISTINCT ON (brand_name, COALESCE(corp_name, ''))
                brand_name, corp_name, biz_number, industry_medium,
                franchise_count, avg_sales, source
            FROM combined
            ORDER BY brand_name, COALESCE(corp_name, ''),
                     CASE WHEN source = 'biz_brand_mapping' THEN 0 ELSE 1 END,
                     franchise_count DESC NULLS LAST
        )
        SELECT * FROM deduped b
        WHERE 1=1{where_search}
    """

    params: dict[str, Any] = {**industry_params, **search_params}
    offset = (page - 1) * size

    engine = get_sync_engine(_db_url())
    with engine.connect() as conn:
        total = conn.execute(
            text(f"SELECT COUNT(*) FROM ({base_sql}) t"),
            params,
        ).scalar_one()

        rows = conn.execute(
            text(
                f"""
                {base_sql}
                ORDER BY franchise_count DESC NULLS LAST, brand_name
                LIMIT :limit OFFSET :offset
                """
            ),
            {**params, "limit": size, "offset": offset},
        ).fetchall()

    items: list[dict[str, Any]] = []
    for r in rows:
        m = dict(r._mapping)
        bt = _resolve_business_type(m.get("industry_medium"))
        # industry_medium 이 시뮬 가능 10종에 매핑 안 되면 skip — UNION 이후에도 잡종 brand 가 들어올 수 있음
        if bt is None:
            continue
        bt_key, cs_code = bt
        items.append(
            {
                "brand_name": m["brand_name"],
                "corp_name": m.get("corp_name"),
                "biz_number": m.get("biz_number"),
                "business_type": bt_key,
                "cs_code": cs_code,
                "industry_medium": m.get("industry_medium"),
                "franchise_count": m.get("franchise_count"),
                "avg_sales": m.get("avg_sales"),
                "source": m["source"],
            }
        )

    supported = [{"key": k, "label": v["label_kr"], "cs_code": v["cs_code"]} for k, v in BUSINESS_TYPE_MAPPING.items()]

    return {
        "total": int(total or 0),
        "page": page,
        "size": size,
        "supported_industries": supported,
        "items": items,
    }


@router.get("/brands/industries")
def list_supported_industries(
    _user: UserContext = Depends(require_superadmin),
) -> dict[str, Any]:
    """시뮬 가능 업종 메타정보만 가볍게 반환 (drop-down 초기 로딩)."""
    return {
        "industries": [
            {
                "key": k,
                "label": v["label_kr"],
                "cs_code": v["cs_code"],
                "kakao_category": v["kakao_category"],
            }
            for k, v in BUSINESS_TYPE_MAPPING.items()
        ]
    }
