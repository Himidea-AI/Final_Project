"""
데이터베이스 ORM 모델 검증 — SQLAlchemy 2.0 모델 정의 테스트

외부 DB 연결 없이 메타데이터만으로 테이블/컬럼 존재 여부를 검증합니다.
"""

from src.database.models import Base


def test_all_models_defined() -> None:
    """11개 테이블이 모두 Base.metadata에 등록되었는지 확인"""
    expected_tables = {
        "living_population",
        "sgis_population",
        "sgis_household",
        "sgis_business",
        "golmok_commercial",
        "district_sales",
        "store_info",
        "store_quarterly",
        "rent_cost",
        "dong_mapping",
        "simulation_result",
    }
    registered_tables = set(Base.metadata.tables.keys())
    assert expected_tables == registered_tables, (
        f"누락된 테이블: {expected_tables - registered_tables}, "
        f"예상치 못한 테이블: {registered_tables - expected_tables}"
    )


def test_living_population_columns() -> None:
    """living_population 테이블의 핵심 컬럼 존재 여부 확인"""
    table = Base.metadata.tables["living_population"]
    column_names = {col.name for col in table.columns}

    required_columns = {"date", "time_zone", "dong_code", "total_pop"}
    for col in required_columns:
        assert col in column_names, f"컬럼 누락: {col}"


def test_simulation_result_columns() -> None:
    """simulation_result 테이블의 핵심 컬럼 존재 여부 확인"""
    table = Base.metadata.tables["simulation_result"]
    column_names = {col.name for col in table.columns}

    required_columns = {"request_id", "input_params", "output_result", "status"}
    for col in required_columns:
        assert col in column_names, f"컬럼 누락: {col}"


import pytest
from backend.src.database.postgres import PostgresClient


def test_postgres_client_init():
    """PostgresClient 초기화 확인."""
    client = PostgresClient("postgresql://localhost/test")
    assert client.database_url == "postgresql://localhost/test"
    assert client.engine is None


@pytest.mark.asyncio
async def test_postgres_client_get_session_not_connected():
    """세션 팩토리가 연결 전 사용 시 RuntimeError."""
    client = PostgresClient("postgresql+asyncpg://localhost/test")
    with pytest.raises(RuntimeError, match="Not connected"):
        async with client.get_session() as session:
            pass
