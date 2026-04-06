# Data Pipeline + PostgreSQL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CSV 41개를 PostgreSQL 11개 테이블로 통합 적재하는 데이터 파이프라인 구축

**Architecture:** SQLAlchemy 2.0 ORM으로 11개 테이블 모델 정의, Alembic으로 마이그레이션, pandas 기반 ETL 스크립트로 CSV를 읽어 bulk insert. 에이전트 노드는 async SQLAlchemy 세션으로 조회.

**Tech Stack:** SQLAlchemy 2.0, Alembic, asyncpg, psycopg2-binary, pandas, PostgreSQL 16

---

## File Structure

```
backend/src/database/
  models.py           -- SQLAlchemy ORM 11 tables (CREATE)
  postgres.py         -- Async DB client (REPLACE existing stub)
  __init__.py         -- Update exports (MODIFY)

backend/alembic.ini           -- Alembic config (CREATE)
backend/alembic/
  env.py                      -- Alembic environment (CREATE)
  versions/                   -- Migration scripts auto-generated

data/pipeline/
  load_to_db.py               -- CSV -> PostgreSQL ETL (CREATE)

backend/requirements.txt      -- Add alembic, asyncpg (MODIFY)

tests/
  test_database.py            -- DB model + client tests (CREATE)
```

---

### Task 1: Add Dependencies

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add alembic and asyncpg to requirements.txt**

Add these lines to the `# === ORM / DB ===` section of `backend/requirements.txt`:

```
alembic>=1.13.0
asyncpg>=0.30.0
```

- [ ] **Step 2: Install dependencies**

Run:
```bash
cd backend && pip install alembic asyncpg
```
Expected: Successfully installed alembic asyncpg

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "IM3-28: alembic, asyncpg 의존성 추가"
```

---

### Task 2: Define SQLAlchemy ORM Models

**Files:**
- Create: `backend/src/database/models.py`

- [ ] **Step 1: Write the test for model imports**

Create `tests/test_database.py`:

```python
"""데이터베이스 모델 + 클라이언트 테스트."""

from backend.src.database.models import (
    Base,
    DongMapping,
    DistrictSales,
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


def test_all_models_defined():
    """11개 테이블 모델이 모두 정의되어 있는지 확인."""
    tables = Base.metadata.tables
    expected = {
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
    assert expected == set(tables.keys()), f"Missing: {expected - set(tables.keys())}"


def test_living_population_columns():
    """living_population 테이블 주요 컬럼 확인."""
    cols = {c.name for c in LivingPopulation.__table__.columns}
    assert "date" in cols
    assert "time_zone" in cols
    assert "dong_code" in cols
    assert "total_pop" in cols


def test_simulation_result_columns():
    """simulation_result 테이블 주요 컬럼 확인."""
    cols = {c.name for c in SimulationResult.__table__.columns}
    assert "request_id" in cols
    assert "input_params" in cols
    assert "output_result" in cols
    assert "status" in cols
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Users/804/Documents/final project" && python -m pytest tests/test_database.py -v`
Expected: FAIL — ModuleNotFoundError (models.py doesn't exist yet)

- [ ] **Step 3: Write models.py with all 11 tables**

Create `backend/src/database/models.py`:

```python
"""
SQLAlchemy ORM 모델 — PostgreSQL 11개 테이블 정의

Tables:
  1. living_population   — 행정동 단위 생활인구 (KT 통신 데이터)
  2. sgis_population     — SGIS 인구통계 (통계청)
  3. sgis_household      — SGIS 가구통계
  4. sgis_business       — SGIS 사업체통계
  5. golmok_commercial   — 골목상권 종합 (서울 상권분석서비스)
  6. district_sales      — 행정동 추정매출
  7. store_info          — 개별 점포 정보 (소상공인시장진흥공단)
  8. store_quarterly     — 분기별 점포 집계
  9. rent_cost           — 임대료/실거래가 통합
  10. dong_mapping       — 행정동 마스터 (16개 동)
  11. simulation_result  — 시뮬레이션 입력/결과
"""

import uuid

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    Float,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class LivingPopulation(Base):
    """행정동 단위 생활인구 — 일별/시간대별/성별/연령대별."""

    __tablename__ = "living_population"

    date = Column(Date, primary_key=True)
    time_zone = Column(SmallInteger, primary_key=True)
    dong_code = Column(String(10), primary_key=True)
    dong_name = Column(String(20))
    total_pop = Column(Float)
    male_0_9 = Column(Float)
    male_10_14 = Column(Float)
    male_15_19 = Column(Float)
    male_20_24 = Column(Float)
    male_25_29 = Column(Float)
    male_30_34 = Column(Float)
    male_35_39 = Column(Float)
    male_40_44 = Column(Float)
    male_45_49 = Column(Float)
    male_50_54 = Column(Float)
    male_55_59 = Column(Float)
    male_60_64 = Column(Float)
    male_65_69 = Column(Float)
    male_70_plus = Column(Float)
    female_0_9 = Column(Float)
    female_10_14 = Column(Float)
    female_15_19 = Column(Float)
    female_20_24 = Column(Float)
    female_25_29 = Column(Float)
    female_30_34 = Column(Float)
    female_35_39 = Column(Float)
    female_40_44 = Column(Float)
    female_45_49 = Column(Float)
    female_50_54 = Column(Float)
    female_55_59 = Column(Float)
    female_60_64 = Column(Float)
    female_65_69 = Column(Float)
    female_70_plus = Column(Float)


class SgisPopulation(Base):
    """SGIS 인구통계 — 소지역 단위 인구/연령/밀도."""

    __tablename__ = "sgis_population"

    year = Column(SmallInteger, primary_key=True)
    area_code = Column(String(14), primary_key=True)
    indicator = Column(String(30), primary_key=True)
    value = Column(Float)


class SgisHousehold(Base):
    """SGIS 가구통계 — 소지역 단위 가구수/구성."""

    __tablename__ = "sgis_household"

    year = Column(SmallInteger, primary_key=True)
    area_code = Column(String(14), primary_key=True)
    indicator = Column(String(30), primary_key=True)
    value = Column(Float)


class SgisBusiness(Base):
    """SGIS 사업체통계 — 소지역 단위 업종별 사업체수/종사자수."""

    __tablename__ = "sgis_business"

    year = Column(SmallInteger, primary_key=True)
    area_code = Column(String(14), primary_key=True)
    indicator = Column(String(30), primary_key=True)
    value = Column(Float)


class GolmokCommercial(Base):
    """골목상권 종합 — 매출/점포/유동인구/직장인구/지수/변화지표."""

    __tablename__ = "golmok_commercial"

    id = Column(Integer, primary_key=True, autoincrement=True)
    quarter = Column(Integer, nullable=False, index=True)
    trdar_code = Column(String(10), nullable=False)
    data_type = Column(String(20), nullable=False, index=True)
    industry_code = Column(String(20), default="ALL")
    metrics = Column(JSONB)


class DistrictSales(Base):
    """행정동 추정매출 — 분기별/업종별/시간대별/성별/연령대별."""

    __tablename__ = "district_sales"

    quarter = Column(Integer, primary_key=True)
    dong_code = Column(String(10), primary_key=True, index=True)
    industry_code = Column(String(20), primary_key=True)
    dong_name = Column(String(20))
    industry_name = Column(String(50))
    monthly_sales = Column(BigInteger)
    monthly_count = Column(Integer)
    weekday_sales = Column(BigInteger)
    weekend_sales = Column(BigInteger)
    mon_sales = Column(BigInteger)
    tue_sales = Column(BigInteger)
    wed_sales = Column(BigInteger)
    thu_sales = Column(BigInteger)
    fri_sales = Column(BigInteger)
    sat_sales = Column(BigInteger)
    sun_sales = Column(BigInteger)
    time_00_06_sales = Column(BigInteger)
    time_06_11_sales = Column(BigInteger)
    time_11_14_sales = Column(BigInteger)
    time_14_17_sales = Column(BigInteger)
    time_17_21_sales = Column(BigInteger)
    time_21_24_sales = Column(BigInteger)
    male_sales = Column(BigInteger)
    female_sales = Column(BigInteger)
    age_10_sales = Column(BigInteger)
    age_20_sales = Column(BigInteger)
    age_30_sales = Column(BigInteger)
    age_40_sales = Column(BigInteger)
    age_50_sales = Column(BigInteger)
    age_60_above_sales = Column(BigInteger)
    weekday_count = Column(Integer)
    weekend_count = Column(Integer)
    mon_count = Column(Integer)
    tue_count = Column(Integer)
    wed_count = Column(Integer)
    thu_count = Column(Integer)
    fri_count = Column(Integer)
    sat_count = Column(Integer)
    sun_count = Column(Integer)
    time_00_06_count = Column(Integer)
    time_06_11_count = Column(Integer)
    time_11_14_count = Column(Integer)
    time_14_17_count = Column(Integer)
    time_17_21_count = Column(Integer)
    time_21_24_count = Column(Integer)
    male_count = Column(Integer)
    female_count = Column(Integer)
    age_10_count = Column(Integer)
    age_20_count = Column(Integer)
    age_30_count = Column(Integer)
    age_40_count = Column(Integer)
    age_50_count = Column(Integer)
    age_60_above_count = Column(Integer)


class StoreInfo(Base):
    """개별 점포 정보 — 위치/업종/상호."""

    __tablename__ = "store_info"

    store_id = Column(String(20), primary_key=True)
    store_name = Column(String(100))
    dong_code = Column(String(10), index=True)
    dong_name = Column(String(20), index=True)
    address = Column(Text)
    road_address = Column(Text)
    lat = Column(Float)
    lon = Column(Float)
    industry_l_code = Column(String(10))
    industry_l = Column(String(50))
    industry_m_code = Column(String(10))
    industry_m = Column(String(50), index=True)
    industry_s_code = Column(String(10))
    industry_s = Column(String(50))
    building_name = Column(String(100))
    floor_info = Column(String(20))


class StoreQuarterly(Base):
    """분기별 점포 집계 — 개업/폐업/프랜차이즈."""

    __tablename__ = "store_quarterly"

    quarter = Column(Integer, primary_key=True)
    dong_code = Column(String(10), primary_key=True, index=True)
    industry_code = Column(String(20), primary_key=True)
    dong_name = Column(String(20))
    industry_name = Column(String(50))
    store_count = Column(Integer)
    open_count = Column(Integer)
    close_count = Column(Integer)
    closure_rate = Column(Float)
    franchise_count = Column(Integer)


class RentCost(Base):
    """임대료/비용 통합 — 빌딩임대료 + 실거래가."""

    __tablename__ = "rent_cost"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data_type = Column(String(20), nullable=False, index=True)
    area_name = Column(String(50))
    year = Column(SmallInteger)
    quarter = Column(SmallInteger)
    rent = Column(Float)
    vacancy_rate = Column(Float)
    investment_return = Column(Float)
    income_return = Column(Float)
    capital_return = Column(Float)
    transaction_date = Column(String(10))
    price = Column(BigInteger)
    floor_area = Column(Float)
    floor = Column(String(10))
    source = Column(String(20))


class DongMapping(Base):
    """행정동 마스터 — 16개 동 기본 정보 + 상권코드 매핑."""

    __tablename__ = "dong_mapping"

    dong_code = Column(String(10), primary_key=True)
    dong_name = Column(String(20), nullable=False)
    resident_pop = Column(Integer)
    floating_pop = Column(Float)
    avg_age = Column(Float)
    total_households = Column(Integer)
    trdar_codes = Column(JSONB)


class SimulationResult(Base):
    """시뮬레이션 입력/결과 저장."""

    __tablename__ = "simulation_result"

    request_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(Date, server_default=func.now())
    input_params = Column(JSONB)
    output_result = Column(JSONB)
    status = Column(String(20), default="pending")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "C:/Users/804/Documents/final project" && python -m pytest tests/test_database.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/database/models.py tests/test_database.py
git commit -m "IM3-28: SQLAlchemy ORM 모델 11개 테이블 정의"
```

---

### Task 3: Setup Alembic Migrations

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/` (directory)

- [ ] **Step 1: Initialize Alembic**

Run:
```bash
cd "C:/Users/804/Documents/final project/backend" && alembic init alembic
```
Expected: Creates `alembic/` directory and `alembic.ini`

- [ ] **Step 2: Configure alembic.ini**

Edit `backend/alembic.ini` — change the `sqlalchemy.url` line:

```ini
sqlalchemy.url = postgresql://postgres:postgres@localhost:5432/mapo_simulator
```

- [ ] **Step 3: Configure alembic/env.py**

Replace the `target_metadata` line in `backend/alembic/env.py`:

```python
# Add at top of file, after existing imports
import sys
from pathlib import Path

# Add backend/src to path so models can be imported
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from database.models import Base

target_metadata = Base.metadata
```

- [ ] **Step 4: Generate initial migration**

Run:
```bash
cd "C:/Users/804/Documents/final project/backend" && alembic revision --autogenerate -m "initial schema 11 tables"
```
Expected: Creates a migration file in `alembic/versions/`

- [ ] **Step 5: Commit**

```bash
git add backend/alembic.ini backend/alembic/
git commit -m "IM3-28: Alembic 초기 설정 + 11 테이블 마이그레이션"
```

---

### Task 4: Implement PostgresClient

**Files:**
- Replace: `backend/src/database/postgres.py`
- Modify: `backend/src/database/__init__.py`

- [ ] **Step 1: Write test for PostgresClient**

Add to `tests/test_database.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.src.database.postgres import PostgresClient


def test_postgres_client_init():
    """PostgresClient 초기화 확인."""
    client = PostgresClient("postgresql://localhost/test")
    assert client.database_url == "postgresql://localhost/test"
    assert client.engine is None


@pytest.mark.asyncio
async def test_postgres_client_get_session():
    """세션 팩토리가 연결 후 사용 가능한지 확인."""
    client = PostgresClient("postgresql+asyncpg://localhost/test")
    # connect 없이 session 호출하면 RuntimeError
    with pytest.raises(RuntimeError):
        async with client.get_session() as session:
            pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Users/804/Documents/final project" && python -m pytest tests/test_database.py::test_postgres_client_init -v`
Expected: FAIL

- [ ] **Step 3: Implement PostgresClient**

Replace `backend/src/database/postgres.py`:

```python
"""
PostgreSQL 비동기 클라이언트 — SQLAlchemy 2.0 async engine + session
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .models import Base


class PostgresClient:
    """PostgreSQL async 클라이언트."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = None
        self._session_factory = None

    async def connect(self) -> None:
        """async engine + session factory 초기화."""
        async_url = self.database_url.replace(
            "postgresql://", "postgresql+asyncpg://"
        )
        self.engine = create_async_engine(async_url, echo=False, pool_size=5)
        self._session_factory = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def disconnect(self) -> None:
        """엔진 종료."""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self._session_factory = None

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """async session context manager."""
        if self._session_factory is None:
            raise RuntimeError("Not connected. Call connect() first.")
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def create_tables(self) -> None:
        """모든 테이블 생성 (개발/테스트용)."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_tables(self) -> None:
        """모든 테이블 삭제 (테스트용)."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
```

- [ ] **Step 4: Update __init__.py exports**

Replace `backend/src/database/__init__.py`:

```python
"""
데이터베이스 연결 패키지 — PostgreSQL, Redis, ChromaDB

담당: A1 — 데이터 엔지니어
"""

from .models import (
    Base,
    DongMapping,
    DistrictSales,
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
from .redis_client import RedisClient
from .vector_db import VectorDBClient

__all__ = [
    "Base",
    "PostgresClient",
    "RedisClient",
    "VectorDBClient",
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
]
```

- [ ] **Step 5: Run tests**

Run: `cd "C:/Users/804/Documents/final project" && python -m pytest tests/test_database.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/database/postgres.py backend/src/database/__init__.py
git commit -m "IM3-28: PostgresClient async 구현 (SQLAlchemy 2.0)"
```

---

### Task 5: Build ETL Pipeline — load_to_db.py

**Files:**
- Create: `data/pipeline/__init__.py`
- Create: `data/pipeline/load_to_db.py`

- [ ] **Step 1: Create pipeline directory**

Run:
```bash
mkdir -p "C:/Users/804/Documents/final project/data/pipeline"
touch "C:/Users/804/Documents/final project/data/pipeline/__init__.py"
```

- [ ] **Step 2: Write load_to_db.py**

Create `data/pipeline/load_to_db.py`:

```python
"""
CSV -> PostgreSQL ETL 파이프라인

41개 CSV → 11개 테이블로 통합 적재.
동기 SQLAlchemy + pandas bulk insert 사용.

Usage:
    cd data && python pipeline/load_to_db.py
    또는 특정 테이블만:
    python pipeline/load_to_db.py --table district_sales
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# backend 모듈 import를 위한 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend" / "src"))
from database.models import Base

PROC = Path(__file__).resolve().parents[1] / "processed"
DB_URL = "postgresql://postgres:postgres@localhost:5432/mapo_simulator"


def get_engine(db_url: str = DB_URL):
    engine = create_engine(db_url, echo=False)
    Base.metadata.create_all(engine)
    return engine


# ─── 1. living_population ───────────────────────────────────────────
def load_living_population(engine):
    print("[1/11] living_population...")
    df = pd.read_csv(PROC / "living_population_dong_mapo.csv", dtype=str)

    # 컬럼 매핑
    col_map = {"STDR_DE_ID": "date", "TMZON_PD_SE": "time_zone", "ADSTRD_CODE_SE": "dong_code", "TOT_LVPOP_CO": "total_pop"}
    # 남녀 연령대 컬럼 매핑
    male_age = [("남자0세부터9세생활인구수", "male_0_9"), ("남자10세부터14세생활인구수", "male_10_14"),
                ("남자15세부터19세생활인구수", "male_15_19"), ("남자20세부터24세생활인구수", "male_20_24"),
                ("남자25세부터29세생활인구수", "male_25_29"), ("남자30세부터34세생활인구수", "male_30_34"),
                ("남자35세부터39세생활인구수", "male_35_39"), ("남자40세부터44세생활인구수", "male_40_44"),
                ("남자45세부터49세생활인구수", "male_45_49"), ("남자50세부터54세생활인구수", "male_50_54"),
                ("남자55세부터59세생활인구수", "male_55_59"), ("남자60세부터64세생활인구수", "male_60_64"),
                ("남자65세부터69세생활인구수", "male_65_69"), ("남자70세이상생활인구수", "male_70_plus")]
    female_age = [(m[0].replace("남자", "여자"), m[1].replace("male", "female")) for m in male_age]

    for old, new in male_age + female_age:
        if old in df.columns:
            col_map[old] = new
    # MALE_F*_LVPOP_CO 형식도 매핑 (API에서 가져온 데이터)
    api_male = [("MALE_F0T9_LVPOP_CO", "male_0_9"), ("MALE_F10T14_LVPOP_CO", "male_10_14"),
                ("MALE_F15T19_LVPOP_CO", "male_15_19"), ("MALE_F20T24_LVPOP_CO", "male_20_24"),
                ("MALE_F25T29_LVPOP_CO", "male_25_29"), ("MALE_F30T34_LVPOP_CO", "male_30_34"),
                ("MALE_F35T39_LVPOP_CO", "male_35_39"), ("MALE_F40T44_LVPOP_CO", "male_40_44"),
                ("MALE_F45T49_LVPOP_CO", "male_45_49"), ("MALE_F50T54_LVPOP_CO", "male_50_54"),
                ("MALE_F55T59_LVPOP_CO", "male_55_59"), ("MALE_F60T64_LVPOP_CO", "male_60_64"),
                ("MALE_F65T69_LVPOP_CO", "male_65_69"), ("MALE_F70T74_LVPOP_CO", "male_70_plus")]
    api_female = [(m[0].replace("MALE", "FEMALE"), m[1].replace("male", "female")) for m in api_male]
    for old, new in api_male + api_female:
        if old in df.columns:
            col_map[old] = new

    rename = {k: v for k, v in col_map.items() if k in df.columns}
    df = df.rename(columns=rename)

    # 필요한 컬럼만 선택
    target_cols = ["date", "time_zone", "dong_code", "dong_name", "total_pop",
                   "male_0_9", "male_10_14", "male_15_19", "male_20_24", "male_25_29",
                   "male_30_34", "male_35_39", "male_40_44", "male_45_49", "male_50_54",
                   "male_55_59", "male_60_64", "male_65_69", "male_70_plus",
                   "female_0_9", "female_10_14", "female_15_19", "female_20_24", "female_25_29",
                   "female_30_34", "female_35_39", "female_40_44", "female_45_49", "female_50_54",
                   "female_55_59", "female_60_64", "female_65_69", "female_70_plus"]
    available = [c for c in target_cols if c in df.columns]
    df = df[available]

    # 타입 변환
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d").dt.date
    df["time_zone"] = pd.to_numeric(df["time_zone"], errors="coerce").astype("Int16")
    for c in df.columns:
        if c not in ("date", "time_zone", "dong_code", "dong_name"):
            df[c] = pd.to_numeric(df[c], errors="coerce")

    df.to_sql("living_population", engine, if_exists="replace", index=False, method="multi", chunksize=5000)
    print(f"  -> {len(df):,} rows loaded")


# ─── 2~4. SGIS tables ──────────────────────────────────────────────
def _load_sgis_table(engine, table_name: str, csv_files: list[str], extra_csvs: list[tuple[str, str]] = None):
    """SGIS long-format 테이블 로드."""
    print(f"[{table_name}]...")
    dfs = []
    for f in csv_files:
        path = PROC / f
        if not path.exists():
            continue
        df = pd.read_csv(path, dtype={"area_code": str})
        # indicator를 파일명에서 추출 (sgis_population_total -> total)
        ind = f.replace("sgis_population_", "").replace("sgis_household_", "").replace("sgis_business_", "").replace(".csv", "")
        if "indicator" not in df.columns:
            df["indicator"] = ind
        dfs.append(df)

    # 추가 CSV (district_* 파일들)
    if extra_csvs:
        for csv_file, indicator_prefix in extra_csvs:
            path = PROC / csv_file
            if not path.exists():
                continue
            edf = pd.read_csv(path, dtype=str)
            # long format으로 변환
            if "year" in edf.columns and "행정동코드" in edf.columns:
                for col in edf.columns:
                    if col in ("year", "행정동코드", "행정동명", "area_count"):
                        continue
                    rows = edf[["year", "행정동코드", col]].copy()
                    rows.columns = ["year", "area_code", "value"]
                    rows["indicator"] = f"{indicator_prefix}_{col}"
                    rows["value"] = pd.to_numeric(rows["value"], errors="coerce")
                    rows["year"] = pd.to_numeric(rows["year"], errors="coerce")
                    dfs.append(rows)

    if not dfs:
        print(f"  -> no data")
        return

    result = pd.concat(dfs, ignore_index=True)
    result["year"] = pd.to_numeric(result["year"], errors="coerce").astype("Int16")
    result["value"] = pd.to_numeric(result["value"], errors="coerce")
    result = result[["year", "area_code", "indicator", "value"]].dropna(subset=["year", "area_code"])

    result.to_sql(table_name, engine, if_exists="replace", index=False, method="multi", chunksize=5000)
    print(f"  -> {len(result):,} rows loaded")


def load_sgis_population(engine):
    print("[2/11] sgis_population...")
    _load_sgis_table(engine, "sgis_population",
                     ["sgis_population_total.csv", "sgis_population_avg_age.csv",
                      "sgis_population_density.csv", "sgis_population_aging.csv",
                      "sgis_population_age_gender.csv"],
                     [("district_resident_pop.csv", "resident"),
                      ("district_avg_age.csv", "avg_age"),
                      ("district_demographics.csv", "demo")])


def load_sgis_household(engine):
    print("[3/11] sgis_household...")
    _load_sgis_table(engine, "sgis_household",
                     ["sgis_household_total.csv", "sgis_household_composition.csv"],
                     [("district_households.csv", "household")])


def load_sgis_business(engine):
    print("[4/11] sgis_business...")
    _load_sgis_table(engine, "sgis_business",
                     ["sgis_business_major_count.csv", "sgis_business_major_workers.csv",
                      "sgis_business_mid_count.csv", "sgis_business_mid_workers.csv"])


# ─── 5. golmok_commercial ──────────────────────────────────────────
def load_golmok_commercial(engine):
    print("[5/11] golmok_commercial...")
    sources = {
        "sales": "golmok_sales_mapo.csv",
        "stores": "golmok_stores_mapo.csv",
        "floating_pop": "golmok_floating_pop_mapo.csv",
        "worker_pop": "golmok_worker_pop_mapo.csv",
        "index": "golmok_index_mapo.csv",
        "change": "commercial_change_mapo.csv",
    }

    rows = []
    for data_type, fname in sources.items():
        path = PROC / fname
        if not path.exists():
            continue
        df = pd.read_csv(path, dtype=str, low_memory=False)

        # 공통 키 컬럼 식별
        quarter_col = next((c for c in df.columns if "YYQU" in c or "quarter" in c.lower() or "분기" in c), None)
        trdar_col = next((c for c in df.columns if "TRDAR_CD" == c), None)
        industry_col = next((c for c in df.columns if "SVC_INDUTY_CD" == c), None)

        if quarter_col is None:
            continue

        for _, row in df.iterrows():
            quarter = row.get(quarter_col, "")
            trdar = row.get(trdar_col, "ALL") if trdar_col else "ALL"
            industry = row.get(industry_col, "ALL") if industry_col else "ALL"

            # 나머지 컬럼을 metrics JSONB로
            skip = {quarter_col, trdar_col, industry_col} if trdar_col else {quarter_col}
            metrics = {}
            for c in df.columns:
                if c not in skip and c != industry_col:
                    val = row[c]
                    if pd.notna(val):
                        try:
                            metrics[c] = float(val)
                        except (ValueError, TypeError):
                            metrics[c] = str(val)

            rows.append({
                "quarter": int(quarter) if quarter else 0,
                "trdar_code": str(trdar),
                "data_type": data_type,
                "industry_code": str(industry),
                "metrics": json.dumps(metrics, ensure_ascii=False),
            })

    result = pd.DataFrame(rows)
    result.to_sql("golmok_commercial", engine, if_exists="replace", index=False, method="multi", chunksize=5000)
    print(f"  -> {len(result):,} rows loaded")


# ─── 6. district_sales ─────────────────────────────────────────────
def load_district_sales(engine):
    print("[6/11] district_sales...")
    df = pd.read_csv(PROC / "district_sales.csv", dtype={"행정동코드": str}, low_memory=False)

    col_map = {
        "STDR_YYQU_CD": "quarter", "행정동코드": "dong_code", "행정동명": "dong_name",
        "SVC_INDUTY_CD": "industry_code", "SVC_INDUTY_CD_NM": "industry_name",
        "THSMON_SELNG_AMT": "monthly_sales", "THSMON_SELNG_CO": "monthly_count",
        "MDWK_SELNG_AMT": "weekday_sales", "WKEND_SELNG_AMT": "weekend_sales",
        "MON_SELNG_AMT": "mon_sales", "TUES_SELNG_AMT": "tue_sales",
        "WED_SELNG_AMT": "wed_sales", "THUR_SELNG_AMT": "thu_sales",
        "FRI_SELNG_AMT": "fri_sales", "SAT_SELNG_AMT": "sat_sales", "SUN_SELNG_AMT": "sun_sales",
        "TMZON_00_06_SELNG_AMT": "time_00_06_sales", "TMZON_06_11_SELNG_AMT": "time_06_11_sales",
        "TMZON_11_14_SELNG_AMT": "time_11_14_sales", "TMZON_14_17_SELNG_AMT": "time_14_17_sales",
        "TMZON_17_21_SELNG_AMT": "time_17_21_sales", "TMZON_21_24_SELNG_AMT": "time_21_24_sales",
        "ML_SELNG_AMT": "male_sales", "FML_SELNG_AMT": "female_sales",
        "AGRDE_10_SELNG_AMT": "age_10_sales", "AGRDE_20_SELNG_AMT": "age_20_sales",
        "AGRDE_30_SELNG_AMT": "age_30_sales", "AGRDE_40_SELNG_AMT": "age_40_sales",
        "AGRDE_50_SELNG_AMT": "age_50_sales", "AGRDE_60_ABOVE_SELNG_AMT": "age_60_above_sales",
        "MDWK_SELNG_CO": "weekday_count", "WKEND_SELNG_CO": "weekend_count",
        "MON_SELNG_CO": "mon_count", "TUES_SELNG_CO": "tue_count",
        "WED_SELNG_CO": "wed_count", "THUR_SELNG_CO": "thu_count",
        "FRI_SELNG_CO": "fri_count", "SAT_SELNG_CO": "sat_count", "SUN_SELNG_CO": "sun_count",
        "TMZON_00_06_SELNG_CO": "time_00_06_count", "TMZON_06_11_SELNG_CO": "time_06_11_count",
        "TMZON_11_14_SELNG_CO": "time_11_14_count", "TMZON_14_17_SELNG_CO": "time_14_17_count",
        "TMZON_17_21_SELNG_CO": "time_17_21_count", "TMZON_21_24_SELNG_CO": "time_21_24_count",
        "ML_SELNG_CO": "male_count", "FML_SELNG_CO": "female_count",
        "AGRDE_10_SELNG_CO": "age_10_count", "AGRDE_20_SELNG_CO": "age_20_count",
        "AGRDE_30_SELNG_CO": "age_30_count", "AGRDE_40_SELNG_CO": "age_40_count",
        "AGRDE_50_SELNG_CO": "age_50_count", "AGRDE_60_ABOVE_SELNG_CO": "age_60_above_count",
    }
    rename = {k: v for k, v in col_map.items() if k in df.columns}
    df = df.rename(columns=rename)
    target = [v for v in col_map.values() if v in df.columns]
    df = df[target]

    df.to_sql("district_sales", engine, if_exists="replace", index=False, method="multi", chunksize=5000)
    print(f"  -> {len(df):,} rows loaded")


# ─── 7. store_info ─────────────────────────────────────────────────
def load_store_info(engine):
    print("[7/11] store_info...")
    df = pd.read_csv(PROC / "store_info_mapo.csv", dtype=str, low_memory=False)

    col_map = {
        "상가업소번호": "store_id", "상호명": "store_name",
        "행정동코드": "dong_code", "행정동명": "dong_name",
        "지번주소": "address", "도로명주소": "road_address",
        "위도": "lat", "경도": "lon",
        "상권업종대분류코드": "industry_l_code", "상권업종대분류명": "industry_l",
        "상권업종중분류코드": "industry_m_code", "상권업종중분류명": "industry_m",
        "상권업종소분류코드": "industry_s_code", "상권업종소분류명": "industry_s",
        "건물명": "building_name", "층정보": "floor_info",
    }
    rename = {k: v for k, v in col_map.items() if k in df.columns}
    df = df.rename(columns=rename)
    target = [v for v in col_map.values() if v in df.columns]
    df = df[target]
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")

    df.to_sql("store_info", engine, if_exists="replace", index=False, method="multi", chunksize=5000)
    print(f"  -> {len(df):,} rows loaded")


# ─── 8. store_quarterly ────────────────────────────────────────────
def load_store_quarterly(engine):
    print("[8/11] store_quarterly...")
    df = pd.read_csv(PROC / "district_stores.csv", dtype={"행정동코드": str}, low_memory=False)

    col_map = {
        "STDR_YYQU_CD": "quarter", "행정동코드": "dong_code", "행정동명": "dong_name",
        "SVC_INDUTY_CD": "industry_code", "SVC_INDUTY_CD_NM": "industry_name",
        "STOR_CO": "store_count", "OPBIZ_STOR_CO": "open_count",
        "CLSBIZ_STOR_CO": "close_count", "CLSBIZ_RT": "closure_rate",
        "FRC_STOR_CO": "franchise_count",
    }
    # district_store_timeseries도 매핑
    ts_map = {
        "quarter": "quarter", "dong_code": "dong_code", "dong_name": "dong_name",
        "industry_code": "industry_code", "industry_name": "industry_name",
        "store_count": "store_count", "open_count": "open_count", "close_count": "close_count",
    }

    rename = {k: v for k, v in col_map.items() if k in df.columns}
    df = df.rename(columns=rename)
    target = [v for v in col_map.values() if v in df.columns]
    df = df[target]

    df.to_sql("store_quarterly", engine, if_exists="replace", index=False, method="multi", chunksize=5000)
    print(f"  -> {len(df):,} rows loaded")


# ─── 9. rent_cost ──────────────────────────────────────────────────
def load_rent_cost(engine):
    print("[9/11] rent_cost...")
    rows = []

    # building rent
    rb = pd.read_csv(PROC / "rent_building_mapo.csv")
    for _, r in rb.iterrows():
        rows.append({
            "data_type": str(r.get("source", "building_rent")),
            "area_name": r.get("area_name", ""),
            "year": int(r["year"]) if pd.notna(r.get("year")) else None,
            "quarter": int(r["quarter"]) if pd.notna(r.get("quarter")) else None,
            "rent": r.get("rent"), "vacancy_rate": r.get("vacancy_rate"),
            "investment_return": r.get("investment_return"),
            "income_return": r.get("income_return"),
            "capital_return": r.get("capital_return"),
            "source": str(r.get("source", "building_rent")),
        })

    # commercial trade
    ct = pd.read_csv(PROC / "commercial_trade_mapo.csv", dtype=str, low_memory=False)
    price_col = next((c for c in ct.columns if "거래금액" in c), None)
    area_col = next((c for c in ct.columns if "전용" in c or "연면적" in c), None)
    date_col = next((c for c in ct.columns if "계약년월" in c or "계약일" in c), None)
    floor_col = next((c for c in ct.columns if c == "층"), None)
    addr_col = next((c for c in ct.columns if "도로명" in c), None)

    for _, r in ct.iterrows():
        price_val = str(r.get(price_col, "")).replace(",", "")
        rows.append({
            "data_type": "trade",
            "area_name": r.get(addr_col, "") if addr_col else "",
            "transaction_date": r.get(date_col, "") if date_col else "",
            "price": int(price_val) if price_val.isdigit() else None,
            "floor_area": float(r[area_col]) if area_col and pd.notna(r.get(area_col)) else None,
            "floor": r.get(floor_col, "") if floor_col else "",
            "source": "molit_trade",
        })

    result = pd.DataFrame(rows)
    result.to_sql("rent_cost", engine, if_exists="replace", index=False, method="multi", chunksize=5000)
    print(f"  -> {len(result):,} rows loaded")


# ─── 10. dong_mapping ──────────────────────────────────────────────
def load_dong_mapping(engine):
    print("[10/11] dong_mapping...")
    dp = pd.read_csv(PROC / "district_population.csv", dtype={"dong_code": str})
    mapping = pd.read_csv(PROC / "trdar_dong_mapping.csv", dtype=str)

    # 동별 상권코드 목록
    trdar_by_dong = mapping.groupby("행정동명")["TRDAR_CD"].apply(list).to_dict()

    # district_demographics에서 avg_age, total_households
    demo = pd.read_csv(PROC / "district_demographics.csv")

    rows = []
    for _, r in dp.iterrows():
        dong_name = r["dong_name"]
        demo_row = demo[demo["행정동명"] == dong_name] if "행정동명" in demo.columns else demo[demo["dong_name"] == dong_name] if "dong_name" in demo.columns else pd.DataFrame()
        rows.append({
            "dong_code": r["dong_code"],
            "dong_name": dong_name,
            "resident_pop": int(r["resident_pop"]) if pd.notna(r.get("resident_pop")) else None,
            "floating_pop": r.get("floating_pop"),
            "avg_age": float(demo_row["avg_age"].iloc[0]) if len(demo_row) > 0 and "avg_age" in demo_row.columns else None,
            "total_households": int(demo_row["total_households"].iloc[0]) if len(demo_row) > 0 and "total_households" in demo_row.columns else None,
            "trdar_codes": json.dumps(trdar_by_dong.get(dong_name, []), ensure_ascii=False),
        })

    result = pd.DataFrame(rows)
    result.to_sql("dong_mapping", engine, if_exists="replace", index=False, method="multi", chunksize=100)
    print(f"  -> {len(result):,} rows loaded")


# ─── 11. simulation_result ─────────────────────────────────────────
def load_simulation_result(engine):
    print("[11/11] simulation_result...")
    # 빈 테이블 생성만 (데이터 없음)
    print("  -> empty table (created by schema)")


# ─── Main ───────────────────────────────────────────────────────────
LOADERS = {
    "living_population": load_living_population,
    "sgis_population": load_sgis_population,
    "sgis_household": load_sgis_household,
    "sgis_business": load_sgis_business,
    "golmok_commercial": load_golmok_commercial,
    "district_sales": load_district_sales,
    "store_info": load_store_info,
    "store_quarterly": load_store_quarterly,
    "rent_cost": load_rent_cost,
    "dong_mapping": load_dong_mapping,
    "simulation_result": load_simulation_result,
}


def main():
    parser = argparse.ArgumentParser(description="CSV -> PostgreSQL ETL")
    parser.add_argument("--table", type=str, help="Load specific table only")
    parser.add_argument("--db-url", type=str, default=DB_URL, help="Database URL")
    args = parser.parse_args()

    engine = get_engine(args.db_url)
    print(f"Connected to {args.db_url}\n")

    if args.table:
        if args.table not in LOADERS:
            print(f"Unknown table: {args.table}. Available: {list(LOADERS.keys())}")
            return
        LOADERS[args.table](engine)
    else:
        for name, loader in LOADERS.items():
            loader(engine)

    # 적재 결과 확인
    print("\n=== Load Summary ===")
    with engine.connect() as conn:
        for table in LOADERS:
            try:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
                print(f"  {table:25s}: {count:>10,} rows")
            except Exception:
                print(f"  {table:25s}: (not created)")

    engine.dispose()
    print("\nDone.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Commit**

```bash
git add data/pipeline/
git commit -m "IM3-28: CSV->PostgreSQL ETL 파이프라인 구현 (11개 테이블)"
```

---

### Task 6: Run Migration + ETL

**Requires:** Docker Compose PostgreSQL running

- [ ] **Step 1: Start PostgreSQL**

Run:
```bash
cd "C:/Users/804/Documents/final project" && docker compose up -d db
```
Expected: PostgreSQL container running on port 5432

- [ ] **Step 2: Run Alembic migration**

Run:
```bash
cd "C:/Users/804/Documents/final project/backend" && alembic upgrade head
```
Expected: "Running upgrade -> (revision), initial schema 11 tables"

- [ ] **Step 3: Run ETL pipeline**

Run:
```bash
cd "C:/Users/804/Documents/final project/data" && python pipeline/load_to_db.py
```
Expected output:
```
[1/11] living_population...
  -> 968,064 rows loaded
[2/11] sgis_population...
  -> ~190,000 rows loaded
...
[11/11] simulation_result...
  -> empty table

=== Load Summary ===
  living_population       :    968,064 rows
  sgis_population         :    ~190,000 rows
  ...
  dong_mapping            :         16 rows
  simulation_result       :          0 rows

Done.
```

- [ ] **Step 4: Verify with psql**

Run:
```bash
docker exec -it $(docker ps -q -f name=db) psql -U postgres -d mapo_simulator -c "\dt"
```
Expected: 11 tables listed

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "IM3-28: 데이터 파이프라인 실행 완료 — 11개 테이블 적재"
```

---

### Task 7: Lint + Final Verification

- [ ] **Step 1: Run ruff**

```bash
cd "C:/Users/804/Documents/final project" && ruff check --fix backend/src/database/models.py backend/src/database/postgres.py data/pipeline/load_to_db.py && ruff format backend/src/database/models.py backend/src/database/postgres.py data/pipeline/load_to_db.py
```

- [ ] **Step 2: Run all tests**

```bash
cd "C:/Users/804/Documents/final project" && python -m pytest tests/test_database.py -v
```
Expected: All PASS

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "IM3-28: lint + 테스트 통과 확인"
```
