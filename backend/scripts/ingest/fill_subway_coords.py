"""master_subway_station 좌표 채우기 (마포 한정).

소스: backend/data/seed/raw/seoul_subway_stations_with_coords.csv
  - 서울 1~9호선 역사 좌표 CSV (yoon-gu gist, Naver API 기반)
  - 컬럼: lat,lon,name(역명+'역' 접미),no_line(숫자)

매칭: (정규화 station_name, line_name) → master_subway_station UPDATE.
정규화: 괄호 부속 명칭 제거('월드컵경기장(성산)' → '월드컵경기장'), '역' 접미 제거, trim.
범위: 마포 14역 (sigungu_code='11440' 인 행 + master 의 마포 환승역).

사용법:
    cd backend
    python -m scripts.ingest.fill_subway_coords --dry-run   # 매칭만 보고 DB 미수정
    python -m scripts.ingest.fill_subway_coords             # 실제 UPDATE
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

# repo root .env auto-load (settings.py 와 동일 패턴) — backend/scripts/ingest/X.py → parents[3]
_REPO_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
if _REPO_ROOT_ENV.exists():
    load_dotenv(_REPO_ROOT_ENV)

_DEFAULT_DB_URL = os.environ.get(
    "POSTGRES_URL",
    "postgresql://postgres:postgres@localhost:5432/mapo_simulator",
)

# 마포 14역 — master_subway_station 의 (station_name, line_name) 그대로 (괄호 포함).
# UPDATE 의 WHERE 절에 station_name 원본 그대로 사용해야 함.
MAPO_STATIONS: list[tuple[str, str]] = [
    ("합정", "2호선"),
    ("홍대입구", "2호선"),
    ("마포", "5호선"),
    ("공덕", "5호선"),
    ("애오개", "5호선"),
    ("디지털미디어시티", "6호선"),
    ("월드컵경기장(성산)", "6호선"),
    ("마포구청", "6호선"),
    ("망원", "6호선"),
    ("합정", "6호선"),
    ("상수", "6호선"),
    ("광흥창(서강)", "6호선"),
    ("대흥(서강대앞)", "6호선"),
    ("공덕", "6호선"),
]

_PAREN_RE = re.compile(r"\(.*?\)")


def _normalize(name: str) -> str:
    s = _PAREN_RE.sub("", name).strip()
    if s.endswith("역"):
        s = s[:-1]
    return s.strip()


def _load_raw(
    path: Path,
) -> tuple[dict[tuple[str, str], tuple[float, float]], dict[str, tuple[float, float]]]:
    by_pair: dict[tuple[str, str], tuple[float, float]] = {}
    by_name: dict[str, tuple[float, float]] = {}
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
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


def fill(raw_path: Path, db_url: str, dry_run: bool) -> int:
    if not raw_path.exists():
        print(f"[fill] ERROR: raw CSV not found: {raw_path}", file=sys.stderr)
        return 2

    by_pair, by_name = _load_raw(raw_path)
    print(f"[fill] raw stations loaded: pairs={len(by_pair)} unique_names={len(by_name)}")

    matched: list[dict] = []
    rejects: list[dict] = []

    for station_name, line_name in MAPO_STATIONS:
        norm = _normalize(station_name)
        coord = by_pair.get((norm, line_name)) or by_name.get(norm)
        if coord is None:
            rejects.append(
                {
                    "station_name": station_name,
                    "line_name": line_name,
                    "_reason": "no match in raw CSV",
                }
            )
            continue
        matched.append(
            {
                "station_name": station_name,
                "line_name": line_name,
                "lat": coord[0],
                "lon": coord[1],
                "_match": "exact" if (norm, line_name) in by_pair else "name_fallback",
            }
        )

    print(f"[fill] matched={len(matched)}/{len(MAPO_STATIONS)}, rejects={len(rejects)}")
    for m in matched:
        print(f"  {m['station_name']:<14} {m['line_name']}  lat={m['lat']:.6f} lon={m['lon']:.6f}  ({m['_match']})")
    for r in rejects:
        print(f"  REJECT: {r}")

    if dry_run:
        print("[fill] dry-run - DB not modified")
        return 0

    url = db_url.replace("+asyncpg", "").replace("+psycopg", "")
    updated = 0
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            for m in matched:
                cur.execute(
                    """
                    UPDATE master_subway_station
                    SET lat = %s, lon = %s, sigungu_code = '11440'
                    WHERE station_name = %s AND line_name = %s
                    """,
                    (m["lat"], m["lon"], m["station_name"], m["line_name"]),
                )
                if cur.rowcount == 0:
                    rejects.append(
                        {
                            "station_name": m["station_name"],
                            "line_name": m["line_name"],
                            "_reason": "DB row not found",
                        }
                    )
                else:
                    updated += cur.rowcount
        conn.commit()

    print(f"[fill] DB updated rows: {updated}")

    if rejects:
        reject_dir = Path("backend/data/cleaned/reject")
        reject_dir.mkdir(parents=True, exist_ok=True)
        reject_path = reject_dir / "subway_coords_unmatched.csv"
        with reject_path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["station_name", "line_name", "_reason"])
            w.writeheader()
            w.writerows(rejects)
        print(f"[fill] rejects: {reject_path}")

    return 0 if updated == len(MAPO_STATIONS) else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--raw",
        type=Path,
        default=Path("backend/data/seed/raw/seoul_subway_stations_with_coords.csv"),
    )
    parser.add_argument("--db-url", default=_DEFAULT_DB_URL)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    return fill(args.raw, args.db_url, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
