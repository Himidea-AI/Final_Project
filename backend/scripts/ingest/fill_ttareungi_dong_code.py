"""master_ttareungi_station.dong_code 채우기 (마포 한정).

PR #184 가 ttareungi station 의 lat/lon + sigungu_code 채움 (3,230 row API 매핑).
본 스크립트는 그 결과 위에서 마포(sigungu_code='11440') station 의 dong_code 를
``dong_centroid`` 16 동과의 haversine 거리 비교로 매핑.

- 마포 station: 가장 가까운 dong_centroid → dong_code 적용
- 마포 외 station: 서울 전체 dong_centroid 부재 (E4 한계) — skip
- ``opened_at`` 컬럼: 따릉이 API 응답에 없음 — skip

사용법:
    cd backend && python scripts/ingest/fill_ttareungi_dong_code.py

idempotent — dong_code 이미 채워진 row 는 skip.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import sqlalchemy as sa

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.config.settings import settings  # noqa: E402


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 좌표 간 거리 (미터)."""
    radius = 6371000  # Earth radius m
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlon / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def main() -> None:
    engine = sa.create_engine(settings.postgres_url)

    with engine.connect() as conn:
        centroids = conn.execute(
            sa.text("SELECT dong_code, lat, lon FROM dong_centroid WHERE lat IS NOT NULL")
        ).fetchall()
        cents = [(r._mapping["dong_code"], r._mapping["lat"], r._mapping["lon"]) for r in centroids]
        print(f"dong_centroid: {len(cents)} 동")

        rows = conn.execute(
            sa.text(
                "SELECT station_id, lat, lon FROM master_ttareungi_station "
                "WHERE sigungu_code='11440' AND dong_code IS NULL AND lat IS NOT NULL"
            )
        ).fetchall()
        print(f"마포 ttareungi (dong_code NULL): {len(rows)}")

    matched: list[tuple[str, str]] = []
    for r in rows:
        sid = r._mapping["station_id"]
        lat = r._mapping["lat"]
        lon = r._mapping["lon"]
        best = min(cents, key=lambda c: _haversine_m(lat, lon, c[1], c[2]))
        matched.append((sid, best[0]))

    print(f"matched: {len(matched)}")

    with engine.begin() as conn:
        for sid, dc in matched:
            conn.execute(
                sa.text("UPDATE master_ttareungi_station SET dong_code=:dc WHERE station_id=:sid"),
                {"dc": dc, "sid": sid},
            )

    with engine.connect() as conn:
        total = conn.execute(sa.text("SELECT COUNT(*) FROM master_ttareungi_station")).scalar()
        null_dc = conn.execute(
            sa.text("SELECT COUNT(*) FROM master_ttareungi_station WHERE dong_code IS NULL")
        ).scalar()
        mapo_filled = conn.execute(
            sa.text(
                "SELECT COUNT(*) FROM master_ttareungi_station WHERE sigungu_code='11440' AND dong_code IS NOT NULL"
            )
        ).scalar()

    print()
    print("=== AFTER ===")
    print(f"  total {total}, dong_code NULL {null_dc} ({null_dc / total * 100:.1f}%)")
    print(f"  마포 dong_code 채워짐: {mapo_filled}")
    print()
    print("미적재 사유 (마포 외 5,298 row):")
    print("  서울 전체 dong_centroid 부재 (E4 한계). DongCentroid 서울 확장 별 PR 필요.")


if __name__ == "__main__":
    main()
