import pytest
from fastapi.testclient import TestClient
from src.main import app

@pytest.fixture(scope="session")
def client():
    """
    통합 테스트용 FastAPI TestClient
    - 내부적으로 .env의 POSTGRES_URL(RDS)을 사용합니다.
    """
    with TestClient(app) as c:
        yield c
