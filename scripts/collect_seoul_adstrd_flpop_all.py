"""
seoul_adstrd_flpop 전수(25 자치구) 재수집.

원인: scripts/collect_seoul_commercial_5.py 가 마포(11440) prefix 만 필터링했음.
해결: VwsmAdstrdFlpopW OpenAPI 에서 서울 전체를 수집하여 ON CONFLICT DO NOTHING 으로 적재.

실행: python scripts/collect_seoul_adstrd_flpop_all.py
"""

from __future__ import annotations

import asyncio
import os
import sys

import httpx
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(".env")

DB_URL = os.environ["POSTGRES_URL"]
KEY = os.environ["SEOUL_OPENDATA_KEY"].strip()
SVC = "VwsmAdstrdFlpopW"
TABLE = "seoul_adstrd_flpop"
PAGE_SIZE = 1000


def to_int(v):
    try:
        return int(float(v)) if v not in (None, "", "null") else None
    except (TypeError, ValueError):
        return None


def map_row(r: dict) -> dict:
    return {
        "quarter": to_int(r.get("STDR_YYQU_CD")),
        "dong_code": str(r.get("ADSTRD_CD") or ""),
        "dong_name": r.get("ADSTRD_CD_NM"),
        "total_flpop": to_int(r.get("TOT_FLPOP_CO")),
        "male_flpop": to_int(r.get("ML_FLPOP_CO")),
        "female_flpop": to_int(r.get("FML_FLPOP_CO")),
        "age_10": to_int(r.get("AGRDE_10_FLPOP_CO")),
        "age_20": to_int(r.get("AGRDE_20_FLPOP_CO")),
        "age_30": to_int(r.get("AGRDE_30_FLPOP_CO")),
        "age_40": to_int(r.get("AGRDE_40_FLPOP_CO")),
        "age_50": to_int(r.get("AGRDE_50_FLPOP_CO")),
        "age_60_above": to_int(r.get("AGRDE_60_ABOVE_FLPOP_CO")),
        "time_00_06": to_int(r.get("TMZON_00_06_FLPOP_CO")),
        "time_06_11": to_int(r.get("TMZON_06_11_FLPOP_CO")),
        "time_11_14": to_int(r.get("TMZON_11_14_FLPOP_CO")),
        "time_14_17": to_int(r.get("TMZON_14_17_FLPOP_CO")),
        "time_17_21": to_int(r.get("TMZON_17_21_FLPOP_CO")),
        "time_21_24": to_int(r.get("TMZON_21_24_FLPOP_CO")),
        "mon": to_int(r.get("MON_FLPOP_CO")),
        "tue": to_int(r.get("TUES_FLPOP_CO")),
        "wed": to_int(r.get("WED_FLPOP_CO")),
        "thu": to_int(r.get("THUR_FLPOP_CO")),
        "fri": to_int(r.get("FRI_FLPOP_CO")),
        "sat": to_int(r.get("SAT_FLPOP_CO")),
        "sun": to_int(r.get("SUN_FLPOP_CO")),
    }


async def fetch_page(client: httpx.AsyncClient, start: int, end: int) -> list[dict]:
    url = f"http://openapi.seoul.go.kr:8088/{KEY}/json/{SVC}/{start}/{end}"
    for attempt in range(3):
        try:
            r = await client.get(url, timeout=30)
            d = r.json()
            return d.get(SVC, {}).get("row", []) or []
        except Exception as e:
            if attempt == 2:
                raise
            await asyncio.sleep(1.0)
            print(f"  [retry {attempt + 1}] page {start}: {e}", flush=True)
    return []


async def main() -> int:
    eng = create_engine(DB_URL, pool_size=1, max_overflow=0)

    # 수집 전 상태
    with eng.connect() as c:
        pre_total = c.execute(text(f"SELECT COUNT(*) FROM {TABLE}")).scalar()
        pre_gus = c.execute(text(f"SELECT COUNT(DISTINCT LEFT(dong_code,5)) FROM {TABLE}")).scalar()
    print(f"=== 수집 전: {pre_total:,}행 / {pre_gus}자치구 ===", flush=True)

    async with httpx.AsyncClient() as client:
        r = await client.get(f"http://openapi.seoul.go.kr:8088/{KEY}/json/{SVC}/1/1", timeout=15)
        total = r.json().get(SVC, {}).get("list_total_count", 0)
        print(f"API 전체 row 수: {total:,}", flush=True)

        all_rows: list[dict] = []
        for start in range(1, total + 1, PAGE_SIZE):
            end = min(start + PAGE_SIZE - 1, total)
            rows = await fetch_page(client, start, end)
            mapped = []
            for row in rows:
                m = map_row(row)
                if m.get("quarter") and m.get("dong_code"):
                    mapped.append(m)
            all_rows.extend(mapped)
            print(
                f"  [page {start:>5}~{end:>5}] fetched={len(rows):>4}, "
                f"mapped={len(mapped):>4}, total={len(all_rows):,}",
                flush=True,
            )

    print(f"\n수집 완료: {len(all_rows):,}행", flush=True)

    # UPSERT
    cols = list(all_rows[0].keys())
    col_list = ", ".join(cols)
    param_list = ", ".join(f":{c}" for c in cols)
    sql = text(f"INSERT INTO {TABLE} ({col_list}) VALUES ({param_list}) ON CONFLICT (quarter, dong_code) DO NOTHING")
    with eng.begin() as conn:
        inserted = 0
        for i in range(0, len(all_rows), 500):
            chunk = all_rows[i : i + 500]
            conn.execute(sql, chunk)
            inserted += len(chunk)
            if i % 5000 == 0:
                print(f"  [insert] 진행 {inserted:,}/{len(all_rows):,}", flush=True)

    # 수집 후 상태
    with eng.connect() as c:
        post_total = c.execute(text(f"SELECT COUNT(*) FROM {TABLE}")).scalar()
        post_gus = c.execute(text(f"SELECT COUNT(DISTINCT LEFT(dong_code,5)) FROM {TABLE}")).scalar()
        q_range = c.execute(text(f"SELECT MIN(quarter), MAX(quarter) FROM {TABLE}")).fetchone()
    print(f"\n=== 수집 후: {post_total:,}행 / {post_gus}자치구 (quarter {q_range[0]}~{q_range[1]}) ===")
    print(f"순증: +{post_total - pre_total:,}행, +{post_gus - pre_gus}자치구")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
