"""DB 통합 테스트 전용 fixture.

POSTGRES_URL 로 연결 시도. 실패 시 모든 테스트 skip.
"""

import os

import psycopg
import pytest


@pytest.fixture(scope="session")
def db_conn():
    url = os.environ.get(
        "POSTGRES_URL",
        "postgresql://postgres:postgres@localhost:5432/mapo_simulator",
    )
    url = url.replace("+asyncpg", "").replace("+psycopg", "")
    try:
        conn = psycopg.connect(url, connect_timeout=2)
    except Exception as exc:
        pytest.skip(f"PostgreSQL not available: {exc}")
    try:
        yield conn
    finally:
        conn.close()
