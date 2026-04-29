"""지하철 승하차 raw CSV → seed CSV 정제.

입력  : data.seoul.go.kr / 서울교통공사 (사용일자/호선명/역명/승차총승객수/하차총승객수)
출력  : seed/cleaned/seoul_subway_passenger_daily_<ym>.csv
        seed/cleaned/master_subway_station_<ym>.csv  (해당 월에서 발견된 역)
       (옵션) seed/reject/subway_<ym>.csv

호선명이 _VALID_LINES 화이트리스트에 없으면 reject.
역코드는 (호선 + 역명) sha1 hash 앞 10자리로 surrogate (운영사별 코드 통합 이슈 회피).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

from src.ingest import _common as C


_VALID_LINES = {
    "1호선",
    "2호선",
    "3호선",
    "4호선",
    "5호선",
    "6호선",
    "7호선",
    "8호선",
    "9호선",
    "공항철도",
    "경의중앙선",
    "수인분당선",
    "신분당선",
    "우이신설선",
    "경춘선",
    "경강선",
    "서해선",
    "GTX-A",
}


def _surrogate_code(station_name: str, line_name: str) -> str:
    h = hashlib.sha1(f"{station_name}|{line_name}".encode("utf-8")).hexdigest()
    return h[:10]


def _read_csv_any_encoding(path: Path) -> list[dict]:
    last_err: Exception | None = None
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            with path.open(encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError as e:
            last_err = e
    raise RuntimeError(f"unable to decode {path}: {last_err}")


def ingest_one_csv(
    src: Path,
    *,
    cleaned_dir: Path,
    reject_dir: Path,
    ym_tag: str,
) -> dict[str, Path]:
    cleaned_dir.mkdir(parents=True, exist_ok=True)
    rows = _read_csv_any_encoding(src)

    passenger_rows: list[dict] = []
    master_seen: dict[str, dict] = {}
    rejects: list[dict] = []

    for r in rows:
        line = (r.get("호선명") or "").strip()
        name = (r.get("역명") or "").strip()
        date_raw = (r.get("사용일자") or "").strip()
        if not name or not line or not date_raw:
            rejects.append({**r, "_reason": "missing line/name/date"})
            continue
        if line not in _VALID_LINES:
            rejects.append({"station_name": name, "line_name": line, "_reason": "unknown line"})
            continue
        if len(date_raw) != 8 or not date_raw.isdigit():
            rejects.append({**r, "_reason": "invalid date format"})
            continue

        date_iso = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:8]}"
        code = _surrogate_code(name, line)
        boarding = C.parse_int_safe(r.get("승차총승객수")) or 0
        alighting = C.parse_int_safe(r.get("하차총승객수")) or 0

        passenger_rows.append(
            {
                "date": date_iso,
                "station_code": code,
                "boarding_cnt": boarding,
                "alighting_cnt": alighting,
            }
        )
        if code not in master_seen:
            master_seen[code] = {
                "station_code": code,
                "station_name": name,
                "line_name": line,
                "sigungu_code": "",
                "lat": "",
                "lon": "",
            }

    out_passenger = cleaned_dir / f"seoul_subway_passenger_daily_{ym_tag}.csv"
    out_master = cleaned_dir / f"master_subway_station_{ym_tag}.csv"
    _write_csv(
        out_passenger,
        passenger_rows,
        ["date", "station_code", "boarding_cnt", "alighting_cnt"],
    )
    _write_csv(
        out_master,
        list(master_seen.values()),
        ["station_code", "station_name", "line_name", "sigungu_code", "lat", "lon"],
    )

    result: dict[str, Path] = {"passenger": out_passenger, "master": out_master}
    reject_path = C.write_reject_csv(reject_dir, f"subway_{ym_tag}", rejects)
    if reject_path is not None:
        result["reject"] = reject_path
    return result


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--cleaned-dir", type=Path, required=True)
    parser.add_argument("--reject-dir", type=Path, required=True)
    args = parser.parse_args()

    for src in sorted(args.raw_dir.glob("*.csv")):
        ym = src.stem[-6:] if src.stem[-6:].isdigit() else "unknown"
        ingest_one_csv(
            src,
            cleaned_dir=args.cleaned_dir,
            reject_dir=args.reject_dir,
            ym_tag=ym,
        )


if __name__ == "__main__":
    main()
