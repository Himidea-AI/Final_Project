"""마포 16동 학교 위치 ingest — 카카오 Local API 기반.

목적:
  - 학교환경위생정화구역(학교보건법 제6조) 거리 룰(rule_school_zone) 데이터 소스
  - 마포 16동 centroid(dong_centroid 테이블)에서 keyword="학교", radius=2000 검색
  - mapo_schools 테이블에 UPSERT (name + lat + lon UNIQUE)

전제:
  - alembic d4f1a2b3c5e6 (mapo_schools) 적용 완료
  - dong_centroid 적재 완료 (a8b2c4d6e8f0)
  - 환경변수: KAKAO_API_KEY 또는 KAKAO_REST_API_KEY (없으면 mock 5개로 fallback)

실행:
    python -m data.legal.ingest_mapo_schools
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

if sys.platform == "win32":
    import asyncio

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

POSTGRES_URL = os.getenv(
    "POSTGRES_URL",
    "postgresql://postgres:postgres@localhost:5432/mapo_simulator",
)
KAKAO_API_KEY = (
    os.getenv("KAKAO_API_KEY")
    or os.getenv("KAKAO_REST_API_KEY")
    or ""
)

# 마포 16동 (없으면 mock fallback 시 동 라벨로 사용)
_MAPO_DISTRICTS = [
    "아현동", "공덕동", "도화동", "용강동", "대흥동",
    "염리동", "신수동", "서교동", "합정동", "망원1동",
    "망원2동", "연남동", "성산1동", "성산2동", "상암동",
    "서강동",
]

# fallback mock 데이터 (실제 좌표 5개, KAKAO_API_KEY 없을 때만 사용)
_MOCK_SCHOOLS: list[dict] = [
    {
        "name": "망원초등학교",
        "school_type": "초등학교",
        "address": "서울 마포구 망원로 33",
        "lat": 37.5567,
        "lon": 126.9038,
        "district": "망원1동",
    },
    {
        "name": "합정중학교",
        "school_type": "중학교",
        "address": "서울 마포구 양화로 45",
        "lat": 37.5495,
        "lon": 126.9112,
        "district": "합정동",
    },
    {
        "name": "서울서교초등학교",
        "school_type": "초등학교",
        "address": "서울 마포구 잔다리로 71",
        "lat": 37.5532,
        "lon": 126.9217,
        "district": "서교동",
    },
    {
        "name": "공덕초등학교",
        "school_type": "초등학교",
        "address": "서울 마포구 공덕동 256",
        "lat": 37.5435,
        "lon": 126.9519,
        "district": "공덕동",
    },
    {
        "name": "홍익대학교",
        "school_type": "대학교",
        "address": "서울 마포구 와우산로 94",
        "lat": 37.5511,
        "lon": 126.9249,
        "district": "서교동",
    },
]


def _classify_school_type(name: str) -> str | None:
    """학교 이름에서 유형 추출."""
    if not name:
        return None
    if "초등학교" in name or "초교" in name:
        return "초등학교"
    if "중학교" in name:
        return "중학교"
    if "고등학교" in name or "고교" in name:
        return "고등학교"
    if "대학교" in name or "대학원" in name:
        return "대학교"
    if "유치원" in name:
        return "유치원"
    if "특수학교" in name:
        return "특수학교"
    return None


def _is_school_category(category_name: str, category_group_code: str) -> bool:
    """카카오 카테고리에서 학교 여부 판정."""
    if category_group_code == "SC4":
        return True
    return "학교" in (category_name or "")


def _fetch_kakao_schools(lat: float, lon: float, radius: int = 2000) -> list[dict]:
    """카카오 Local keyword.json — query=학교, radius=2000m.

    KAKAO_API_KEY 미설정 시 빈 리스트 반환 (호출자 fallback).
    """
    if not KAKAO_API_KEY:
        return []
    try:
        import requests
    except ImportError:  # pragma: no cover
        print("[ingest] requests 모듈 없음 — mock fallback")
        return []

    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    out: list[dict] = []
    page = 1
    while page <= 3:  # max 3 pages (45개)
        params = {
            "query": "학교",
            "x": str(lon),
            "y": str(lat),
            "radius": str(radius),
            "page": str(page),
            "size": "15",
        }
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code != 200:
                print(f"[ingest] kakao API HTTP {resp.status_code}: {resp.text[:200]}")
                break
            data = resp.json()
        except Exception as e:
            print(f"[ingest] kakao API 호출 실패: {e}")
            break

        docs = data.get("documents", [])
        for d in docs:
            cat_name = d.get("category_name", "")
            cat_group = d.get("category_group_code", "")
            if not _is_school_category(cat_name, cat_group):
                continue
            try:
                out.append({
                    "name": d.get("place_name", ""),
                    "school_type": _classify_school_type(d.get("place_name", "")),
                    "address": d.get("road_address_name") or d.get("address_name", ""),
                    "lat": float(d["y"]),
                    "lon": float(d["x"]),
                })
            except (KeyError, ValueError, TypeError):
                continue

        meta = data.get("meta", {})
        if meta.get("is_end", True):
            break
        page += 1

    return out


def _load_mapo_dong_centroids() -> list[tuple[str, float, float]]:
    """dong_centroid 테이블에서 마포 16동 (dong_name, lat, lon) 조회."""
    from sqlalchemy import text

    from src.database.sync_engine import get_sync_engine

    sql = text(
        """
        SELECT dong_name, lat, lon
          FROM dong_centroid
         WHERE dong_code LIKE '11440%'
           AND lat IS NOT NULL AND lon IS NOT NULL
        ORDER BY dong_code
        """
    )
    engine = get_sync_engine(POSTGRES_URL)
    with engine.connect() as conn:
        rows = conn.execute(sql).fetchall()
    return [(r[0], float(r[1]), float(r[2])) for r in rows if r[0]]


def _upsert_schools(records: list[dict]) -> int:
    """mapo_schools UPSERT — UNIQUE(name, lat, lon)."""
    if not records:
        return 0
    from sqlalchemy import text

    from src.database.sync_engine import get_sync_engine

    sql = text(
        """
        INSERT INTO mapo_schools
            (name, school_type, address, lat, lon, district, fetched_at)
        VALUES
            (:name, :school_type, :address, :lat, :lon, :district, NOW())
        ON CONFLICT (name, lat, lon) DO UPDATE SET
            school_type = EXCLUDED.school_type,
            address     = EXCLUDED.address,
            district    = EXCLUDED.district,
            fetched_at  = NOW()
        """
    )
    engine = get_sync_engine(POSTGRES_URL)
    inserted = 0
    with engine.begin() as conn:
        for r in records:
            try:
                conn.execute(sql, r)
                inserted += 1
            except Exception as e:
                print(f"[ingest] upsert 실패 ({r.get('name')}): {e}")
    return inserted


def main() -> None:
    print(f"[ingest] KAKAO_API_KEY={'set' if KAKAO_API_KEY else 'MISSING'}")
    if not KAKAO_API_KEY:
        print("[ingest] KAKAO_API_KEY 미설정 → mock 5개 적재")
        n = _upsert_schools(_MOCK_SCHOOLS)
        print(f"[ingest] mock 적재 완료: {n} 건")
        return

    try:
        centroids = _load_mapo_dong_centroids()
    except Exception as e:
        print(f"[ingest] dong_centroid 조회 실패 → mock fallback: {e}")
        n = _upsert_schools(_MOCK_SCHOOLS)
        print(f"[ingest] mock 적재 완료: {n} 건")
        return

    if not centroids:
        print("[ingest] dong_centroid 결과 없음 → mock fallback")
        n = _upsert_schools(_MOCK_SCHOOLS)
        print(f"[ingest] mock 적재 완료: {n} 건")
        return

    seen_keys: set[tuple[str, float, float]] = set()
    all_records: list[dict] = []
    for dong_name, lat, lon in centroids:
        if not dong_name:
            continue
        results = _fetch_kakao_schools(lat, lon, radius=2000)
        for s in results:
            key = (s["name"], round(s["lat"], 6), round(s["lon"], 6))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            all_records.append({**s, "district": dong_name})
        print(f"[ingest] {dong_name}: {len(results)} 학교")

    n = _upsert_schools(all_records)
    print(f"[ingest] kakao 적재 완료: {n} / {len(all_records)} 건")


if __name__ == "__main__":
    main()
