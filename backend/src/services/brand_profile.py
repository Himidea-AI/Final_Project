"""FTC 가맹본부 공시 데이터 기반 브랜드 벤치마크.

출처: `ftc_brand_franchise` (공정위 가맹사업정보공개서, 연도별 집계).
단위: avrgSlsAmt, arUnitAvrgSlsAmt 는 **천원** 단위 → 원으로 변환해 반환.

FTC 미등재 브랜드(예: 스타벅스 - 직영체제)는 benchmark_available=False 로 응답.
"""

from __future__ import annotations

import os
from typing import TypedDict

from sqlalchemy import text

from src.database.sync_engine import get_sync_engine

DEFAULT_YEAR = 2024  # FTC 2024 공시 기준 (2025 데이터는 2026 하반기 발표 예정)


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

    FTC 미등재 (직영 브랜드 등) 시 benchmark_available=False.
    """
    sql = text(
        """
        SELECT "corpNm", "brandNm", "indutyLclasNm", "indutyMlsfcNm",
               "frcsCnt", "newFrcsRgsCnt", "ctrtEndCnt", "ctrtCncltnCnt", "nmChgCnt",
               "avrgSlsAmt", "arUnitAvrgSlsAmt"
          FROM ftc_brand_franchise
         WHERE "brandNm" = :brand
           AND yr = :year
         LIMIT 1
        """
    )
    engine = get_sync_engine(os.environ["POSTGRES_URL"])
    with engine.connect() as conn:
        row = conn.execute(sql, {"brand": brand_name, "year": year}).mappings().first()

    if not row:
        return {
            "brand_name": brand_name,
            "benchmark_available": False,
            "reason": "FTC 가맹사업 공시 미등재 (직영 체제 또는 해당 연도 데이터 없음)",
            "reference_year": year,
        }

    frcs = row["frcsCnt"] or 0
    closure_rate = (row["ctrtEndCnt"] or 0) / frcs if frcs else None
    growth_rate = (row["newFrcsRgsCnt"] or 0) / frcs if frcs else None

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
        "closure_rate": round(closure_rate, 4) if closure_rate is not None else None,
        "growth_rate": round(growth_rate, 4) if growth_rate is not None else None,
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
