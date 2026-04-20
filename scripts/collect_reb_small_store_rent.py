"""
Collect 한국부동산원 소규모상가 분기별 지역별 임대료 via R-ONE OpenAPI.

Replaces the legacy 2019~2021 CSV ingestion (data.go.kr dataset 15069766).
Single source now: REB R-ONE `SttsApiTblData.do` across 7 STATBL_IDs covering
2013 Q1 ~ latest published quarter (2025 Q4 as of 2026-04-20).

실행: python scripts/collect_reb_small_store_rent.py
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass

import httpx
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DB_URL = os.environ["POSTGRES_URL"]
REB_KEY = os.environ["REB_API_KEY"]
BASE = "https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do"
PAGE_SIZE = 1000  # API 상한

engine = create_engine(DB_URL, echo=False)


@dataclass(frozen=True)
class StatTable:
    statbl_id: str
    label: str


# SttsApiTbl.do로 확인된 "지역별 임대료(소규모상가)" 시리즈 (cycle=QY).
# 표본 재설정 시점에서 STATBL_ID가 분리됨.
STAT_TABLES: list[StatTable] = [
    StatTable("A_2024_00259", "2013~2016"),
    StatTable("A_2024_00263", "2017~2018"),
    StatTable("A_2024_00267", "2019"),
    StatTable("A_2024_00271", "2020"),
    StatTable("A_2024_00275", "2021"),
    StatTable("A_2024_00279", "2022~2024 Q2"),
    StatTable("T248223134698125", "2024 Q3~"),
]


def fetch_all(client: httpx.Client, statbl_id: str) -> list[dict]:
    out: list[dict] = []
    page = 1
    while True:
        params = {
            "KEY": REB_KEY,
            "Type": "json",
            "pIndex": page,
            "pSize": PAGE_SIZE,
            "STATBL_ID": statbl_id,
            "DTACYCLE_CD": "QY",
        }
        r = client.get(BASE, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        if "SttsApiTblData" not in data:
            raise RuntimeError(f"{statbl_id}: unexpected response {data}")
        rows = data["SttsApiTblData"][1].get("row", [])
        total = data["SttsApiTblData"][0]["head"][0]["list_total_count"]
        out.extend(rows)
        if len(out) >= total or not rows:
            break
        page += 1
        time.sleep(0.1)
    return out


def build_cls_dict(all_rows: list[dict]) -> dict[int, tuple[str, str]]:
    """CLS_ID → (CLS_FULLNM, CLS_NM) 매핑. 일부 STATBL_ID가 null로 주는 이름을 보충."""
    d: dict[int, tuple[str, str]] = {}
    for r in all_rows:
        full = r.get("CLS_FULLNM")
        nm = r.get("CLS_NM")
        if not full and not nm:
            continue
        cid = int(r["CLS_ID"])
        # 더 풍부한 이름이 들어오면 교체
        if cid not in d or (full and not d[cid][0]):
            d[cid] = (full or nm, nm or full)
    return d


def normalize(rows: list[dict], cls_dict: dict[int, tuple[str, str]]) -> pd.DataFrame:
    recs = []
    for r in rows:
        if r.get("ITM_NM") != "임대료":
            continue
        wrt = str(r["WRTTIME_IDTFR_ID"])  # e.g. "201901"
        if len(wrt) != 6:
            continue
        year = int(wrt[:4])
        quarter = int(wrt[4:])
        if quarter not in (1, 2, 3, 4):
            continue
        cid = int(r["CLS_ID"])
        full = r.get("CLS_FULLNM")
        nm = r.get("CLS_NM")
        if not full or not nm:
            fb_full, fb_nm = cls_dict.get(cid, (None, None))
            full = full or fb_full or f"CLS_{cid}"
            nm = nm or fb_nm or f"CLS_{cid}"
        recs.append(
            {
                "cls_id": cid,
                "cls_full_nm": full,
                "cls_nm": nm,
                "region": full,
                "year": year,
                "quarter": quarter,
                "rent": float(r["DTA_VAL"]),
                "statbl_id": r["STATBL_ID"],
            }
        )
    return pd.DataFrame(recs)


def ensure_schema() -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS small_store_rent_q"))
        conn.execute(
            text(
                """
                CREATE TABLE small_store_rent_q (
                    id BIGSERIAL PRIMARY KEY,
                    cls_id INTEGER NOT NULL,
                    cls_full_nm TEXT NOT NULL,
                    cls_nm TEXT,
                    region TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    quarter INTEGER NOT NULL,
                    rent DOUBLE PRECISION,
                    statbl_id TEXT,
                    UNIQUE (cls_id, year, quarter)
                )
                """
            )
        )
        conn.execute(text("CREATE INDEX idx_ssrq_region ON small_store_rent_q (region)"))
        conn.execute(text("CREATE INDEX idx_ssrq_yq ON small_store_rent_q (year, quarter)"))


def load(df: pd.DataFrame) -> int:
    # (cls_id, year, quarter) 중복 시 최신(= 더 큰 STATBL_ID 연도) 우선
    df = df.sort_values(["cls_id", "year", "quarter", "statbl_id"]).drop_duplicates(
        subset=["cls_id", "year", "quarter"], keep="last"
    )
    df.to_sql("small_store_rent_q", engine, if_exists="append", index=False, method="multi", chunksize=1000)
    return len(df)


def verify() -> None:
    with engine.connect() as c:
        total = c.execute(text("SELECT COUNT(*) FROM small_store_rent_q")).scalar()
        yr_range = c.execute(text("SELECT MIN(year*10+quarter), MAX(year*10+quarter) FROM small_store_rent_q")).one()
        by_year = c.execute(
            text(
                "SELECT year, COUNT(DISTINCT quarter) q, COUNT(DISTINCT cls_id) regions, COUNT(*) n "
                "FROM small_store_rent_q GROUP BY year ORDER BY year"
            )
        ).all()
        gwanghwamun = c.execute(
            text(
                "SELECT year, quarter, ROUND(rent::numeric, 2) rent FROM small_store_rent_q "
                "WHERE cls_full_nm LIKE '%광화문%' AND year=2019 ORDER BY quarter"
            )
        ).all()

    print(f"\n[verify] total rows: {total:,}")
    print(f"[verify] range: {yr_range[0]} ~ {yr_range[1]} (YYYY+Q)")
    print("[verify] by year: year | quarters | regions | rows")
    for y, q, reg, n in by_year:
        print(f"  {y}  |   {q}     |   {reg}    | {n}")
    print("[verify] 서울>도심>광화문 2019 sample:")
    for y, q, rent in gwanghwamun:
        print(f"  {y} Q{q}: {rent} 천원/㎡  (CSV 기존: 95.0/95.0/95.0/95.1)")


def main() -> int:
    ensure_schema()
    raw_by_tbl: list[tuple[StatTable, list[dict]]] = []
    with httpx.Client() as client:
        for tbl in STAT_TABLES:
            rows = fetch_all(client, tbl.statbl_id)
            raw_by_tbl.append((tbl, rows))
            print(f"  [{tbl.statbl_id}] {tbl.label:12s}: api_rows={len(rows):>5}")

    cls_dict = build_cls_dict([r for _, rows in raw_by_tbl for r in rows])
    print(f"  [cls_dict] {len(cls_dict)} unique CLS_ID mapped")

    all_df = [normalize(rows, cls_dict) for _, rows in raw_by_tbl]
    merged = pd.concat(all_df, ignore_index=True)
    n = load(merged)
    print(f"\n[load] inserted {n:,} unique (cls_id, year, quarter) rows")
    verify()
    return 0


if __name__ == "__main__":
    sys.exit(main())
