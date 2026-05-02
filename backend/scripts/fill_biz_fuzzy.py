"""biz_brand_mapping 퍼지 매칭 — 미매칭 1,137건 추가 커버.

data.go.kr API에서 가져온 브랜드와 DB의 법인명/브랜드명을
유사도 기반으로 매칭하여 사업자번호 업데이트.

Usage:
    cd backend && python scripts/fill_biz_fuzzy.py [--dry-run] [--threshold 0.75]
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time

import requests
from difflib import SequenceMatcher
from sqlalchemy import text

sys.path.insert(0, ".")
from src.database.sync_engine import get_sync_engine  # noqa: E402


def _db_url() -> str:
    from src.config.settings import settings

    return settings.postgres_url


def normalize(s: str) -> str:
    """매칭용 정규화."""
    s = s.lower().strip()
    s = re.sub(r"[\(\)\[\]（）\s\.\,\-]", "", s)
    s = s.replace("㈜", "").replace("주식회사", "")
    return s


def fetch_api_brands(api_key: str) -> dict[tuple[str, str], str]:
    """data.go.kr에서 전체 브랜드 → {(corpNm, brandNm): brno} 매핑."""
    all_brands: list[dict] = []
    page = 1
    while True:
        url = (
            f"https://apis.data.go.kr/1130000/FftcBrandRlsInfo2_Service/getBrandinfo"
            f"?serviceKey={api_key}&pageNo={page}&numOfRows=100"
            f"&resultType=json&jngBizCrtraYr=2024"
        )
        r = requests.get(url, timeout=30)
        data = r.json()
        items = data.get("items", [])
        if not items:
            break
        all_brands.extend(items)
        total = int(data.get("totalCount", 0))
        if page % 20 == 0:
            print(f"  API 조회 중... {len(all_brands)}/{total}")
        if len(all_brands) >= total:
            break
        page += 1
        time.sleep(0.2)

    print(f"API 브랜드: {len(all_brands)}개")

    api_map: dict[tuple[str, str], str] = {}
    for b in all_brands:
        corp = (b.get("corpNm") or "").strip()
        brand = (b.get("brandNm") or "").strip()
        brno = (b.get("brno") or "").strip()
        if corp and brand and brno and len(brno) == 10:
            api_map[(corp, brand)] = brno

    print(f"유효한 사업자번호: {len(api_map)}건")
    return api_map


def run(threshold: float = 0.75, dry_run: bool = False) -> None:
    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.environ.get("NTS_API_KEY", "")
    if not api_key:
        print("ERROR: NTS_API_KEY 없음")
        return

    # 1. API에서 전체 브랜드 가져오기
    print("data.go.kr API 조회 중...")
    api_map = fetch_api_brands(api_key)

    # 2. 정규화된 API 인덱스 구축
    api_normalized: list[tuple[str, str, str, str, str]] = []
    for (corp, brand), brno in api_map.items():
        api_normalized.append((normalize(corp), normalize(brand), corp, brand, brno))

    # 3. DB에서 미매칭 건 가져오기
    engine = get_sync_engine(_db_url())
    with engine.connect() as conn:
        fakes = conn.execute(
            text("SELECT biz_number, company_name, brand_name FROM biz_brand_mapping WHERE biz_number LIKE 's_%'")
        ).fetchall()

    print(f"미매칭: {len(fakes)}건")
    print(f"임계값: {threshold}")

    # 4. 퍼지 매칭
    updated = 0
    skipped = 0

    with engine.connect() as conn:
        for i, row in enumerate(fakes):
            d = dict(row._mapping)
            db_corp = normalize(d["company_name"])
            db_brand = normalize(d["brand_name"])

            best_score = 0.0
            best_brno = None

            for norm_corp, norm_brand, _, _, brno in api_normalized:
                corp_score = SequenceMatcher(None, db_corp, norm_corp).ratio()
                brand_score = SequenceMatcher(None, db_brand, norm_brand).ratio()
                combined = corp_score * 0.4 + brand_score * 0.6

                if combined > best_score:
                    best_score = combined
                    best_brno = brno

            if best_score < threshold or not best_brno:
                skipped += 1
                continue

            # 중복 체크
            dup = conn.execute(
                text("SELECT 1 FROM biz_brand_mapping WHERE biz_number = :biz"),
                {"biz": best_brno},
            ).fetchone()

            if dry_run:
                if updated < 10:
                    print(f"  [DRY] {d['biz_number']} → {best_brno} ({best_score:.2f}) | {d['company_name']} | {d['brand_name']}")
                updated += 1
                continue

            if dup:
                conn.execute(
                    text("DELETE FROM biz_brand_mapping WHERE biz_number = :old"),
                    {"old": d["biz_number"]},
                )
            else:
                conn.execute(
                    text("UPDATE biz_brand_mapping SET biz_number = :new WHERE biz_number = :old"),
                    {"new": best_brno, "old": d["biz_number"]},
                )
            updated += 1

            if (i + 1) % 200 == 0:
                print(f"  진행: {i + 1}/{len(fakes)} (매칭 {updated})")

        if not dry_run:
            conn.commit()

    # 5. 결과
    with engine.connect() as conn:
        real_cnt = conn.execute(text("SELECT COUNT(*) FROM biz_brand_mapping WHERE biz_number NOT LIKE 's_%'")).scalar()
        total = conn.execute(text("SELECT COUNT(*) FROM biz_brand_mapping")).scalar()

    print(f"\n완료!")
    print(f"  퍼지 매칭: {updated}건")
    print(f"  미매칭 유지: {skipped}건")
    print(f"  진짜 사업자번호: {real_cnt}/{total} ({real_cnt / total * 100:.1f}%)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="퍼지 매칭으로 사업자번호 추가 채우기")
    parser.add_argument("--dry-run", action="store_true", help="미리보기")
    parser.add_argument("--threshold", type=float, default=0.75, help="유사도 임계값 (기본 0.75)")
    args = parser.parse_args()

    run(threshold=args.threshold, dry_run=args.dry_run)
