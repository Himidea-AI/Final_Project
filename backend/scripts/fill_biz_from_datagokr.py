"""biz_brand_mapping 사업자번호 일괄 채우기 — data.go.kr 가맹정보 API 기반.

공정거래위원회_가맹정보_브랜드 목록 정보 제공 서비스에서
전체 브랜드의 사업자등록번호(brno)를 가져와 biz_brand_mapping 업데이트.

Usage:
    cd backend && python scripts/fill_biz_from_datagokr.py [--dry-run] [--year 2024]
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import requests
from sqlalchemy import text

sys.path.insert(0, ".")
from src.database.sync_engine import get_sync_engine  # noqa: E402


def _db_url() -> str:
    from src.config.settings import settings

    return settings.postgres_url


def fetch_all_brands(api_key: str, year: str) -> list[dict]:
    """data.go.kr에서 전체 브랜드 목록 조회 (페이지네이션)."""
    brands = []
    page = 1
    num_rows = 100

    while True:
        url = (
            f"https://apis.data.go.kr/1130000/FftcBrandRlsInfo2_Service/getBrandinfo"
            f"?serviceKey={api_key}&pageNo={page}&numOfRows={num_rows}"
            f"&resultType=json&jngBizCrtraYr={year}"
        )
        resp = requests.get(url, timeout=30)
        data = resp.json()

        items = data.get("items", [])
        if not items:
            break

        brands.extend(items)
        total = int(data.get("totalCount", 0))
        print(f"  page {page}: {len(items)}건 (누적 {len(brands)}/{total})")

        if len(brands) >= total:
            break
        page += 1
        time.sleep(0.3)

    print(f"data.go.kr: {year}년 브랜드 {len(brands)}개 조회 완료")
    return brands


def run(year: str = "2024", dry_run: bool = False) -> None:
    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.environ.get("NTS_API_KEY", "")
    if not api_key:
        print("ERROR: NTS_API_KEY가 .env에 설정되어 있지 않습니다.")
        return

    # 1. API에서 전체 브랜드 가져오기
    print("data.go.kr API 조회 중...")
    api_brands = fetch_all_brands(api_key, year)
    if not api_brands:
        print("ERROR: 브랜드 목록이 비어있습니다.")
        return

    # 2. brno → {corpNm, brandNm} 매핑 구축
    api_map: dict[tuple[str, str], str] = {}
    for b in api_brands:
        corp = (b.get("corpNm") or "").strip()
        brand = (b.get("brandNm") or "").strip()
        brno = (b.get("brno") or "").strip()
        if corp and brand and brno and len(brno) == 10:
            api_map[(corp, brand)] = brno

    print(f"유효한 사업자번호: {len(api_map)}건")

    # 3. DB에서 가상번호 행 가져오기
    engine = get_sync_engine(_db_url())
    with engine.connect() as conn:
        fake_rows = conn.execute(
            text("SELECT biz_number, company_name, brand_name FROM biz_brand_mapping WHERE biz_number LIKE 's_%'")
        ).fetchall()

    print(f"가상 사업자번호 행: {len(fake_rows)}건")

    # 4. 매칭 + 업데이트
    updated = 0
    skipped = 0
    not_found = 0

    with engine.connect() as conn:
        for row in fake_rows:
            d = dict(row._mapping)
            key = (d["company_name"].strip(), d["brand_name"].strip())
            brno = api_map.get(key)

            if not brno:
                not_found += 1
                continue

            # 중복 체크
            dup = conn.execute(
                text("SELECT 1 FROM biz_brand_mapping WHERE biz_number = :biz"),
                {"biz": brno},
            ).fetchone()

            if dry_run:
                status = "DUP" if dup else "OK"
                if updated < 10:
                    print(f"  [DRY {status}] {d['biz_number']} → {brno} | {d['company_name']} | {d['brand_name']}")
                updated += 1
                continue

            if dup:
                conn.execute(
                    text("DELETE FROM biz_brand_mapping WHERE biz_number = :old"),
                    {"old": d["biz_number"]},
                )
                skipped += 1
            else:
                conn.execute(
                    text("UPDATE biz_brand_mapping SET biz_number = :new WHERE biz_number = :old"),
                    {"new": brno, "old": d["biz_number"]},
                )
                updated += 1

        if not dry_run:
            conn.commit()

    # 5. 결과
    with engine.connect() as conn:
        real_cnt = conn.execute(
            text("SELECT COUNT(*) FROM biz_brand_mapping WHERE biz_number NOT LIKE 's_%'")
        ).scalar()
        total = conn.execute(text("SELECT COUNT(*) FROM biz_brand_mapping")).scalar()

    print(f"\n완료!")
    print(f"  업데이트: {updated}건")
    print(f"  중복 정리: {skipped}건")
    print(f"  미매칭: {not_found}건")
    print(f"  진짜 사업자번호: {real_cnt}건 / 전체: {total}건")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="data.go.kr 가맹정보 API로 사업자번호 일괄 채우기")
    parser.add_argument("--dry-run", action="store_true", help="실제 DB 수정 없이 미리보기")
    parser.add_argument("--year", default="2024", help="기준년도 (기본: 2024)")
    args = parser.parse_args()

    run(year=args.year, dry_run=args.dry_run)
