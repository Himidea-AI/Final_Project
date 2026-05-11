"""master_subway_station 좌표 채우기 (서울 전체).

기존 ``fill_subway_coords.py`` 는 마포 14역 한정. 본 스크립트는 CSV 의 모든 서울 역
(1~9호선) 을 매칭해 lat NULL 인 row 를 일괄 UPDATE.

소스: backend/data/seed/raw/seoul_subway_stations_with_coords.csv (yoon-gu gist).
매칭: (정규화 station_name, line_name) → master_subway_station UPDATE.
정규화: 괄호 부속 명칭 제거, '역' 접미 제거, trim.

사용법:
    cd backend && python scripts/ingest/fill_subway_coords_seoul.py
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import sqlalchemy as sa

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.config.settings import settings  # noqa: E402

CSV_PATH = Path(__file__).resolve().parents[2] / "data/seed/raw/seoul_subway_stations_with_coords.csv"

_PAREN_RE = re.compile(r"\(.*?\)")


def _normalize(name: str) -> str:
    s = _PAREN_RE.sub("", name).strip()
    if s.endswith("역"):
        s = s[:-1]
    return s.strip()


def _load_csv() -> tuple[dict, dict]:
    by_pair: dict = {}
    by_name: dict = {}
    with CSV_PATH.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                norm = _normalize(row["name"])
                line = f"{int(row['no_line'].strip())}호선"
                lat = float(row["lat"])
                lon = float(row["lon"])
            except (ValueError, KeyError):
                continue
            by_pair[(norm, line)] = (lat, lon)
            by_name.setdefault(norm, (lat, lon))
    return by_pair, by_name


def main() -> None:
    by_pair, by_name = _load_csv()
    print(f"CSV loaded: pairs={len(by_pair)}, unique_names={len(by_name)}")

    engine = sa.create_engine(settings.postgres_url)
    with engine.connect() as conn:
        rows = conn.execute(
            sa.text("SELECT station_code, station_name, line_name FROM master_subway_station WHERE lat IS NULL")
        ).fetchall()
    print(f"DB rows lat NULL: {len(rows)}")

    matched, rejected = [], []
    for code, name, line in rows:
        norm = _normalize(name)
        coord = by_pair.get((norm, line)) or by_name.get(norm)
        if coord:
            matched.append((code, coord[0], coord[1]))
        else:
            rejected.append((code, name, line))

    print(f"matched: {len(matched)}, rejected: {len(rejected)}")
    for r in rejected[:10]:
        print(" ", r)

    with engine.begin() as conn:
        for code, lat, lon in matched:
            conn.execute(
                sa.text("UPDATE master_subway_station SET lat=:lat, lon=:lon WHERE station_code=:code"),
                {"lat": lat, "lon": lon, "code": code},
            )

    with engine.connect() as conn:
        total = conn.execute(sa.text("SELECT COUNT(*) FROM master_subway_station")).scalar()
        null_n = conn.execute(sa.text("SELECT COUNT(*) FROM master_subway_station WHERE lat IS NULL")).scalar()
    print(f"\n=== AFTER ===\n  total {total}, lat NULL {null_n}, filled {total - null_n}")


if __name__ == "__main__":
    main()
