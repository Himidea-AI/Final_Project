"""마포 kakao_store 에 누락된 brand 매장 일괄 적재.

사용자 보고 (2026-05-06): 한신포차 홍대점 (마포 잔다리로 13) 등 더본/본아이에프 다업종
brand 가 kakao 에 실존하지만 우리 kakao_store DB 에 미적재. corp_brand_resolver 로
override 된 brand_name 검색 시 마포 0건 → 자사 매장 별표 표시 누락.

해결: Kakao Local Search API 로 마포 16동 × N brand 검색 → 누락 매장 INSERT.

Usage:
    cd backend && PYTHONIOENCODING=utf-8 python -X utf8 scripts/ingest/refresh_kakao_missing_brands.py
    cd backend && ... refresh_kakao_missing_brands.py --dry-run
    cd backend && ... refresh_kakao_missing_brands.py --brand 한신포차
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv("../.env")

sys.path.insert(0, ".")

from sqlalchemy import text  # noqa: E402

from src.database.sync_engine import get_sync_engine  # noqa: E402

# ---------------------------------------------------------------------------
# 마포 16동 centroid (MapSection.tsx 의 DONG_COORDS 와 동일)
# ---------------------------------------------------------------------------

MAPO_DONGS: dict[str, tuple[float, float]] = {
    "아현동": (37.5502, 126.9594),
    "공덕동": (37.543, 126.9519),
    "도화동": (37.5393, 126.9457),
    "용강동": (37.5382, 126.9383),
    "대흥동": (37.548, 126.9437),
    "염리동": (37.5523, 126.9474),
    "신수동": (37.5453, 126.9361),
    "서강동": (37.5493, 126.9347),
    "서교동": (37.5565, 126.9239),
    "합정동": (37.5497, 126.9143),
    "망원1동": (37.5558, 126.9059),
    "망원2동": (37.5531, 126.9021),
    "연남동": (37.5617, 126.9226),
    "성산1동": (37.5663, 126.9069),
    "성산2동": (37.5706, 126.9111),
    "상암동": (37.5789, 126.8899),
}

# ---------------------------------------------------------------------------
# 누락 brand list — 검증 결과 (FTC ≥ 50 인데 kakao_store 마포 0건)
# ---------------------------------------------------------------------------

MISSING_BRANDS: list[str] = [
    # 더본코리아
    "한신포차",
    "빽보이피자",
    "롤링파스타",
    "백스비어",
    "리춘시장",
    "막이오름",
    "인생설렁탕",
    # 본아이에프
    "본죽&비빔밥",
    "본도시락",
    "본설렁탕",
    # 다름플러스
    "이차돌",
    "제육폭식",
]


# ---------------------------------------------------------------------------
# Kakao Local Search API
# ---------------------------------------------------------------------------

KAKAO_API = "https://dapi.kakao.com/v2/local/search/keyword.json"
SEARCH_RADIUS_M = 2000  # 동 centroid 기준 2km — 마포 16동 cover


def _kakao_search(api_key: str, query: str, lat: float, lon: float, radius: int = SEARCH_RADIUS_M) -> list[dict]:
    """Kakao Local Search keyword API 호출. 반경 내 매장 list."""
    headers = {"Authorization": f"KakaoAK {api_key}"}
    all_docs: list[dict] = []
    page = 1
    while page <= 3:  # max 45 results (15 per page × 3)
        params = {
            "query": query,
            "x": str(lon),
            "y": str(lat),
            "radius": radius,
            "page": page,
            "size": 15,
            "sort": "distance",
        }
        try:
            r = requests.get(KAKAO_API, headers=headers, params=params, timeout=10)
            if r.status_code != 200:
                print(f"  [kakao] {r.status_code} {r.text[:100]}")
                break
            data = r.json()
            docs = data.get("documents", [])
            all_docs.extend(docs)
            if data.get("meta", {}).get("is_end", True):
                break
            page += 1
            time.sleep(0.1)  # rate limit 부드럽게
        except Exception as e:
            print(f"  [kakao] error {e}")
            break
    return all_docs


def _is_mapo(address: str) -> bool:
    """주소가 마포구 안인지."""
    if not address:
        return False
    return "마포구" in address or "Mapo" in address


def _extract_dong(address: str) -> str | None:
    """address 에서 dong_name 추출 — '서울 마포구 X동' 패턴."""
    if not address:
        return None
    parts = address.split()
    for p in parts:
        if p.endswith("동") and "마포구" not in p:
            return p
    return None


def _kakao_doc_to_store(doc: dict, brand_query: str) -> dict | None:
    """Kakao API doc → kakao_store row dict. 마포 외 매장은 None."""
    address = doc.get("address_name") or ""
    road = doc.get("road_address_name") or ""
    if not _is_mapo(address) and not _is_mapo(road):
        return None
    dong = _extract_dong(address)
    if not dong:
        return None

    return {
        "kakao_id": doc.get("id"),
        "place_name": doc.get("place_name") or "",
        "brand_name": brand_query,  # 검색 query 를 brand_name 으로 (정규화는 brand_mapping_resolver)
        "category": _infer_category(doc.get("category_name") or ""),
        "category_detail": doc.get("category_name") or None,
        "address": address or None,
        "road_address": road or None,
        "dong_name": dong,
        "lat": float(doc.get("y") or 0) if doc.get("y") else None,
        "lon": float(doc.get("x") or 0) if doc.get("x") else None,
        "phone": doc.get("phone") or None,
        "place_url": doc.get("place_url") or None,
        "is_franchise": True,  # 검색 brand 매칭 매장 = 가맹점 추정
        "collected_at": datetime.now(timezone.utc),
    }


def _infer_category(category_name: str) -> str:
    """Kakao category_name (예: '음식점 > 한식 > 백반') → 우리 표기 ('한식음식점' 등)."""
    if not category_name:
        return "기타"
    last = category_name.split(">")[-1].strip().lower()
    full = category_name.lower()
    # 매핑 — kakao_store top categories 와 일치
    if "한식" in full:
        return "한식음식점"
    if "중식" in full or "중국" in full:
        return "중식음식점"
    if "일식" in full:
        return "일식음식점"
    if "양식" in full or "이탈리" in full or "파스타" in full or "스테이크" in full:
        return "양식음식점"
    if "베이커리" in full or "제과" in full or "빵" in full:
        return "제과점"
    if "패스트푸드" in full or "버거" in full or "햄버거" in full:
        return "패스트푸드점"
    if "치킨" in full:
        return "치킨전문점"
    if "분식" in full:
        return "분식전문점"
    if "주점" in full or "호프" in full or "이자카야" in full:
        return "호프-간이주점"
    if "카페" in full or "커피" in full:
        return "커피-음료"
    if "피자" in full:
        # 피자: kakao_store 의 기존 정책 — 패스트푸드점 (commercial_intelligence.py:_KAKAO_CATEGORY_MAP)
        return "패스트푸드점"
    return "기타"


# ---------------------------------------------------------------------------
# UPSERT
# ---------------------------------------------------------------------------


def _upsert_stores(engine, stores: list[dict]) -> int:
    """kakao_store ON CONFLICT (kakao_id) DO UPDATE — 변경 row 수 반환."""
    if not stores:
        return 0
    sql = text(
        """
        INSERT INTO kakao_store (
            kakao_id, place_name, brand_name, category, category_detail,
            address, road_address, dong_name, lat, lon, phone, place_url,
            is_franchise, collected_at
        ) VALUES (
            :kakao_id, :place_name, :brand_name, :category, :category_detail,
            :address, :road_address, :dong_name, :lat, :lon, :phone, :place_url,
            :is_franchise, :collected_at
        )
        ON CONFLICT (kakao_id) DO UPDATE SET
            place_name = EXCLUDED.place_name,
            brand_name = EXCLUDED.brand_name,
            category = EXCLUDED.category,
            category_detail = EXCLUDED.category_detail,
            address = EXCLUDED.address,
            road_address = EXCLUDED.road_address,
            dong_name = EXCLUDED.dong_name,
            lat = EXCLUDED.lat,
            lon = EXCLUDED.lon,
            phone = EXCLUDED.phone,
            place_url = EXCLUDED.place_url,
            is_franchise = EXCLUDED.is_franchise,
            collected_at = EXCLUDED.collected_at
        """
    )
    with engine.begin() as conn:
        conn.execute(sql, stores)
    return len(stores)


# ---------------------------------------------------------------------------
# Main ETL
# ---------------------------------------------------------------------------


def run(brands: list[str], dry_run: bool = False) -> None:
    api_key = os.environ.get("KAKAO_API_KEY")
    if not api_key:
        raise SystemExit("KAKAO_API_KEY missing in .env")

    engine = get_sync_engine(os.environ["POSTGRES_URL"])

    print(f"=== Kakao 누락 brand ETL 시작 — {len(brands)} brand × {len(MAPO_DONGS)} 동 ===")
    print(f"   dry_run={dry_run} radius={SEARCH_RADIUS_M}m")
    print()

    total_found = 0
    total_inserted = 0
    seen_ids: set[str] = set()
    per_brand: dict[str, int] = {}

    for brand in brands:
        per_brand[brand] = 0
        brand_buffer: list[dict] = []
        for dong, (lat, lon) in MAPO_DONGS.items():
            docs = _kakao_search(api_key, brand, lat, lon)
            for doc in docs:
                kid = doc.get("id")
                if not kid or kid in seen_ids:
                    continue
                seen_ids.add(kid)
                store = _kakao_doc_to_store(doc, brand)
                if store:
                    brand_buffer.append(store)
                    per_brand[brand] += 1
        total_found += len(brand_buffer)
        print(f"  [{brand:<15s}] 마포 {len(brand_buffer)}건 발견")
        if brand_buffer and not dry_run:
            _upsert_stores(engine, brand_buffer)
            total_inserted += len(brand_buffer)

    print()
    print(f"=== 완료 — 발견 {total_found}건 / 적재 {total_inserted}건 ===")
    if dry_run:
        print("   (dry_run 모드 — DB write 없음)")
    print()
    print("=== brand 별 ===")
    for brand, cnt in sorted(per_brand.items(), key=lambda x: -x[1]):
        print(f"  {brand:<15s}: {cnt}")


def main():
    parser = argparse.ArgumentParser(description="Kakao 누락 brand 마포 매장 적재")
    parser.add_argument(
        "--brand",
        default=None,
        help="단일 brand 만 처리 (default: 전체 MISSING_BRANDS)",
    )
    parser.add_argument("--dry-run", action="store_true", help="DB write 없이 발견만")
    args = parser.parse_args()

    brands = [args.brand] if args.brand else MISSING_BRANDS
    run(brands, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
