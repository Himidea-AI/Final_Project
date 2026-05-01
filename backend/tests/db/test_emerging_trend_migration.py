"""Alembic migration b9c1e3f5d7a2 (emerging trend B1) up/down 검증.

PostgreSQL 미가용 환경에서는 db_conn fixture 가 자동 skip.
"""

import os
import subprocess

import pytest


REVISION = "b9c1e3f5d7a2"
PRIOR = "a8b2c4d6e8f0"
TABLES = [
    "master_subway_station",
    "master_ttareungi_station",
    "seoul_subway_passenger_daily",
    "seoul_dong_migration_monthly",
    "seoul_ttareungi_usage_daily",
]


@pytest.fixture(scope="module")
def alembic_env():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _run_alembic(env_dir: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["alembic", *args],
        cwd=env_dir,
        capture_output=True,
        text=True,
        check=False,
    )


def _table_exists(conn, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename = %s",
        (name,),
    ).fetchone()
    return row is not None


@pytest.mark.integration
def test_migration_upgrade_creates_all_tables(alembic_env, db_conn):
    res = _run_alembic(alembic_env, "upgrade", REVISION)
    assert res.returncode == 0, f"upgrade failed: {res.stderr}"
    for t in TABLES:
        assert _table_exists(db_conn, t), f"{t} not created"


@pytest.mark.integration
def test_migration_downgrade_drops_all_tables(alembic_env, db_conn):
    res = _run_alembic(alembic_env, "downgrade", PRIOR)
    assert res.returncode == 0, f"downgrade failed: {res.stderr}"
    for t in TABLES:
        assert not _table_exists(db_conn, t), f"{t} still exists"
    # 다시 head 로 복구해서 후속 테스트에 영향 없도록
    _run_alembic(alembic_env, "upgrade", "head")
