"""biz_brand_mapping의 가상 사업자번호(s_*)를 진짜 번호로 교체.

공정위 가맹사업 정보공개서 API에서 전체 브랜드 목록을 가져온 뒤,
각 정보공개서 본문(XML)에서 사업자등록번호를 추출하여 UPDATE.

Usage:
    1. .env에 FTC_API_KEY를 새로 발급받은 키로 교체
    2. cd backend && python scripts/fill_biz_numbers_from_ftc.py [--dry-run] [--year 2025] [--limit 100]

주의:
    - API 호출 1건당 약 1~2초 소요. 전체 5,900건 기준 약 2~3시간.
    - --limit으로 테스트 후 전체 실행 권장.
    - 기존 진짜 사업자번호(s_가 아닌 것)는 건너뜀.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys

import httpx
from lxml import etree
from sqlalchemy import text
from urllib.parse import unquote

sys.path.insert(0, ".")
from src.database.sync_engine import get_sync_engine  # noqa: E402

BASE_URL = "https://franchise.ftc.go.kr"
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://franchise.ftc.go.kr/",
    "Accept": "application/xml, text/xml, */*",
}


def _db_url() -> str:
    from src.config.settings import settings

    return settings.postgres_url


def _extract_biz_number(xml_content: str) -> str | None:
    """정보공개서 본문 XML에서 사업자등록번호를 추출.

    패턴: XXX-XX-XXXXX 또는 XXXXXXXXXX (10자리 숫자)
    """
    # 하이픈 포함 패턴
    m = re.search(r"사업자[^0-9]{0,20}(\d{3})-(\d{2})-(\d{5})", xml_content)
    if m:
        return m.group(1) + m.group(2) + m.group(3)

    # 하이픈 없는 10자리
    m = re.search(r"사업자[^0-9]{0,20}(\d{10})", xml_content)
    if m:
        return m.group(1)

    # 등록번호 패턴
    m = re.search(r"등록번호[^0-9]{0,20}(\d{3})-(\d{2})-(\d{5})", xml_content)
    if m:
        return m.group(1) + m.group(2) + m.group(3)

    return None


async def fetch_all_brands(api_key: str, year: str) -> list[dict]:
    """FTC API에서 전체 브랜드 목록 조회."""
    key = unquote(api_key)
    url = f"{BASE_URL}/api/search.do?type=list&yr={year}&serviceKey={key}"

    async with httpx.AsyncClient(timeout=30, headers=_BROWSER_HEADERS) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    root = etree.fromstring(resp.content)
    items = root.findall(".//item")

    brands = []
    for item in items:
        brands.append(
            {
                "jng_ifrmp_sn": item.findtext("jngIfrmpSn") or "",
                "brand_name": item.findtext("brandNm") or "",
                "corp_name": item.findtext("corpNm") or "",
            }
        )

    print(f"FTC API: {year}년 브랜드 {len(brands)}개 조회 완료")
    return brands


async def fetch_content_and_extract_biz(api_key: str, jng_ifrmp_sn: str) -> str | None:
    """정보공개서 본문에서 사업자등록번호 추출."""
    key = unquote(api_key)
    url = f"{BASE_URL}/api/search.do?type=content&jngIfrmpSn={jng_ifrmp_sn}&serviceKey={key}"

    try:
        async with httpx.AsyncClient(timeout=20, headers=_BROWSER_HEADERS) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        return _extract_biz_number(resp.text)
    except Exception as e:
        print(f"  [ERROR] jngIfrmpSn={jng_ifrmp_sn}: {e}")
        return None


async def run(
    year: str = "2025",
    dry_run: bool = False,
    limit: int | None = None,
) -> None:
    import os
    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.environ.get("FTC_API_KEY", "")
    if not api_key:
        print("ERROR: FTC_API_KEY가 .env에 설정되어 있지 않습니다.")
        return

    # 1. API 키 유효성 확인
    print("FTC API 키 확인 중...")
    try:
        test_brands = await fetch_all_brands(api_key, year)
    except Exception as e:
        print(f"ERROR: FTC API 호출 실패 — {e}")
        print("API 키가 유효한지 확인해주세요.")
        return

    if not test_brands:
        print("ERROR: 브랜드 목록이 비어있습니다. 연도를 확인해주세요.")
        return

    # 2. DB에서 가상 사업자번호(s_*) 행 조회
    engine = get_sync_engine(_db_url())
    with engine.connect() as conn:
        fake_rows = conn.execute(
            text("SELECT biz_number, company_name, brand_name FROM biz_brand_mapping WHERE biz_number LIKE 's_%'")
        ).fetchall()

    fake_map: dict[str, dict] = {}
    for r in fake_rows:
        d = dict(r._mapping)
        key = (d["company_name"].strip(), d["brand_name"].strip())
        fake_map[key] = d

    print(f"가상 사업자번호 행: {len(fake_map)}건")

    # 3. FTC 브랜드 목록과 DB 매칭
    matched = []
    for brand in test_brands:
        key = (brand["corp_name"].strip(), brand["brand_name"].strip())
        if key in fake_map:
            matched.append({**brand, "old_biz": fake_map[key]["biz_number"]})

    print(f"FTC ↔ DB 매칭: {len(matched)}건")

    if limit:
        matched = matched[:limit]
        print(f"--limit {limit} 적용 → {len(matched)}건 처리")

    # 4. 각 브랜드의 정보공개서에서 사업자번호 추출
    updated = 0
    skipped = 0
    failed = 0

    with engine.connect() as conn:
        for i, brand in enumerate(matched):
            # Rate limiting (1초 간격)
            if i > 0 and i % 10 == 0:
                print(f"  진행: {i}/{len(matched)} (updated={updated}, skipped={skipped}, failed={failed})")
                await asyncio.sleep(1)

            biz_number = await fetch_content_and_extract_biz(api_key, brand["jng_ifrmp_sn"])

            if not biz_number:
                failed += 1
                continue

            # 이미 같은 사업자번호가 DB에 있으면 skip
            dup = conn.execute(
                text("SELECT 1 FROM biz_brand_mapping WHERE biz_number = :biz"),
                {"biz": biz_number},
            ).fetchone()

            if dry_run:
                status = "DUP" if dup else "OK"
                print(
                    f"  [DRY {status}] {brand['old_biz']} → {biz_number} | {brand['corp_name']} | {brand['brand_name']}"
                )
                updated += 1
                continue

            if dup:
                # 중복이면 가상번호 행 삭제 (진짜 번호가 이미 있으므로)
                conn.execute(
                    text("DELETE FROM biz_brand_mapping WHERE biz_number = :old"),
                    {"old": brand["old_biz"]},
                )
                skipped += 1
            else:
                conn.execute(
                    text("UPDATE biz_brand_mapping SET biz_number = :new WHERE biz_number = :old"),
                    {"new": biz_number, "old": brand["old_biz"]},
                )
                updated += 1

        if not dry_run:
            conn.commit()

    # 5. 결과
    with engine.connect() as conn:
        real_cnt = conn.execute(text("SELECT COUNT(*) FROM biz_brand_mapping WHERE biz_number NOT LIKE 's_%'")).scalar()
        total = conn.execute(text("SELECT COUNT(*) FROM biz_brand_mapping")).scalar()

    print("\n완료!")
    print(f"  업데이트: {updated}건")
    print(f"  중복 정리: {skipped}건")
    print(f"  추출 실패: {failed}건")
    print(f"  진짜 사업자번호: {real_cnt}건 / 전체: {total}건")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FTC API로 사업자번호 일괄 채우기")
    parser.add_argument("--dry-run", action="store_true", help="실제 DB 수정 없이 미리보기")
    parser.add_argument("--year", default="2025", help="FTC 정보공개서 연도 (기본: 2025)")
    parser.add_argument("--limit", type=int, default=None, help="처리할 최대 건수 (테스트용)")
    args = parser.parse_args()

    asyncio.run(run(year=args.year, dry_run=args.dry_run, limit=args.limit))
