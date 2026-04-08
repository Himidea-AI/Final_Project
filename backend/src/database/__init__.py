"""
데이터베이스 연결 패키지 — PostgreSQL, Redis, ChromaDB

  - postgres.py     : PostgreSQL 연결 + SQLAlchemy (상권통계, 시뮬레이션 결과)
  - redis_client.py : Redis 연결 (시뮬레이션 결과 캐시, Job 상태 관리)
  - vector_db.py    : ChromaDB 연결 + OpenAI 임베딩 (법률 문서 RAG)

Docker Compose 환경에서 서비스명:
  PostgreSQL → localhost:5432 | Redis → localhost:6379 | ChromaDB → localhost:8000

담당: A — 데이터 엔지니어
"""

from .models import (
    Base,
    DistrictSales,
    DongMapping,
    GolmokCommercial,
    LivingPopulation,
    RentCost,
    SgisBusiness,
    SgisHousehold,
    SgisPopulation,
    SimulationResult,
    StoreInfo,
    StoreQuarterly,
)
from .postgres import PostgresClient

__all__ = [
    "Base",
    "LivingPopulation",
    "SgisPopulation",
    "SgisHousehold",
    "SgisBusiness",
    "GolmokCommercial",
    "DistrictSales",
    "StoreInfo",
    "StoreQuarterly",
    "RentCost",
    "DongMapping",
    "SimulationResult",
    "PostgresClient",
]
