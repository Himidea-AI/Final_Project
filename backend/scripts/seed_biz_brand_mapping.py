"""biz_brand_mapping 테이블 bulk seed — ftc_brand_franchise 기반.

ftc_brand_franchise 테이블의 법인명(corpNm)별 대표 브랜드를 선정하여
biz_brand_mapping에 INSERT. 기존 행(사업자번호 기준)은 건너뜀.

사업자등록번호는 ftc_brand_franchise에 없으므로,
corpNm 해시 기반 가상 biz_number를 생성한다 (실제 가입 시 ON CONFLICT DO UPDATE로 덮어씀).

Usage:
    cd backend
    python scripts/seed_biz_brand_mapping.py [--dry-run] [--year 2024]
"""

from __future__ import annotations

import argparse
import hashlib
import sys

from sqlalchemy import text

sys.path.insert(0, ".")
from src.database.sync_engine import get_sync_engine  # noqa: E402


def _db_url() -> str:
    from src.config.settings import settings

    return settings.postgres_url


def _make_virtual_biz(corp_name: str) -> str:
    """법인명 해시로 가상 사업자번호 생성 (10자리, 숫자+영소문자).

    실제 가입 시 ON CONFLICT DO UPDATE로 진짜 번호로 교체됨.
    """
    h = hashlib.md5(corp_name.encode()).hexdigest()[:8]
    return f"s_{h}"


def seed(year: int | None = None, dry_run: bool = False) -> None:
    engine = get_sync_engine(_db_url())

    with engine.connect() as conn:
        # 1. 최신 연도 결정
        if year is None:
            year = conn.execute(text("SELECT MAX(yr) FROM ftc_brand_franchise")).scalar()
            print(f"최신 연도: {year}")

        # 2. 법인명별 대표 브랜드 선정 (가맹점 수 최대)
        rows = conn.execute(
            text(
                """
                SELECT DISTINCT ON ("corpNm")
                    "corpNm" AS corp_name,
                    "brandNm" AS brand_name,
                    "indutyLclasNm" AS industry_large,
                    "indutyMlsfcNm" AS industry_medium,
                    "frcsCnt" AS franchise_count,
                    "avrgSlsAmt" AS avg_sales
                FROM ftc_brand_franchise
                WHERE yr = :yr AND "frcsCnt" > 0
                ORDER BY "corpNm", "frcsCnt" DESC
                """
            ),
            {"yr": year},
        ).fetchall()

        print(f"ftc_brand_franchise {year}년 법인 수: {len(rows)}")

        # 3. 기존 biz_brand_mapping 확인 (중복 방지)
        existing = conn.execute(text("SELECT biz_number FROM biz_brand_mapping")).fetchall()
        existing_set = {r[0] for r in existing}
        print(f"기존 biz_brand_mapping 행 수: {len(existing_set)}")

        # 4. INSERT 준비
        inserted = 0
        skipped = 0
        for row in rows:
            d = dict(row._mapping)
            virtual_biz = _make_virtual_biz(d["corp_name"])

            if virtual_biz in existing_set:
                skipped += 1
                continue

            if dry_run:
                print(f"  [DRY] {virtual_biz} | {d['corp_name']} | {d['brand_name']} | {d['franchise_count']}개")
                inserted += 1
                continue

            conn.execute(
                text(
                    """
                    INSERT INTO biz_brand_mapping
                        (biz_number, company_name, brand_name,
                         industry_large, industry_medium,
                         franchise_count, avg_sales, mapo_store_count)
                    VALUES
                        (:biz, :corp, :brand, :ind_l, :ind_m, :frc, :avg, 0)
                    ON CONFLICT (biz_number) DO NOTHING
                    """
                ),
                {
                    "biz": virtual_biz,
                    "corp": d["corp_name"],
                    "brand": d["brand_name"],
                    "ind_l": d["industry_large"],
                    "ind_m": d["industry_medium"],
                    "frc": d["franchise_count"],
                    "avg": d["avg_sales"],
                },
            )
            inserted += 1

        if not dry_run:
            conn.commit()

        print(f"\n완료: {inserted}건 INSERT, {skipped}건 SKIP (이미 존재)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="biz_brand_mapping bulk seed")
    parser.add_argument("--dry-run", action="store_true", help="실제 INSERT 없이 미리보기")
    parser.add_argument("--year", type=int, default=None, help="대상 연도 (기본: 최신)")
    args = parser.parse_args()

    from dotenv import load_dotenv

    load_dotenv()
    seed(year=args.year, dry_run=args.dry_run)
