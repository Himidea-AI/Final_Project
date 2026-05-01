"""Step 0 후속 — 블로커 3개 해소용 추가 쿼리.

A. 좌표 소스: dong_mapping 대체 (kakao_store 동별 평균 좌표)
B. 이디야 실제 kakao_store 표기
C. biz_brand_mapping 테이블 실제 상태
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

for env_path in (Path(__file__).parents[2] / ".env", Path(__file__).parents[3] / ".env"):
    if env_path.exists():
        load_dotenv(env_path)
        break

from src.database.sync_engine import get_sync_engine  # noqa: E402

engine = get_sync_engine(os.environ["POSTGRES_URL"])

QUERIES: list[tuple[str, str]] = [
    (
        "A1. kakao_store 기반 동별 평균 좌표 (centroid 대용)",
        """
        SELECT dong_name,
               COUNT(*) AS store_cnt,
               AVG(lat)::numeric(10,6) AS avg_lat,
               AVG(lon)::numeric(10,6) AS avg_lon
          FROM kakao_store
         WHERE dong_name IS NOT NULL
           AND lat IS NOT NULL AND lon IS NOT NULL
         GROUP BY dong_name
         ORDER BY dong_name
         LIMIT 20
        """,
    ),
    (
        "A2. store_info 기반 동 좌표 (대안)",
        """
        SELECT dong_code, dong_name,
               COUNT(*) AS cnt,
               AVG(lat)::numeric(10,6) AS avg_lat,
               AVG(lon)::numeric(10,6) AS avg_lon
          FROM store_info
         WHERE dong_code LIKE '11440%'
         GROUP BY dong_code, dong_name
         ORDER BY dong_code
         LIMIT 20
        """,
    ),
    (
        "A3. 좌표 커버 품질 (NULL 비율)",
        """
        SELECT
            SUM(CASE WHEN lat IS NULL OR lon IS NULL THEN 1 ELSE 0 END) AS null_coords,
            COUNT(*) AS total,
            ROUND(SUM(CASE WHEN lat IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS null_pct
          FROM kakao_store
        """,
    ),
    (
        "B1. 이디야 실제 표기 (brand_name LIKE)",
        """
        SELECT brand_name, COUNT(*) AS cnt
          FROM kakao_store
         WHERE brand_name ILIKE '%이디야%' OR brand_name ILIKE '%ediya%'
         GROUP BY brand_name
        """,
    ),
    (
        "B2. 이디야 place_name 검색 (brand_name이 비어있는 경우)",
        """
        SELECT place_name, brand_name, dong_name
          FROM kakao_store
         WHERE place_name ILIKE '%이디야%'
         LIMIT 10
        """,
    ),
    (
        "C1. biz_brand_mapping 전체 row/샘플",
        """
        SELECT COUNT(*) AS total_rows,
               COUNT(DISTINCT brand_name) AS unique_brands,
               COUNT(*) FILTER (WHERE mapo_store_count > 0) AS with_mapo_stores
          FROM biz_brand_mapping
        """,
    ),
    (
        "C2. biz_brand_mapping 샘플 10개",
        """
        SELECT brand_name, company_name, franchise_count, mapo_store_count, avg_sales
          FROM biz_brand_mapping
         ORDER BY mapo_store_count DESC NULLS LAST
         LIMIT 10
        """,
    ),
    (
        "C3. ftc_brand_franchise 2024 대상 브랜드 존재 확인",
        """
        SELECT "brandNm", "frcsCnt", "avrgSlsAmt", "indutyMlsfcNm"
          FROM ftc_brand_franchise
         WHERE yr = 2024
           AND "brandNm" IN ('빽다방','메가MGC커피','이디야','이디야커피',
                              '교촌치킨','BBQ','BHC','맘스터치','롯데리아','버거킹','스타벅스')
         ORDER BY "frcsCnt" DESC
        """,
    ),
    (
        "C4. ftc_brand_franchise 이디야 표기 검색",
        """
        SELECT DISTINCT "brandNm"
          FROM ftc_brand_franchise
         WHERE "brandNm" ILIKE '%이디야%'
        """,
    ),
    (
        "D. kakao_store_hours 존재 여부 (보조용)",
        """
        SELECT COUNT(*) AS total,
               COUNT(DISTINCT kakao_id) AS stores
          FROM kakao_store_hours
        """,
    ),
]


def main() -> None:
    for title, sql in QUERIES:
        print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")
        try:
            with engine.connect() as conn:
                rows = conn.execute(text(sql)).mappings().all()
            if not rows:
                print("(empty)")
                continue
            for r in rows:
                print(dict(r))
        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
