"""FTC 가맹본부 공시 데이터 기반 브랜드 벤치마크.

출처: `ftc_brand_franchise` (공정위 가맹사업정보공개서, 연도별 집계).
단위: avrgSlsAmt, arUnitAvrgSlsAmt 는 **천원** 단위 → 원으로 변환해 반환.

FTC 미등재 브랜드(예: 스타벅스 - 직영체제)는 benchmark_available=False 로 응답.
"""

from __future__ import annotations

import logging
import os
from typing import TypedDict

from sqlalchemy import text

from src.database.sync_engine import get_sync_engine

logger = logging.getLogger(__name__)

DEFAULT_YEAR = 2024  # FTC 2024 공시 기준 (2025 데이터는 2026 하반기 발표 예정)

# Module-level fuzzy SQL — text() 객체 매 호출마다 재생성 회피.
_FUZZY_SQL = text(
    """
    SELECT "corpNm", "brandNm", "indutyLclasNm", "indutyMlsfcNm",
           "frcsCnt", "newFrcsRgsCnt", "ctrtEndCnt", "ctrtCncltnCnt", "nmChgCnt",
           "avrgSlsAmt", "arUnitAvrgSlsAmt"
      FROM ftc_brand_franchise
     WHERE "brandNm" ILIKE :pattern
       AND yr = :year
       AND ("frcsCnt" IS NULL OR "frcsCnt" > 0)
     ORDER BY "frcsCnt" DESC NULLS LAST
     LIMIT 1
    """
)


class BrandBenchmark(TypedDict, total=False):
    brand_name: str
    benchmark_available: bool
    reason: str
    reference_year: int
    # 아래 필드는 benchmark_available=True 일 때만 채움
    corp_name: str | None
    franchise_count_national: int | None
    avg_sales_per_store: int | None  # 원
    unit_area_sales: int | None  # 원/3.3㎡
    new_stores: int | None
    closed_contracts: int | None
    cancelled_contracts: int | None
    name_changes: int | None
    closure_rate: float | None
    growth_rate: float | None
    industry_large: str | None
    industry_medium: str | None


def _won_from_thousand(val: int | None) -> int | None:
    """천원 → 원. FTC avrgSlsAmt 단위 변환."""
    return int(val) * 1000 if val is not None else None


def get_brand_benchmark(brand_name: str, year: int = DEFAULT_YEAR) -> BrandBenchmark:
    """FTC 가맹본부 공시에서 브랜드 연간 실적 조회.

    매칭 우선순위:
    1. 정확 일치 (`brandNm = :brand`)
    2. 1차 실패 시 fuzzy 매칭 (예: '홍콩반점' → '홍콩반점0410') — ILIKE prefix + frcsCnt 큰 것 우선
    3. 매칭 row 의 frcsCnt = 0 이면 benchmark_available=False (closure_rate/growth_rate 계산 불가)

    FTC 미등재 (직영 브랜드 등) 시 benchmark_available=False.
    """
    engine = get_sync_engine(os.environ["POSTGRES_URL"])

    # 1차: 정확 일치 — 동일 (brandNm, yr) 다 row 시 silent tie-break 회피.
    # 복수 row 발견 시 첫 row 반환 + WARNING 로그 (FTC 원본 brand명 변경 중간 단계 등 데이터 품질 신호).
    exact_sql = text(
        """
        SELECT "corpNm", "brandNm", "indutyLclasNm", "indutyMlsfcNm",
               "frcsCnt", "newFrcsRgsCnt", "ctrtEndCnt", "ctrtCncltnCnt", "nmChgCnt",
               "avrgSlsAmt", "arUnitAvrgSlsAmt"
          FROM ftc_brand_franchise
         WHERE "brandNm" = :brand
           AND yr = :year
        """
    )
    with engine.connect() as conn:
        all_exact = conn.execute(exact_sql, {"brand": brand_name, "year": year}).mappings().all()
        if len(all_exact) > 1:
            logger.warning(
                "[brand_profile] FTC 동일 brandNm 복수 row 감지 brand=%s yr=%d count=%d corps=%s",
                brand_name,
                year,
                len(all_exact),
                [r["corpNm"] for r in all_exact],
            )
        row = all_exact[0] if all_exact else None

        # 2차: fuzzy prefix 매칭 — 정확 매칭 실패 시 접미 변형 흡수 (예: '홍콩반점' → '홍콩반점0410').
        # 위험 (false positive): '파리' → '파리바게뜨'/'파리크라상' 같은 별 brand 잘못 매칭 가능.
        # 가드: 길이 ≥ 4 (한글 4자 이상은 prefix 충돌 거의 없음) + frcsCnt > 0 우선.
        if row is None and brand_name and len(brand_name) >= 4:
            row = conn.execute(_FUZZY_SQL, {"pattern": f"{brand_name}%", "year": year}).mappings().first()

    if not row:
        return {
            "brand_name": brand_name,
            "benchmark_available": False,
            "reason": "FTC 가맹사업 공시 미등재 (직영 체제 또는 해당 연도 데이터 없음)",
            "reference_year": year,
        }

    frcs = row["frcsCnt"] or 0

    # frcsCnt = 0 (paper brand) → 계산 불가 명시. None * 100 등 다운스트림 폭발 방지.
    if frcs == 0:
        return {
            "brand_name": row["brandNm"],
            "benchmark_available": False,
            "reason": f"FTC 등재됐으나 가맹점 0 (paper brand). corp={row['corpNm']!s}, yr={year}. 통계 계산 불가.",
            "reference_year": year,
            "corp_name": row["corpNm"],
            "franchise_count_national": 0,
            "industry_large": row["indutyLclasNm"],
            "industry_medium": row["indutyMlsfcNm"],
        }

    closure_rate = (row["ctrtEndCnt"] or 0) / frcs
    growth_rate = (row["newFrcsRgsCnt"] or 0) / frcs

    return {
        "brand_name": row["brandNm"],
        "benchmark_available": True,
        "reference_year": year,
        "corp_name": row["corpNm"],
        "franchise_count_national": frcs,
        "avg_sales_per_store": _won_from_thousand(row["avrgSlsAmt"]),
        "unit_area_sales": _won_from_thousand(row["arUnitAvrgSlsAmt"]),
        "new_stores": row["newFrcsRgsCnt"],
        "closed_contracts": row["ctrtEndCnt"],
        "cancelled_contracts": row["ctrtCncltnCnt"],
        "name_changes": row["nmChgCnt"],
        "closure_rate": round(closure_rate, 4),
        "growth_rate": round(growth_rate, 4),
        "industry_large": row["indutyLclasNm"],
        "industry_medium": row["indutyMlsfcNm"],
    }


def get_industry_peer_brands(
    industry_medium: str,
    year: int = DEFAULT_YEAR,
    top_n: int = 5,
) -> list[dict]:
    """동일 중분류 업종의 경쟁 브랜드 top N (가맹점 수 기준).

    Args:
        industry_medium: `indutyMlsfcNm` 값 (예: "커피", "치킨", "패스트푸드").
        top_n: 반환 개수.

    Returns:
        [{brand_name, franchise_count, avg_sales(원), closure_rate}, ...]
    """
    sql = text(
        """
        SELECT "brandNm", "frcsCnt", "avrgSlsAmt", "ctrtEndCnt"
          FROM ftc_brand_franchise
         WHERE "indutyMlsfcNm" = :ind
           AND yr = :year
         ORDER BY "frcsCnt" DESC NULLS LAST
         LIMIT :n
        """
    )
    engine = get_sync_engine(os.environ["POSTGRES_URL"])
    with engine.connect() as conn:
        rows = conn.execute(sql, {"ind": industry_medium, "year": year, "n": top_n}).mappings().all()

    peers: list[dict] = []
    for r in rows:
        frcs = r["frcsCnt"] or 0
        peers.append(
            {
                "brand_name": r["brandNm"],
                "franchise_count": frcs,
                "avg_sales": _won_from_thousand(r["avrgSlsAmt"]),
                "closure_rate": round((r["ctrtEndCnt"] or 0) / frcs, 4) if frcs else None,
            }
        )
    return peers
