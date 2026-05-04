"""신흥 상권 B1 적재 후 검증.

체크 항목:
  - 5개 테이블 row 수 (>0 인지)
  - 마포 row 수 (sigungu_code='11440' 또는 dong_code LIKE '11440%')
  - PK 중복
  - NULL 비율 (특정 컬럼: boarding_cnt, move_in_cnt, rent_cnt 가 NULL > 5% → WARN)
  - 날짜/시점 범위

사용법:
  POSTGRES_URL=... python scripts/verify/verify_emerging_trend_data.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

# repo root .env auto-load
_REPO_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
if _REPO_ROOT_ENV.exists():
    load_dotenv(_REPO_ROOT_ENV)

_DEFAULT_DB_URL = os.environ.get(
    "POSTGRES_URL",
    "postgresql://postgres:postgres@localhost:5432/mapo_simulator",
)


_TABLES: list[tuple[str, str | None, str, str | None]] = [
    # (table, null_check_col, mapo_filter, date_col)
    ("master_subway_station", None, "sigungu_code = '11440'", None),
    ("master_ttareungi_station", None, "sigungu_code = '11440'", None),
    (
        "seoul_subway_passenger_daily",
        "boarding_cnt",
        "station_code IN (SELECT station_code FROM master_subway_station WHERE sigungu_code='11440')",
        "date",
    ),
    (
        "seoul_dong_migration_monthly",
        "move_in_cnt",
        "dong_code LIKE '11440%'",
        "ym",
    ),
    (
        "seoul_ttareungi_usage_daily",
        "rent_cnt",
        "station_id IN (SELECT station_id FROM master_ttareungi_station WHERE sigungu_code='11440')",
        "date",
    ),
]


def main() -> int:
    url = _DEFAULT_DB_URL.replace("+asyncpg", "").replace("+psycopg", "")
    errors = 0
    warnings = 0

    with psycopg.connect(url) as conn:
        for table, null_col, mapo_filter, date_col in _TABLES:
            total = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            mapo = conn.execute(f'SELECT COUNT(*) FROM "{table}" WHERE {mapo_filter}').fetchone()[0]
            extra = ""
            if date_col and total > 0:
                d_min, d_max = conn.execute(f'SELECT MIN("{date_col}"), MAX("{date_col}") FROM "{table}"').fetchone()
                extra = f"  range={d_min}~{d_max}"
            print(f"[{table}]  total={total:,}  mapo={mapo:,}{extra}")

            if total == 0:
                print("  WARN: empty table")
                warnings += 1
                continue

            if null_col is not None:
                null_cnt = conn.execute(f'SELECT COUNT(*) FROM "{table}" WHERE "{null_col}" IS NULL').fetchone()[0]
                ratio = null_cnt / total
                if ratio > 0.05:
                    print(f"  WARN: {null_col} NULL ratio = {ratio:.1%}")
                    warnings += 1

            # PK 중복 점검 — 일반화 (PK 컬럼 자동 조회)
            pk_cols = conn.execute(
                """
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = %s::regclass AND i.indisprimary
                ORDER BY array_position(i.indkey, a.attnum)
                """,
                (table,),
            ).fetchall()
            if pk_cols:
                cols_sql = ", ".join(f'"{c[0]}"' for c in pk_cols)
                dup = conn.execute(
                    f"""
                    SELECT COUNT(*) FROM (
                        SELECT {cols_sql} FROM "{table}"
                        GROUP BY {cols_sql} HAVING COUNT(*) > 1
                    ) t
                    """
                ).fetchone()[0]
                if dup > 0:
                    print(f"  ERROR: PK duplicates: {dup}")
                    errors += 1

        # 마포 지하철역 좌표 coverage — fill_subway_coords 실행 후 필수.
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM master_subway_station WHERE sigungu_code='11440'")
            mapo_total = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM master_subway_station "
                "WHERE sigungu_code='11440' AND lat IS NOT NULL AND lon IS NOT NULL"
            )
            mapo_with_coord = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM master_subway_station "
                "WHERE sigungu_code='11440' AND lat IS NOT NULL "
                "AND (lat NOT BETWEEN 37.53 AND 37.59 OR lon NOT BETWEEN 126.87 AND 126.97)"
            )
            out_of_bbox = cur.fetchone()[0]
            print(f"[master_subway_station coords]  mapo={mapo_total}  with_coord={mapo_with_coord}")
            if mapo_with_coord < mapo_total:
                print(f"  WARN: {mapo_total - mapo_with_coord} mapo stations missing coord")
                warnings += 1
            if out_of_bbox > 0:
                print(f"  ERROR: {out_of_bbox} mapo stations outside Mapo bbox")
                errors += 1

    print()
    print(f"errors={errors}  warnings={warnings}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
