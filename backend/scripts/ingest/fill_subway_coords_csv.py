"""seed CSV (master_subway_station_all.csv) 의 마포 행에 좌표 in-place 업데이트.

DB UPDATE 와 별개로 seed CSV truth 도 같이 갱신 — 재배포/DB 재생성 시 빈 좌표 재출하 방지.

매칭 로직은 fill_subway_coords.py 와 동일.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from scripts.ingest.fill_subway_coords import MAPO_STATIONS, _load_raw, _normalize


def update_csv(seed_path: Path, raw_path: Path, dry_run: bool) -> int:
    if not seed_path.exists():
        print(f"[csv] seed missing: {seed_path}", file=sys.stderr)
        return 2
    if not raw_path.exists():
        print(f"[csv] raw missing: {raw_path}", file=sys.stderr)
        return 2

    by_pair, by_name = _load_raw(raw_path)
    target = {(s, ln) for s, ln in MAPO_STATIONS}

    rows: list[dict] = []
    fieldnames: list[str] = []
    with seed_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    updated = 0
    for row in rows:
        key = (row["station_name"].strip(), row["line_name"].strip())
        if key not in target:
            continue
        norm = _normalize(key[0])
        coord = by_pair.get((norm, key[1])) or by_name.get(norm)
        if coord is None:
            continue
        new_lat, new_lon = coord
        if row.get("lat") != f"{new_lat:.7f}" or row.get("lon") != f"{new_lon:.7f}":
            row["lat"] = f"{new_lat:.7f}"
            row["lon"] = f"{new_lon:.7f}"
            row["sigungu_code"] = "11440"
            updated += 1

    print(f"[csv] mapo rows updated in-memory: {updated}/14")

    if dry_run:
        print("[csv] dry-run - file not written")
        return 0

    with seed_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"[csv] wrote: {seed_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--seed",
        type=Path,
        default=Path("data/seed/master_subway_station_all.csv"),
    )
    parser.add_argument(
        "--raw",
        type=Path,
        default=Path("data/seed/raw/seoul_subway_stations_with_coords.csv"),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    return update_csv(args.seed, args.raw, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
