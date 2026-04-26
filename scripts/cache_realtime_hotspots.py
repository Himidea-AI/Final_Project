"""seoul_realtime_hotspots cron 적재 스크립트.

서울시 OpenAPI (citydata_ppltn) → seoul_realtime_hotspots DB upsert.
30분 주기 cron 으로 실행하여 ABM 이 최신 hotspot 데이터를 사용 가능하게 유지.

설계:
    - DB 의 (area_cd, collected_at) UNIQUE 키로 중복 방지 (idempotent)
    - 동일 timestamp 의 행이 이미 있으면 skip (insert ignore)
    - 매 실행마다 4개 마포 POI 조회 (~3초)

Usage:
    python -m scripts.cache_realtime_hotspots                # 마포 4 POI
    python -m scripts.cache_realtime_hotspots --pois POI007 POI053  # 특정 POI

Cron 등록 (Linux):
    */30 * * * * cd /path/to/repo && python -m scripts.cache_realtime_hotspots >> logs/cron_hotspots.log 2>&1

Windows Task Scheduler:
    schtasks /create /sc minute /mo 30 /tn "ABM_Hotspots" /tr "python -m scripts.cache_realtime_hotspots"

담당: A1 — 찬영
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# 프로젝트 루트 path 설정 (backend.src 임포트 위해)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

load_dotenv(PROJECT_ROOT / ".env")

from src.services.seoul_realtime import MAPO_POI_IDS, fetch_realtime_hotspots  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def upsert_hotspots(records: list[dict]) -> tuple[int, int]:
    """records → seoul_realtime_hotspots upsert.

    Returns:
        (inserted, skipped) — collected_at 중복은 skip.
    """
    if not records:
        return 0, 0

    db_url = os.environ.get("POSTGRES_URL")
    if not db_url:
        raise RuntimeError("POSTGRES_URL 환경변수 없음")

    engine = create_engine(db_url, isolation_level="AUTOCOMMIT")
    inserted = 0
    skipped = 0

    insert_sql = text(
        """
        INSERT INTO seoul_realtime_hotspots (
            area_cd, area_nm, collected_at, congest_level, congest_msg,
            pop_min, pop_max, male_rate, female_rate,
            age_0_10, age_10s, age_20s, age_30s, age_40s, age_50s, age_60s, age_70_plus,
            resident_rate, visitor_rate,
            cmrc_total_level, cmrc_payment_cnt, cmrc_payment_amt_min, cmrc_payment_amt_max
        ) VALUES (
            :area_cd, :area_nm, :collected_at, :congest_level, :congest_msg,
            :pop_min, :pop_max, :male_rate, :female_rate,
            :age_0_10, :age_10s, :age_20s, :age_30s, :age_40s, :age_50s, :age_60s, :age_70_plus,
            :resident_rate, :visitor_rate,
            :cmrc_total_level, :cmrc_payment_cnt, :cmrc_payment_amt_min, :cmrc_payment_amt_max
        )
        """
    )

    # 중복 체크: (area_cd, collected_at) 같으면 skip
    dup_check = text(
        "SELECT 1 FROM seoul_realtime_hotspots WHERE area_cd = :area_cd AND collected_at = :collected_at LIMIT 1"
    )

    with engine.connect() as c:
        for rec in records:
            exists = c.execute(
                dup_check,
                {"area_cd": rec["area_cd"], "collected_at": rec["collected_at"]},
            ).fetchone()
            if exists:
                skipped += 1
                continue
            c.execute(insert_sql, rec)
            inserted += 1
    return inserted, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description="seoul_realtime_hotspots 적재")
    ap.add_argument(
        "--pois",
        nargs="+",
        default=None,
        help=f"적재할 POI ID 리스트 (기본: 마포 4개 {MAPO_POI_IDS})",
    )
    args = ap.parse_args()

    poi_ids = args.pois or MAPO_POI_IDS
    logger.info(f"실시간 hotspot 적재 시작 — {len(poi_ids)} POI: {poi_ids}")

    records = fetch_realtime_hotspots(poi_ids=poi_ids)
    if not records:
        logger.warning("API 응답 0건 — 키/네트워크 확인 필요")
        return 1

    inserted, skipped = upsert_hotspots(records)
    logger.info(f"완료 — 신규 {inserted}건 / 중복 skip {skipped}건 / 총 응답 {len(records)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
