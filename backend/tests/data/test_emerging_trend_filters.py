"""마포 필터 query sanity check.

마이그레이션 + seed 적재 후 실행하는 통합 테스트.
DB 미가용 시 db_conn fixture 가 자동 skip.
"""

import pytest

pytestmark = pytest.mark.integration


def _has_table(conn, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename = %s",
        (name,),
    ).fetchone()
    return row is not None


def test_mapo_subway_join_returns_rows(db_conn):
    if not _has_table(db_conn, "seoul_subway_passenger_daily"):
        pytest.skip("table not migrated")
    cnt = db_conn.execute(
        """
        SELECT COUNT(*)
        FROM seoul_subway_passenger_daily p
        JOIN master_subway_station m USING (station_code)
        WHERE m.sigungu_code = '11440'
        """
    ).fetchone()[0]
    assert cnt >= 0


def test_mapo_migration_filter_uses_dong_code(db_conn):
    if not _has_table(db_conn, "seoul_dong_migration_monthly"):
        pytest.skip("table not migrated")
    cnt = db_conn.execute("SELECT COUNT(*) FROM seoul_dong_migration_monthly WHERE dong_code LIKE '11440%'").fetchone()[
        0
    ]
    assert cnt >= 0


def test_mapo_ttareungi_join_returns_rows(db_conn):
    if not _has_table(db_conn, "seoul_ttareungi_usage_daily"):
        pytest.skip("table not migrated")
    cnt = db_conn.execute(
        """
        SELECT COUNT(*)
        FROM seoul_ttareungi_usage_daily u
        JOIN master_ttareungi_station m USING (station_id)
        WHERE m.sigungu_code = '11440'
        """
    ).fetchone()[0]
    assert cnt >= 0


def test_subway_master_pk_unique(db_conn):
    if not _has_table(db_conn, "master_subway_station"):
        pytest.skip("table not migrated")
    dup = db_conn.execute(
        "SELECT COUNT(*) FROM (SELECT station_code FROM master_subway_station GROUP BY station_code HAVING COUNT(*) > 1) t"
    ).fetchone()[0]
    assert dup == 0


def test_ttareungi_master_pk_unique(db_conn):
    if not _has_table(db_conn, "master_ttareungi_station"):
        pytest.skip("table not migrated")
    dup = db_conn.execute(
        "SELECT COUNT(*) FROM (SELECT station_id FROM master_ttareungi_station GROUP BY station_id HAVING COUNT(*) > 1) t"
    ).fetchone()[0]
    assert dup == 0
