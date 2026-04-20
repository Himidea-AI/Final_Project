"""competitor_intel Agent 구현 전 DB 실측 검증 스크립트.

실행:
    cd backend
    PYTHONPATH=. python scripts/verify_competitor_intel_data.py

출력:
    - kakao_store의 대상 브랜드 분포
    - biz_brand_mapping ↔ ftc_brand_franchise 매칭 규칙
    - dong_mapping centroid 컬럼명
    - store_quarterly 마포 커버
    - avg_sales 단위 일치 여부
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

# .env 로드 (worktree/루트 양쪽 지원)
for env_path in (Path(__file__).parents[2] / ".env", Path(__file__).parents[3] / ".env"):
    if env_path.exists():
        load_dotenv(env_path)
        break

from src.database.sync_engine import get_sync_engine  # noqa: E402

DB_URL = os.environ.get("POSTGRES_URL")
if not DB_URL:
    print("ERROR: POSTGRES_URL not set", file=sys.stderr)
    sys.exit(1)

engine = get_sync_engine(DB_URL)

QUERIES: list[tuple[str, str]] = [
    (
        "1. kakao_target_brands — 대상 10개 브랜드 kakao_store 분포",
        """
        SELECT brand_name, COUNT(*) AS cnt,
               array_agg(DISTINCT dong_name ORDER BY dong_name) AS dongs
          FROM kakao_store
         WHERE brand_name IN ('빽다방','메가MGC커피','이디야','스타벅스',
                              '교촌치킨','BBQ','BHC','맘스터치','롯데리아','버거킹')
         GROUP BY brand_name
         ORDER BY cnt DESC
        """,
    ),
    (
        "2. brand_name_overlap — biz_brand_mapping ↔ ftc_brand_franchise 매칭",
        """
        SELECT bbm.brand_name AS biz_name, fbf."brandNm" AS ftc_name
          FROM biz_brand_mapping bbm
          LEFT JOIN ftc_brand_franchise fbf
                 ON (fbf."brandNm" = bbm.brand_name
                     OR bbm.brand_name LIKE fbf."brandNm" || '%')
         WHERE bbm.brand_name IN ('빽다방','교촌치킨','맘스터치','이디야','메가MGC커피')
         LIMIT 20
        """,
    ),
    (
        "3. dong_mapping_cols — centroid 좌표 컬럼명 확인",
        """
        SELECT column_name, data_type
          FROM information_schema.columns
         WHERE table_name = 'dong_mapping'
         ORDER BY ordinal_position
        """,
    ),
    (
        "4. store_quarterly_mapo — 마포 커버/분기 범위",
        """
        SELECT COUNT(*) AS total,
               COUNT(DISTINCT dong_code) AS dong_cnt,
               COUNT(DISTINCT industry_code) AS ind_cnt,
               MIN(quarter) AS earliest,
               MAX(quarter) AS latest
          FROM store_quarterly
         WHERE dong_code LIKE '11440%'
        """,
    ),
    (
        "5. avg_sales_unit — biz vs ftc 단위 비교",
        """
        SELECT bbm.brand_name,
               bbm.avg_sales AS biz_avg,
               fbf."avrgSlsAmt" AS ftc_avg
          FROM biz_brand_mapping bbm
          JOIN ftc_brand_franchise fbf ON fbf."brandNm" = bbm.brand_name
         WHERE bbm.brand_name IN ('빽다방','교촌치킨','맘스터치')
           AND fbf.yr = 2024
        """,
    ),
    (
        "6. industry_codes — store_quarterly 실제 업종 코드 샘플",
        """
        SELECT DISTINCT industry_code, industry_name
          FROM store_quarterly
         WHERE dong_code LIKE '11440%'
           AND industry_name ~ '(커피|치킨|버거|햄버거|패스트)'
         ORDER BY industry_name
         LIMIT 15
        """,
    ),
    (
        "7. kakao_category_samples — category 필드 실제 포맷 확인",
        """
        SELECT category, COUNT(*) AS cnt
          FROM kakao_store
         WHERE category ~ '(커피|카페|치킨|버거|햄버거)'
         GROUP BY category
         ORDER BY cnt DESC
         LIMIT 15
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
