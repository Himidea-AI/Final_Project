"""seoul_realtime_hotspots 새 snapshot 적재 — cmrc_* 컬럼 포함.

기존 ETL bug: ``LIVE_CMRCL_STTS`` (서울 도시데이터 API) path 미파싱 → cmrc_*
4 컬럼 100% NULL (1,876 row). 본 스크립트는 정확한 path 로 재호출하여 새 snapshot
INSERT (cmrc 정상 채워짐).

API: ``/citydata/{AREA_NM}`` → CITYDATA.LIVE_PPLTN_STTS + LIVE_CMRCL_STTS.
DB 의 distinct (area_cd, area_nm) 27 areas 순회.

사용법:
    cd backend && python scripts/ingest/refresh_realtime_hotspots.py

향후 cron 으로 정기 실행 권장 (실시간 지표라 시계열 누적).
"""

from __future__ import annotations

import sys
import time
import urllib.parse as up
from pathlib import Path

import httpx
import sqlalchemy as sa

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.config.settings import settings  # noqa: E402

INSERT_SQL = """
    INSERT INTO seoul_realtime_hotspots
    (area_cd, area_nm, collected_at, congest_level, congest_msg, pop_min, pop_max,
     male_rate, female_rate, age_0_10, age_10s, age_20s, age_30s, age_40s, age_50s, age_60s, age_70_plus,
     resident_rate, visitor_rate,
     cmrc_total_level, cmrc_payment_cnt, cmrc_payment_amt_min, cmrc_payment_amt_max)
    VALUES
    (:area_cd, :area_nm, :collected_at, :congest_level, :congest_msg, :pop_min, :pop_max,
     :male_rate, :female_rate, :age_0_10, :age_10s, :age_20s, :age_30s, :age_40s, :age_50s, :age_60s, :age_70_plus,
     :resident_rate, :visitor_rate,
     :cmrc_total_level, :cmrc_payment_cnt, :cmrc_payment_amt_min, :cmrc_payment_amt_max)
"""


def _row_from_citydata(cd: dict, area_cd_default: str, area_nm_default: str) -> dict:
    ppl = (cd.get("LIVE_PPLTN_STTS") or [{}])[0]
    cmrc = cd.get("LIVE_CMRCL_STTS") or {}
    return {
        "area_cd": cd.get("AREA_CD") or area_cd_default,
        "area_nm": cd.get("AREA_NM") or area_nm_default,
        "collected_at": ppl.get("PPLTN_TIME"),
        "congest_level": ppl.get("AREA_CONGEST_LVL"),
        "congest_msg": ppl.get("AREA_CONGEST_MSG"),
        "pop_min": ppl.get("AREA_PPLTN_MIN"),
        "pop_max": ppl.get("AREA_PPLTN_MAX"),
        "male_rate": ppl.get("MALE_PPLTN_RATE"),
        "female_rate": ppl.get("FEMALE_PPLTN_RATE"),
        "age_0_10": ppl.get("PPLTN_RATE_0"),
        "age_10s": ppl.get("PPLTN_RATE_10"),
        "age_20s": ppl.get("PPLTN_RATE_20"),
        "age_30s": ppl.get("PPLTN_RATE_30"),
        "age_40s": ppl.get("PPLTN_RATE_40"),
        "age_50s": ppl.get("PPLTN_RATE_50"),
        "age_60s": ppl.get("PPLTN_RATE_60"),
        "age_70_plus": ppl.get("PPLTN_RATE_70"),
        "resident_rate": ppl.get("RESNT_PPLTN_RATE"),
        "visitor_rate": ppl.get("NON_RESNT_PPLTN_RATE"),
        "cmrc_total_level": cmrc.get("AREA_CMRCL_LVL"),
        "cmrc_payment_cnt": cmrc.get("AREA_SH_PAYMENT_CNT"),
        "cmrc_payment_amt_min": cmrc.get("AREA_SH_PAYMENT_AMT_MIN"),
        "cmrc_payment_amt_max": cmrc.get("AREA_SH_PAYMENT_AMT_MAX"),
    }


def main() -> None:
    key = settings.seoul_opendata_key
    if not key:
        raise RuntimeError("SEOUL_OPENDATA_KEY missing")

    engine = sa.create_engine(settings.postgres_url)
    with engine.connect() as conn:
        areas = conn.execute(
            sa.text("SELECT DISTINCT area_cd, area_nm FROM seoul_realtime_hotspots ORDER BY area_cd")
        ).fetchall()
    print(f"Distinct areas: {len(areas)}")

    inserts, errors = 0, []
    with engine.begin() as conn:
        for area_cd, area_nm in areas:
            url = f"http://openapi.seoul.go.kr:8088/{key}/json/citydata/1/1/{up.quote(area_nm)}"
            try:
                cd = httpx.get(url, timeout=30).json().get("CITYDATA")
                if not cd:
                    errors.append((area_cd, area_nm, "no CITYDATA"))
                    continue
                conn.execute(sa.text(INSERT_SQL), _row_from_citydata(cd, area_cd, area_nm))
                inserts += 1
            except Exception as ex:
                errors.append((area_cd, area_nm, str(ex)[:80]))
            time.sleep(0.3)

    print(f"Inserted: {inserts}, Errors: {len(errors)}")
    for e in errors[:5]:
        print(" ", e)

    with engine.connect() as conn:
        cmrc_n = conn.execute(
            sa.text("SELECT COUNT(*) FROM seoul_realtime_hotspots WHERE cmrc_total_level IS NOT NULL")
        ).scalar()
        total = conn.execute(sa.text("SELECT COUNT(*) FROM seoul_realtime_hotspots")).scalar()
    print(f"\n=== AFTER ===\n  total {total}, cmrc filled rows: {cmrc_n}")


if __name__ == "__main__":
    main()
