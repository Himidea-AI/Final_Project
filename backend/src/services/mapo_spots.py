"""마포 동 별 대표 spot — ABM 시각화 frontend (`AbmPersonaMap`) 용.

데이터 소스:
    - data/processed/dong_subway_access.csv — 동 centroid + nearest_subway
    - data/processed/store_info_mapo.csv — 마포 매장 좌표 (랜덤 샘플)

설계 의도:
    AbmPersonaMap 의 일반 모드 (`mode="general"`) 가 호출하는
    /mapo/spots/{dong_name} endpoint 의 데이터 source.
    동 별 4개 spot (지하철역 + 매장 3개) 좌표 반환.
"""

from __future__ import annotations

import csv
import random
from functools import lru_cache
from pathlib import Path
from typing import Any

# 프로젝트 root = backend/../
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SUBWAY_CSV = _PROJECT_ROOT / "data" / "processed" / "dong_subway_access.csv"
_STORE_CSV = _PROJECT_ROOT / "data" / "processed" / "store_info_mapo.csv"

# 마포 fallback centroid (data 미존재 시)
_MAPO_FALLBACK_CENTER = {"lat": 37.558, "lng": 126.919}


@lru_cache(maxsize=1)
def _load_subway_centroids() -> dict[str, dict[str, Any]]:
    """동 이름 → {center_lat, center_lon, nearest_subway} dict."""
    out: dict[str, dict[str, Any]] = {}
    if not _SUBWAY_CSV.exists():
        return out
    with open(_SUBWAY_CSV, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            try:
                code = row["dong_code"]
                if not code.startswith("1144"):
                    continue
                out[row["dong_name"]] = {
                    "center_lat": float(row["center_lat"]),
                    "center_lon": float(row["center_lon"]),
                    "nearest_subway": row.get("nearest_subway", ""),
                }
            except (KeyError, ValueError):
                continue
    return out


@lru_cache(maxsize=1)
def _load_stores_by_dong() -> dict[str, list[dict[str, Any]]]:
    """동 이름 → 매장 list ({label, lat, lng, category})."""
    out: dict[str, list[dict[str, Any]]] = {}
    if not _STORE_CSV.exists():
        return out
    with open(_STORE_CSV, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            try:
                dong = row.get("행정동명", "").strip()
                if not dong:
                    continue
                lat = float(row["위도"])
                lng = float(row["경도"])
                label = row.get("상호명", "")
                category = row.get("상권업종중분류명", "기타")
                out.setdefault(dong, []).append(
                    {
                        "label": label,
                        "lat": lat,
                        "lng": lng,
                        "category": category,
                    }
                )
            except (KeyError, ValueError):
                continue
    return out


def get_dong_spots(dong_name: str, limit: int = 4) -> list[dict[str, Any]]:
    """동 이름 → 대표 spot N개 (지하철역 1 + 매장 N-1).

    Args:
        dong_name: 마포 행정동명 (예: "공덕동").
        limit: 반환 spot 수 (default 4).

    Returns:
        [{id, label, lat, lng, tier}, ...]. 데이터 부재 시 fallback 단일 spot.
    """
    spots: list[dict[str, Any]] = []

    centroids = _load_subway_centroids()
    centroid = centroids.get(dong_name)
    if centroid:
        spots.append(
            {
                "id": f"subway_{dong_name}",
                "label": centroid.get("nearest_subway") or f"{dong_name} 중심",
                "lat": centroid["center_lat"],
                "lng": centroid["center_lon"],
                "tier": "S",
            }
        )

    # 매장 limit-1 개 sample
    n_stores = max(0, limit - len(spots))
    stores = _load_stores_by_dong().get(dong_name, [])
    if stores and n_stores > 0:
        rng = random.Random(hash(dong_name) % (2**32))
        sampled = rng.sample(stores, min(n_stores, len(stores)))
        for i, s in enumerate(sampled):
            spots.append(
                {
                    "id": f"store_{dong_name}_{i}",
                    "label": s["label"][:20] or f"{dong_name} 매장 {i + 1}",
                    "lat": s["lat"],
                    "lng": s["lng"],
                    "tier": "A" if i == 0 else "B",
                }
            )

    if not spots:
        spots.append(
            {
                "id": f"fallback_{dong_name}",
                "label": dong_name or "마포 중심",
                "lat": _MAPO_FALLBACK_CENTER["lat"],
                "lng": _MAPO_FALLBACK_CENTER["lng"],
                "tier": "S",
            }
        )

    return spots[:limit]


def get_all_mapo_spots(per_dong: int = 3) -> list[dict[str, Any]]:
    """마포 16동 전체 spot pool — ABM 시각화의 마포 전체 dot spread 용.

    Args:
        per_dong: 동 별 spot 수 (default 3, 16동 × 3 = 48 spot).

    Returns:
        [{id, label, lat, lng, tier}, ...] 마포 16동 전체 합집합.
        지하철 centroid (S tier) 1개 + 매장 (A/B tier) per_dong-1 개 / 동.
    """
    centroids = _load_subway_centroids()
    all_spots: list[dict[str, Any]] = []
    for dong_name in centroids.keys():
        all_spots.extend(get_dong_spots(dong_name, limit=per_dong))
    return all_spots
