"""ecos_timeseries.cycle 100% NULL 채움.

audit-null-orphan-2026-05-04 발견 — ECOS API ETL 이 ``cycle`` 컬럼 미적재.
3 stat_code (121Y006/722Y001/901Y009) × ECOS StatisticItemList API 호출 후
``(stat_code, item_code1)`` 매핑으로 cycle UPDATE.

ECOS API rate limit / pagination:
- 페이지당 1000 item (901Y009 는 페이지 2 추가 호출 필요)
- 기준: 2026-05-05 — 901Y009 = 1,743 items (페이지 1+2 합산), 121Y006 = 57, 722Y001 = 48

결과: 0% → 100% (2,783/2,783)

사용법:
    cd backend && python scripts/ingest/backfill_ecos_cycle.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import sqlalchemy as sa

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.config.settings import settings  # noqa: E402

PAGE = 1000


def _fetch_meta(stat_code: str, key: str) -> dict[str, str]:
    """stat_code 의 모든 item 메타 (item_code → cycle) 가져오기. 페이지네이션 포함."""
    out: dict[str, str] = {}
    start = 1
    while True:
        url = f"http://ecos.bok.or.kr/api/StatisticItemList/{key}/json/kr/{start}/{start + PAGE - 1}/{stat_code}"
        block = httpx.get(url, timeout=30).json().get("StatisticItemList")
        if not block or not block.get("row"):
            break
        rows = block["row"]
        for row in rows:
            ic = row.get("ITEM_CODE")
            cy = row.get("CYCLE")
            if ic and cy:
                out[ic] = cy
        if len(rows) < PAGE:
            break
        start += PAGE
    return out


def main() -> None:
    key = settings.ecos_api_key
    if not key:
        raise RuntimeError("ECOS_API_KEY missing in settings")

    engine = sa.create_engine(settings.postgres_url)

    # DB 의 stat_code distinct
    with engine.connect() as conn:
        stat_codes = [r[0] for r in conn.execute(sa.text("SELECT DISTINCT stat_code FROM ecos_timeseries")).fetchall()]
    print(f"ecos_timeseries stat_codes: {stat_codes}")

    total_updates = 0
    for sc in stat_codes:
        meta = _fetch_meta(sc, key)
        print(f"  {sc}: meta {len(meta)} items")
        with engine.begin() as conn:
            updated = 0
            for ic, cy in meta.items():
                result = conn.execute(
                    sa.text(
                        "UPDATE ecos_timeseries SET cycle=:cy WHERE stat_code=:sc AND item_code1=:ic AND cycle IS NULL"
                    ),
                    {"cy": cy, "sc": sc, "ic": ic},
                )
                updated += result.rowcount
            total_updates += updated
            print(f"    updated: {updated} rows")

    with engine.connect() as conn:
        n = conn.execute(sa.text("SELECT COUNT(*) FROM ecos_timeseries")).scalar()
        n_cy = conn.execute(sa.text("SELECT COUNT(*) FROM ecos_timeseries WHERE cycle IS NOT NULL")).scalar()
    pct = (n_cy / n * 100) if n else 0
    print()
    print(f"=== AFTER ===\n  cycle non-NULL: {n_cy}/{n} ({pct:.1f}%) — total update {total_updates}")


if __name__ == "__main__":
    main()
