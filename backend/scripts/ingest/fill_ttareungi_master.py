"""master_ttareungi_station 좌표 + sigungu_code 채우기.

서울 열린데이터 광장 ``tbCycleStationInfo`` API 호출 → ``RENT_NO`` (대여소번호) /
``RENT_ID`` (ST-XXX) / station_name prefix 번호 multi-key 매칭으로 DB 의
station_id 와 매핑.

3,230 row API × 5,541 row DB → 99.9% 채움 (3건 폐쇄/AS센터 제외).
sigungu_code 는 ``STA_LOC`` (예: '마포구') → 25개 자치구 코드 (11xxx) 매핑.

사용법:
    cd backend && python scripts/ingest/fill_ttareungi_master.py
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import httpx
import sqlalchemy as sa

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.config.settings import settings  # noqa: E402

PAGE = 1000

# 서울 25개 자치구 코드 (행정안전부 표준)
SIGUNGU_CODE = {
    "종로구": "11110",
    "중구": "11140",
    "용산구": "11170",
    "성동구": "11200",
    "광진구": "11215",
    "동대문구": "11230",
    "중랑구": "11260",
    "성북구": "11290",
    "강북구": "11305",
    "도봉구": "11320",
    "노원구": "11350",
    "은평구": "11380",
    "서대문구": "11410",
    "마포구": "11440",
    "양천구": "11470",
    "강서구": "11500",
    "구로구": "11530",
    "금천구": "11545",
    "영등포구": "11560",
    "동작구": "11590",
    "관악구": "11620",
    "서초구": "11650",
    "강남구": "11680",
    "송파구": "11710",
    "강동구": "11740",
}

_PREFIX_RE = re.compile(r"^\s*(\d+)\.\s*")


def _fetch_all() -> list[dict]:
    key = settings.seoul_opendata_key
    if not key:
        raise RuntimeError("SEOUL_OPENDATA_KEY missing in settings")
    rows: list[dict] = []
    start = 1
    while True:
        url = f"http://openapi.seoul.go.kr:8088/{key}/json/tbCycleStationInfo/{start}/{start + PAGE - 1}/"
        block = httpx.get(url, timeout=30).json().get("stationInfo")
        if not block or not block.get("row"):
            break
        rows.extend(block["row"])
        if len(block["row"]) < PAGE:
            break
        start += PAGE
        time.sleep(0.3)
    return rows


def _build_map(api_rows: list[dict]) -> dict[str, tuple[float, float, str | None]]:
    """multi-key map: RENT_NO/RENT_ID/prefix → (lat, lon, sigungu)."""
    out: dict[str, tuple[float, float, str | None]] = {}
    for row in api_rows:
        try:
            lat = float(row["STA_LAT"])
            lon = float(row["STA_LONG"])
        except (ValueError, KeyError, TypeError):
            continue
        sig = SIGUNGU_CODE.get(str(row.get("STA_LOC") or "").strip())
        val = (lat, lon, sig)
        rent_no = str(row.get("RENT_NO") or "").strip()
        rent_id = str(row.get("RENT_ID") or "").strip()
        rent_id_nm = str(row.get("RENT_ID_NM") or "").strip()
        for k in [rent_no, rent_no.lstrip("0"), rent_no.zfill(5), rent_id]:
            if k:
                out[k] = val
        if "." in rent_id_nm:
            pfx = rent_id_nm.split(".")[0].strip()
            out[pfx] = val
            out[pfx.zfill(5)] = val
    return out


def main() -> None:
    print("Fetching tbCycleStationInfo...")
    api_rows = _fetch_all()
    print(f"  fetched: {len(api_rows)}")
    api_map = _build_map(api_rows)
    print(f"  multi-key map size: {len(api_map)}")

    engine = sa.create_engine(settings.postgres_url)
    with engine.connect() as conn:
        rows = conn.execute(
            sa.text(
                "SELECT station_id, station_name FROM master_ttareungi_station "
                "WHERE lat IS NULL OR sigungu_code IS NULL"
            )
        ).fetchall()
    print(f"DB rows needing fill: {len(rows)}")

    matched: list[tuple[str, float, float, str | None]] = []
    unmatched: list[tuple[str, str]] = []
    for sid, sn in rows:
        candidates = [sid, sid.zfill(5), sid.lstrip("0")]
        m = _PREFIX_RE.match(sn or "")
        if m:
            pfx = m.group(1)
            candidates += [pfx, pfx.zfill(5)]
        found = None
        for k in candidates:
            if k in api_map:
                found = api_map[k]
                break
        if found:
            matched.append((sid, *found))
        else:
            unmatched.append((sid, sn))

    print(f"matched: {len(matched)}, unmatched: {len(unmatched)}")

    with engine.begin() as conn:
        for sid, lat, lon, sig in matched:
            conn.execute(
                sa.text(
                    "UPDATE master_ttareungi_station SET lat=:lat, lon=:lon, "
                    "sigungu_code=COALESCE(:sig, sigungu_code) WHERE station_id=:sid"
                ),
                {"lat": lat, "lon": lon, "sig": sig, "sid": sid},
            )

    with engine.connect() as conn:
        total = conn.execute(sa.text("SELECT COUNT(*) FROM master_ttareungi_station")).scalar()
        null_lat = conn.execute(sa.text("SELECT COUNT(*) FROM master_ttareungi_station WHERE lat IS NULL")).scalar()
        null_sig = conn.execute(
            sa.text("SELECT COUNT(*) FROM master_ttareungi_station WHERE sigungu_code IS NULL")
        ).scalar()
    print("\n=== AFTER ===")
    print(f"  total {total}")
    pct_lat = (null_lat / total * 100) if total else 0
    pct_sig = (null_sig / total * 100) if total else 0
    print(f"  lat NULL: {null_lat} ({pct_lat:.1f}%)")
    print(f"  sigungu_code NULL: {null_sig} ({pct_sig:.1f}%)")


if __name__ == "__main__":
    main()
