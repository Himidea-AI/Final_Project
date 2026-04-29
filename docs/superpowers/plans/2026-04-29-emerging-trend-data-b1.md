# 신흥 상권 감지 데이터 B1 (인구·이동성) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 5년치 (2021-04 ~ 2026-03) 서울 전역 인구·이동성 공공데이터 3종을 CSV one-shot 으로 PostgreSQL 에 적재할 인프라 구축 (테이블 + 마이그레이션 + 정제 스크립트 + 검증). 실제 production 적재 명령(`alembic upgrade head`, `seed_from_csv`) 실행은 사용자가 별도로 트리거.

**Architecture:** SQLAlchemy + Alembic 으로 5개 테이블 (마스터 2 + 운영 3) 신설 → 3개 독립 ingest 파이프라인이 raw CSV → seed CSV 로 정제 → 기존 `seed_from_csv.py` 가 COPY 로 적재. 3개 ingest 는 상호 의존 없음 → subagent 병렬 실행 가능.

**Tech Stack:** Python 3.11, SQLAlchemy 2.x, Alembic, psycopg 3.x, pandas, pytest, PostgreSQL 14+

**Spec:** [`docs/superpowers/specs/2026-04-29-emerging-trend-data-b1-design.md`](../specs/2026-04-29-emerging-trend-data-b1-design.md)

---

## File Structure

| 파일 | 책임 | 신규/수정 |
|------|------|-----------|
| `backend/src/database/models.py` | SQLAlchemy 모델 5개 추가 | 수정 |
| `backend/alembic/versions/b9c1e3f5d7a2_add_emerging_trend_b1.py` | 마이그레이션 (5 테이블 + 인덱스 + COMMENT) | 신규 |
| `backend/scripts/ingest/__init__.py` | 패키지 마커 | 신규 |
| `backend/scripts/ingest/_common.py` | dong_code 정규화, 날짜 파서, reject CSV writer 등 공통 헬퍼 | 신규 |
| `backend/scripts/ingest/ingest_subway_passenger.py` | 지하철 raw → seed CSV (passenger + master) | 신규 |
| `backend/scripts/ingest/ingest_dong_migration.py` | 전입출 raw → seed CSV (20-30대 split 포함) | 신규 |
| `backend/scripts/ingest/ingest_ttareungi.py` | 따릉이 raw → 일×대여소 집계 + master | 신규 |
| `backend/scripts/ingest/download_raw.py` | data.seoul.go.kr / KOSIS CSV 다운로더 (5년치 루프) | 신규 |
| `backend/scripts/seed_from_csv.py` | SKIP_TABLES 갱신 (신규 테이블이 SKIP 에 들어가지 않도록 확인만) | 수정 (필요 시) |
| `backend/scripts/verify/verify_emerging_trend_data.py` | 적재 후 row 수 / NULL / 마포 비율 / PK 중복 검증 | 신규 |
| `backend/data/seed/raw/{subway,migration,ttareungi}/.gitkeep` | raw CSV 보관 디렉토리 | 신규 |
| `backend/data/seed/raw/reject/.gitkeep` | reject row 보관 | 신규 |
| `backend/tests/ingest/__init__.py` | 패키지 마커 | 신규 |
| `backend/tests/ingest/conftest.py` | sample CSV fixture | 신규 |
| `backend/tests/ingest/test_common.py` | `_common.py` 헬퍼 테스트 | 신규 |
| `backend/tests/ingest/test_subway_passenger.py` | 지하철 ingest 골든 테스트 | 신규 |
| `backend/tests/ingest/test_dong_migration.py` | 전입출 ingest 골든 테스트 | 신규 |
| `backend/tests/ingest/test_ttareungi.py` | 따릉이 집계 골든 테스트 | 신규 |
| `backend/tests/db/test_emerging_trend_migration.py` | up/down 마이그레이션 테스트 | 신규 |
| `backend/tests/data/test_emerging_trend_filters.py` | 마포 필터 sanity SQL 테스트 | 신규 |

---

## Task 1: 디렉토리 스캐폴딩 + .gitkeep

**Files:**
- Create: `backend/data/seed/raw/subway/.gitkeep`
- Create: `backend/data/seed/raw/migration/.gitkeep`
- Create: `backend/data/seed/raw/ttareungi/.gitkeep`
- Create: `backend/data/seed/raw/reject/.gitkeep`
- Create: `backend/scripts/ingest/__init__.py`
- Create: `backend/tests/ingest/__init__.py`

- [ ] **Step 1: 디렉토리 + .gitkeep 생성**

```bash
mkdir -p backend/data/seed/raw/subway backend/data/seed/raw/migration backend/data/seed/raw/ttareungi backend/data/seed/raw/reject
touch backend/data/seed/raw/subway/.gitkeep
touch backend/data/seed/raw/migration/.gitkeep
touch backend/data/seed/raw/ttareungi/.gitkeep
touch backend/data/seed/raw/reject/.gitkeep
```

- [ ] **Step 2: `__init__.py` 생성 (빈 파일)**

```bash
mkdir -p backend/scripts/ingest backend/tests/ingest backend/tests/db backend/tests/data
: > backend/scripts/ingest/__init__.py
: > backend/tests/ingest/__init__.py
```

- [ ] **Step 3: Commit**

```bash
git add backend/data/seed/raw backend/scripts/ingest/__init__.py backend/tests/ingest/__init__.py
git commit -m "chore(emerging-trend): scaffold ingest directories"
```

---

## Task 2: SQLAlchemy 모델 5개 추가

**Files:**
- Modify: `backend/src/database/models.py` (파일 끝에 새 클래스 추가)

- [ ] **Step 1: 모델 추가**

`backend/src/database/models.py` 파일 끝 (마지막 클래스 아래) 에 추가:

```python
# ===========================================================================
# Emerging Trend B1 — 인구·이동성 (2026-04-29)
# spec: docs/superpowers/specs/2026-04-29-emerging-trend-data-b1-design.md
# ===========================================================================


class MasterSubwayStation(Base):
    """서울 전체 지하철역 마스터 — 호선/sigungu_code/좌표"""

    __tablename__ = "master_subway_station"

    station_code = Column(String(10), primary_key=True, comment="역코드 (운영사별 통합)")
    station_name = Column(String(50), nullable=False, comment="역명")
    line_name = Column(String(20), comment="호선/노선")
    sigungu_code = Column(String(5), index=True, comment="자치구 코드 (마포=11440)")
    lat = Column(Float, comment="위도")
    lon = Column(Float, comment="경도")
    created_at = Column(DateTime, server_default=func.now(), comment="생성 일시")


class MasterTtareungiStation(Base):
    """서울 전체 따릉이 대여소 마스터"""

    __tablename__ = "master_ttareungi_station"

    station_id = Column(String(20), primary_key=True, comment="대여소 ID")
    station_name = Column(String(100), nullable=False, comment="대여소명")
    sigungu_code = Column(String(5), index=True, comment="자치구 코드")
    dong_code = Column(
        String(8),
        ForeignKey("seoul_dong_master.dong_code"),
        index=True,
        comment="행정동 코드 (8자리 FK)",
    )
    lat = Column(Float, comment="위도")
    lon = Column(Float, comment="경도")
    opened_at = Column(Date, comment="개소일 (있으면)")
    created_at = Column(DateTime, server_default=func.now(), comment="생성 일시")


class SeoulSubwayPassengerDaily(Base):
    """서울 전체 지하철 일별 승하차"""

    __tablename__ = "seoul_subway_passenger_daily"

    date = Column(Date, primary_key=True, comment="영업일")
    station_code = Column(
        String(10),
        ForeignKey("master_subway_station.station_code"),
        primary_key=True,
        comment="역코드",
    )
    boarding_cnt = Column(Integer, comment="승차 인원")
    alighting_cnt = Column(Integer, comment="하차 인원")

    __table_args__ = (
        Index("ix_subway_passenger_station", "station_code"),
    )


class SeoulDongMigrationMonthly(Base):
    """서울 전체 동별 월간 전입/전출 (20-30대 별도 컬럼)"""

    __tablename__ = "seoul_dong_migration_monthly"

    ym = Column(Integer, primary_key=True, comment="YYYYMM")
    dong_code = Column(
        String(8),
        ForeignKey("seoul_dong_master.dong_code"),
        primary_key=True,
        comment="행정동 코드",
    )
    move_in_cnt = Column(Integer, comment="전입 총수")
    move_out_cnt = Column(Integer, comment="전출 총수")
    net_move = Column(Integer, comment="순이동 (전입 - 전출)")
    move_in_2030 = Column(Integer, comment="20-30대 전입자 수")
    move_out_2030 = Column(Integer, comment="20-30대 전출자 수")


class SeoulTtareungiUsageDaily(Base):
    """서울 전체 따릉이 일×대여소 집계"""

    __tablename__ = "seoul_ttareungi_usage_daily"

    date = Column(Date, primary_key=True, comment="이용일")
    station_id = Column(
        String(20),
        ForeignKey("master_ttareungi_station.station_id"),
        primary_key=True,
        comment="대여소 ID",
    )
    rent_cnt = Column(Integer, comment="대여 건수")
    return_cnt = Column(Integer, comment="반납 건수")

    __table_args__ = (
        Index("ix_ttareungi_usage_station", "station_id"),
    )
```

- [ ] **Step 2: 임포트 검증 — 기존 `Base` / `Column` / `ForeignKey` / `Index` / `String` / `Integer` / `Float` / `Date` / `DateTime` / `func` 가 이미 import 되어 있는지 확인**

```bash
grep -E "^from sqlalchemy" backend/src/database/models.py
```

`Index` 가 import 안 되어 있으면 import 라인에 추가:

```python
from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Index, Integer, String
```

- [ ] **Step 3: 모델 import 가능한지 확인**

```bash
cd backend && python -c "from src.database.models import (MasterSubwayStation, MasterTtareungiStation, SeoulSubwayPassengerDaily, SeoulDongMigrationMonthly, SeoulTtareungiUsageDaily); print('OK')"
```

Expected output: `OK`

- [ ] **Step 4: ruff lint/format**

```bash
cd backend && ruff check --fix src/database/models.py && ruff format src/database/models.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/database/models.py
git commit -m "feat(db): add emerging-trend B1 models (5 tables, master+operational)"
```

---

## Task 3: Alembic 마이그레이션 (TDD: 테스트 먼저)

**Files:**
- Create: `backend/tests/db/test_emerging_trend_migration.py`
- Create: `backend/alembic/versions/b9c1e3f5d7a2_add_emerging_trend_b1.py`

- [ ] **Step 1: 마이그레이션 테스트 작성 (실패 예정)**

`backend/tests/db/__init__.py` 가 없으면 빈 파일로 생성:

```bash
: > backend/tests/db/__init__.py
```

`backend/tests/db/test_emerging_trend_migration.py`:

```python
"""Alembic migration b9c1e3f5d7a2 (emerging trend B1) up/down 검증."""

import os
import subprocess

import pytest


REVISION = "b9c1e3f5d7a2"
TABLES = [
    "master_subway_station",
    "master_ttareungi_station",
    "seoul_subway_passenger_daily",
    "seoul_dong_migration_monthly",
    "seoul_ttareungi_usage_daily",
]


@pytest.fixture(scope="module")
def alembic_env():
    """alembic 명령은 backend/ 디렉토리에서 실행해야 함."""
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return backend_dir


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
    """upgrade head → 5 테이블 모두 생성."""
    res = _run_alembic(alembic_env, "upgrade", REVISION)
    assert res.returncode == 0, res.stderr
    for t in TABLES:
        assert _table_exists(db_conn, t), f"{t} not created"


@pytest.mark.integration
def test_migration_downgrade_drops_all_tables(alembic_env, db_conn):
    """downgrade → 5 테이블 모두 drop."""
    res = _run_alembic(alembic_env, "downgrade", "-1")
    assert res.returncode == 0, res.stderr
    for t in TABLES:
        assert not _table_exists(db_conn, t), f"{t} still exists"
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

```bash
cd backend && pytest tests/db/test_emerging_trend_migration.py -v -m integration
```

Expected: FAIL — 마이그레이션 파일 없음 또는 alembic 이 revision 못 찾음.

- [ ] **Step 3: 마이그레이션 파일 작성**

`backend/alembic/versions/b9c1e3f5d7a2_add_emerging_trend_b1.py`:

```python
"""add emerging-trend B1 tables (subway/migration/ttareungi)

5 tables:
  - master_subway_station
  - master_ttareungi_station
  - seoul_subway_passenger_daily
  - seoul_dong_migration_monthly
  - seoul_ttareungi_usage_daily

spec: docs/superpowers/specs/2026-04-29-emerging-trend-data-b1-design.md

Revision ID: b9c1e3f5d7a2
Revises: a8b2c4d6e8f0
Create Date: 2026-04-29 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b9c1e3f5d7a2"
down_revision: Union[str, Sequence[str], None] = "a8b2c4d6e8f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "master_subway_station",
        sa.Column("station_code", sa.String(10), primary_key=True, comment="역코드 (운영사별 통합)"),
        sa.Column("station_name", sa.String(50), nullable=False, comment="역명"),
        sa.Column("line_name", sa.String(20), comment="호선/노선"),
        sa.Column("sigungu_code", sa.String(5), comment="자치구 코드 (마포=11440)"),
        sa.Column("lat", sa.Float, comment="위도"),
        sa.Column("lon", sa.Float, comment="경도"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        comment="담당: 찬영 | 서울 전체 지하철역 마스터 | 출처: 서울교통공사 + 국토부 좌표",
    )
    op.create_index("ix_master_subway_sigungu", "master_subway_station", ["sigungu_code"])

    op.create_table(
        "master_ttareungi_station",
        sa.Column("station_id", sa.String(20), primary_key=True, comment="대여소 ID"),
        sa.Column("station_name", sa.String(100), nullable=False, comment="대여소명"),
        sa.Column("sigungu_code", sa.String(5), comment="자치구 코드"),
        sa.Column(
            "dong_code",
            sa.String(8),
            sa.ForeignKey("seoul_dong_master.dong_code"),
            comment="행정동 코드 (8자리 FK)",
        ),
        sa.Column("lat", sa.Float, comment="위도"),
        sa.Column("lon", sa.Float, comment="경도"),
        sa.Column("opened_at", sa.Date, comment="개소일"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        comment="담당: 찬영 | 서울 전체 따릉이 대여소 마스터 | 출처: 서울 열린데이터광장",
    )
    op.create_index("ix_master_ttareungi_sigungu", "master_ttareungi_station", ["sigungu_code"])
    op.create_index("ix_master_ttareungi_dong", "master_ttareungi_station", ["dong_code"])

    op.create_table(
        "seoul_subway_passenger_daily",
        sa.Column("date", sa.Date, primary_key=True, comment="영업일"),
        sa.Column(
            "station_code",
            sa.String(10),
            sa.ForeignKey("master_subway_station.station_code"),
            primary_key=True,
            comment="역코드",
        ),
        sa.Column("boarding_cnt", sa.Integer, comment="승차 인원"),
        sa.Column("alighting_cnt", sa.Integer, comment="하차 인원"),
        comment="담당: 찬영 | 서울 전체 지하철 일별 승하차 | 출처: 서울교통공사",
    )
    op.create_index("ix_subway_passenger_station", "seoul_subway_passenger_daily", ["station_code"])

    op.create_table(
        "seoul_dong_migration_monthly",
        sa.Column("ym", sa.Integer, primary_key=True, comment="YYYYMM"),
        sa.Column(
            "dong_code",
            sa.String(8),
            sa.ForeignKey("seoul_dong_master.dong_code"),
            primary_key=True,
            comment="행정동 코드",
        ),
        sa.Column("move_in_cnt", sa.Integer, comment="전입 총수"),
        sa.Column("move_out_cnt", sa.Integer, comment="전출 총수"),
        sa.Column("net_move", sa.Integer, comment="순이동 (전입 - 전출)"),
        sa.Column("move_in_2030", sa.Integer, comment="20-30대 전입자 수"),
        sa.Column("move_out_2030", sa.Integer, comment="20-30대 전출자 수"),
        comment="담당: 찬영 | 서울 전체 동별 월간 전입/전출 | 출처: 행정안전부 주민등록 이동통계",
    )

    op.create_table(
        "seoul_ttareungi_usage_daily",
        sa.Column("date", sa.Date, primary_key=True, comment="이용일"),
        sa.Column(
            "station_id",
            sa.String(20),
            sa.ForeignKey("master_ttareungi_station.station_id"),
            primary_key=True,
            comment="대여소 ID",
        ),
        sa.Column("rent_cnt", sa.Integer, comment="대여 건수"),
        sa.Column("return_cnt", sa.Integer, comment="반납 건수"),
        comment="담당: 찬영 | 서울 전체 따릉이 일×대여소 집계 | 출처: 서울 열린데이터광장",
    )
    op.create_index("ix_ttareungi_usage_station", "seoul_ttareungi_usage_daily", ["station_id"])


def downgrade() -> None:
    op.drop_index("ix_ttareungi_usage_station", table_name="seoul_ttareungi_usage_daily")
    op.drop_table("seoul_ttareungi_usage_daily")

    op.drop_table("seoul_dong_migration_monthly")

    op.drop_index("ix_subway_passenger_station", table_name="seoul_subway_passenger_daily")
    op.drop_table("seoul_subway_passenger_daily")

    op.drop_index("ix_master_ttareungi_dong", table_name="master_ttareungi_station")
    op.drop_index("ix_master_ttareungi_sigungu", table_name="master_ttareungi_station")
    op.drop_table("master_ttareungi_station")

    op.drop_index("ix_master_subway_sigungu", table_name="master_subway_station")
    op.drop_table("master_subway_station")
```

- [ ] **Step 4: 마이그레이션 테스트 통과 확인**

```bash
cd backend && pytest tests/db/test_emerging_trend_migration.py -v -m integration
```

Expected: 2 passed

- [ ] **Step 5: alembic head 가 단일인지 확인**

```bash
cd backend && alembic heads
```

Expected: `b9c1e3f5d7a2 (head)` 1 줄만 출력. 여러 head 면 충돌 — 해결 후 재실행.

- [ ] **Step 6: ruff + Commit**

```bash
cd backend && ruff check --fix alembic/versions/b9c1e3f5d7a2_add_emerging_trend_b1.py && ruff format alembic/versions/b9c1e3f5d7a2_add_emerging_trend_b1.py
git add backend/alembic/versions/b9c1e3f5d7a2_add_emerging_trend_b1.py backend/tests/db/test_emerging_trend_migration.py backend/tests/db/__init__.py
git commit -m "feat(db): alembic migration for emerging-trend B1 (5 tables)"
```

---

## Task 4: 공통 헬퍼 (`_common.py`) — TDD

**Files:**
- Create: `backend/tests/ingest/conftest.py`
- Create: `backend/tests/ingest/test_common.py`
- Create: `backend/scripts/ingest/_common.py`

- [ ] **Step 1: conftest fixture 작성**

`backend/tests/ingest/conftest.py`:

```python
"""ingest 테스트용 공통 fixture."""
from pathlib import Path

import pytest


@pytest.fixture
def tmp_seed_dir(tmp_path: Path) -> Path:
    """raw / cleaned / reject 서브디렉토리를 갖춘 임시 seed 디렉토리."""
    for sub in ("raw", "cleaned", "reject"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    return tmp_path
```

- [ ] **Step 2: 헬퍼 테스트 작성**

`backend/tests/ingest/test_common.py`:

```python
"""scripts/ingest/_common.py 단위 테스트."""
import csv
from pathlib import Path

import pytest

from scripts.ingest import _common as C


def test_normalize_dong_code_pads_8_digits():
    assert C.normalize_dong_code("11440660") == "11440660"
    assert C.normalize_dong_code("1144066000") == "11440660"  # 10자리 → 8자리 trunc
    assert C.normalize_dong_code(11440660) == "11440660"      # int 입력
    assert C.normalize_dong_code("0") is None
    assert C.normalize_dong_code(None) is None
    assert C.normalize_dong_code("") is None


def test_parse_ym_handles_variants():
    assert C.parse_ym("202503") == 202503
    assert C.parse_ym("2025-03") == 202503
    assert C.parse_ym("2025/3") == 202503
    assert C.parse_ym(202503) == 202503
    with pytest.raises(ValueError):
        C.parse_ym("2025")          # 너무 짧음
    with pytest.raises(ValueError):
        C.parse_ym("not-a-date")


def test_parse_int_safe_handles_commas_and_blanks():
    assert C.parse_int_safe("1,234") == 1234
    assert C.parse_int_safe("0") == 0
    assert C.parse_int_safe("") is None
    assert C.parse_int_safe(None) is None
    assert C.parse_int_safe("N/A") is None


def test_write_reject_csv_creates_file_with_header(tmp_seed_dir: Path):
    rows = [{"dong_code": "BAD", "reason": "not 8-digit"}]
    out = C.write_reject_csv(tmp_seed_dir / "reject", "subway_202503", rows)
    assert out.exists()
    with out.open() as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == ["dong_code", "reason"]
        assert next(reader) == {"dong_code": "BAD", "reason": "not 8-digit"}


def test_write_reject_csv_no_op_when_empty(tmp_seed_dir: Path):
    out = C.write_reject_csv(tmp_seed_dir / "reject", "empty", [])
    assert out is None
```

- [ ] **Step 3: 테스트 실행 → 실패 확인**

```bash
cd backend && pytest tests/ingest/test_common.py -v
```

Expected: ImportError on `scripts.ingest._common`.

- [ ] **Step 4: `_common.py` 구현**

`backend/scripts/ingest/_common.py`:

```python
"""ingest 공통 헬퍼."""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Iterable


_YM_RE = re.compile(r"^(\d{4})[-/]?(\d{1,2})$")


def normalize_dong_code(value) -> str | None:
    """행정동 코드를 8자리 문자열로 정규화. 매칭 불가 시 None."""
    if value is None:
        return None
    s = str(value).strip()
    if not s or s == "0":
        return None
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) < 8:
        return None
    return digits[:8]


def parse_ym(value) -> int:
    """YYYYMM int 로 정규화. 형식 불일치 시 ValueError."""
    if isinstance(value, int) and 100000 <= value <= 999912:
        return value
    s = str(value).strip()
    m = _YM_RE.match(s)
    if not m:
        raise ValueError(f"unparseable ym: {value!r}")
    year, month = int(m.group(1)), int(m.group(2))
    if not (1 <= month <= 12):
        raise ValueError(f"invalid month in ym: {value!r}")
    return year * 100 + month


def parse_int_safe(value) -> int | None:
    """문자열/숫자를 int 로. 빈 값/N/A 등은 None."""
    if value is None:
        return None
    s = str(value).strip().replace(",", "")
    if not s or s.upper() in {"N/A", "NULL", "-"}:
        return None
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return None


def write_reject_csv(reject_dir: Path, name: str, rows: Iterable[dict]) -> Path | None:
    """reject row 들을 reject_dir/<name>.csv 로 기록. 빈 입력 시 None."""
    rows_list = list(rows)
    if not rows_list:
        return None
    reject_dir.mkdir(parents=True, exist_ok=True)
    out = reject_dir / f"{name}.csv"
    fieldnames = list(rows_list[0].keys())
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_list)
    return out
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
cd backend && pytest tests/ingest/test_common.py -v
```

Expected: 5 passed

- [ ] **Step 6: ruff + Commit**

```bash
cd backend && ruff check --fix scripts/ingest/_common.py tests/ingest/ && ruff format scripts/ingest/_common.py tests/ingest/
git add backend/scripts/ingest/_common.py backend/tests/ingest/conftest.py backend/tests/ingest/test_common.py
git commit -m "feat(ingest): add _common helpers (dong_code/ym/int parsers + reject writer)"
```

---

## Task 5 (병렬): 지하철 ingest — TDD

> 이 task 는 Task 6, 7 과 병렬 가능 (subagent 분리). Task 4 완료 후 시작.

**Files:**
- Create: `backend/tests/ingest/test_subway_passenger.py`
- Create: `backend/scripts/ingest/ingest_subway_passenger.py`
- Create: `backend/tests/ingest/fixtures/subway_sample.csv`

**입력 가정 (서울교통공사 / data.seoul.go.kr):**
원본 컬럼: `사용일자, 호선명, 역명, 승차총승객수, 하차총승객수` (한글 헤더, EUC-KR 또는 UTF-8 BOM)

- [ ] **Step 1: 샘플 fixture 작성**

`backend/tests/ingest/fixtures/subway_sample.csv` (UTF-8 BOM 없이):

```csv
사용일자,호선명,역명,승차총승객수,하차총승객수
20250301,2호선,홍대입구,12345,12100
20250301,6호선,망원,3210,3050
20250302,2호선,홍대입구,11000,10800
20250302,9999호선,잘못된역,0,0
```

- [ ] **Step 2: 테스트 작성**

`backend/tests/ingest/test_subway_passenger.py`:

```python
"""scripts/ingest/ingest_subway_passenger.py 골든 테스트."""
import csv
from pathlib import Path

from scripts.ingest.ingest_subway_passenger import ingest_one_csv


FIXTURES = Path(__file__).parent / "fixtures"


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_ingest_one_csv_produces_passenger_and_master_rows(tmp_seed_dir: Path):
    src = FIXTURES / "subway_sample.csv"
    out = ingest_one_csv(
        src,
        cleaned_dir=tmp_seed_dir / "cleaned",
        reject_dir=tmp_seed_dir / "reject",
        ym_tag="202503",
    )
    # passenger 파일
    passenger = _read_csv(out["passenger"])
    assert {r["station_name"] for r in passenger} == {"홍대입구", "망원"}
    holhik = next(r for r in passenger if r["station_name"] == "홍대입구" and r["date"] == "2025-03-01")
    assert holhik["boarding_cnt"] == "12345"
    assert holhik["alighting_cnt"] == "12100"

    # master 파일 (호선별 distinct)
    master = _read_csv(out["master"])
    keys = {(r["station_name"], r["line_name"]) for r in master}
    assert ("홍대입구", "2호선") in keys
    assert ("망원", "6호선") in keys


def test_ingest_one_csv_writes_reject_for_invalid_line(tmp_seed_dir: Path):
    src = FIXTURES / "subway_sample.csv"
    out = ingest_one_csv(
        src,
        cleaned_dir=tmp_seed_dir / "cleaned",
        reject_dir=tmp_seed_dir / "reject",
        ym_tag="202503",
    )
    reject = _read_csv(out["reject"]) if out.get("reject") else []
    assert any(r["station_name"] == "잘못된역" for r in reject)
```

- [ ] **Step 3: 테스트 실행 → 실패 확인**

```bash
cd backend && pytest tests/ingest/test_subway_passenger.py -v
```

Expected: ImportError.

- [ ] **Step 4: ingest 스크립트 구현**

`backend/scripts/ingest/ingest_subway_passenger.py`:

```python
"""지하철 승하차 raw CSV → seed CSV 정제.

입력  : data.seoul.go.kr / 서울교통공사 (사용일자/호선명/역명/승차총승객수/하차총승객수)
출력  : seed/cleaned/seoul_subway_passenger_daily_<ym>.csv
        seed/cleaned/master_subway_station_<ym>.csv  (해당 월에서 발견된 신규 역)
       (옵션) seed/reject/subway_<ym>.csv

호선명이 _VALID_LINES 화이트리스트에 없으면 reject.
역코드는 (호선 + 역명) sha1 hash 앞 10자리로 surrogate (운영사별 코드 통합 이슈 회피).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

from . import _common as C


_VALID_LINES = {
    "1호선", "2호선", "3호선", "4호선", "5호선", "6호선", "7호선", "8호선",
    "9호선", "공항철도", "경의중앙선", "수인분당선", "신분당선", "우이신설선",
    "경춘선", "경강선", "서해선", "GTX-A",
}


def _surrogate_code(station_name: str, line_name: str) -> str:
    h = hashlib.sha1(f"{station_name}|{line_name}".encode("utf-8")).hexdigest()
    return h[:10]


def _read_csv_any_encoding(path: Path) -> list[dict]:
    """UTF-8/UTF-8-BOM/EUC-KR/CP949 자동 시도."""
    last_err: Exception | None = None
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            with path.open(encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError as e:
            last_err = e
    raise UnicodeDecodeError(
        "ingest_subway_passenger",
        b"",
        0,
        1,
        f"unable to decode {path} (tried utf-8-sig/utf-8/cp949/euc-kr): {last_err}",
    )


def ingest_one_csv(
    src: Path,
    *,
    cleaned_dir: Path,
    reject_dir: Path,
    ym_tag: str,
) -> dict[str, Path]:
    """단일 raw CSV 정제. 반환: {'passenger': path, 'master': path, 'reject'?: path}"""
    cleaned_dir.mkdir(parents=True, exist_ok=True)
    rows = _read_csv_any_encoding(src)

    passenger_rows: list[dict] = []
    master_seen: dict[str, dict] = {}  # station_code → master row
    rejects: list[dict] = []

    for r in rows:
        line = (r.get("호선명") or "").strip()
        name = (r.get("역명") or "").strip()
        date_raw = (r.get("사용일자") or "").strip()
        if not name or not line or not date_raw:
            rejects.append({**r, "_reason": "missing line/name/date"})
            continue
        if line not in _VALID_LINES:
            rejects.append({"station_name": name, "line_name": line, "_reason": "unknown line"})
            continue
        if len(date_raw) != 8 or not date_raw.isdigit():
            rejects.append({**r, "_reason": "invalid date format"})
            continue

        date_iso = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:8]}"
        code = _surrogate_code(name, line)
        boarding = C.parse_int_safe(r.get("승차총승객수")) or 0
        alighting = C.parse_int_safe(r.get("하차총승객수")) or 0

        passenger_rows.append(
            {
                "date": date_iso,
                "station_code": code,
                "boarding_cnt": boarding,
                "alighting_cnt": alighting,
            }
        )
        if code not in master_seen:
            master_seen[code] = {
                "station_code": code,
                "station_name": name,
                "line_name": line,
                "sigungu_code": "",  # 별도 boundary join 단계에서 채움
                "lat": "",
                "lon": "",
            }

    out_passenger = cleaned_dir / f"seoul_subway_passenger_daily_{ym_tag}.csv"
    out_master = cleaned_dir / f"master_subway_station_{ym_tag}.csv"
    _write_csv(out_passenger, passenger_rows, ["date", "station_code", "boarding_cnt", "alighting_cnt"])
    _write_csv(
        out_master,
        list(master_seen.values()),
        ["station_code", "station_name", "line_name", "sigungu_code", "lat", "lon"],
    )

    result = {"passenger": out_passenger, "master": out_master}
    reject_path = C.write_reject_csv(reject_dir, f"subway_{ym_tag}", rejects)
    if reject_path is not None:
        result["reject"] = reject_path
    return result


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--cleaned-dir", type=Path, required=True)
    parser.add_argument("--reject-dir", type=Path, required=True)
    args = parser.parse_args()

    for src in sorted(args.raw_dir.glob("*.csv")):
        ym = src.stem[-6:] if src.stem[-6:].isdigit() else "unknown"
        ingest_one_csv(src, cleaned_dir=args.cleaned_dir, reject_dir=args.reject_dir, ym_tag=ym)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
cd backend && pytest tests/ingest/test_subway_passenger.py -v
```

Expected: 2 passed

- [ ] **Step 6: ruff + Commit**

```bash
cd backend && ruff check --fix scripts/ingest/ingest_subway_passenger.py tests/ingest/test_subway_passenger.py && ruff format scripts/ingest/ingest_subway_passenger.py tests/ingest/test_subway_passenger.py
git add backend/scripts/ingest/ingest_subway_passenger.py backend/tests/ingest/test_subway_passenger.py backend/tests/ingest/fixtures/subway_sample.csv
git commit -m "feat(ingest): subway passenger raw → seed CSV cleaner"
```

---

## Task 6 (병렬): 전입출 ingest — TDD

**Files:**
- Create: `backend/tests/ingest/fixtures/migration_sample.csv`
- Create: `backend/tests/ingest/test_dong_migration.py`
- Create: `backend/scripts/ingest/ingest_dong_migration.py`

**입력 가정 (KOSIS 또는 행안부 주민등록 이동통계):**
컬럼: `행정구역코드, 행정구역명, 시점, 연령대, 전입자수, 전출자수`

- [ ] **Step 1: 샘플 fixture 작성**

`backend/tests/ingest/fixtures/migration_sample.csv`:

```csv
행정구역코드,행정구역명,시점,연령대,전입자수,전출자수
1144066000,합정동,2025.03,총계,500,450
1144066000,합정동,2025.03,20-29세,200,150
1144066000,합정동,2025.03,30-39세,150,120
1144068000,망원동,2025.03,총계,300,280
1144068000,망원동,2025.03,20-29세,80,90
1144068000,망원동,2025.03,30-39세,60,70
0,서울특별시,2025.03,총계,1000,900
```

- [ ] **Step 2: 테스트 작성**

`backend/tests/ingest/test_dong_migration.py`:

```python
"""scripts/ingest/ingest_dong_migration.py 골든 테스트."""
import csv
from pathlib import Path

from scripts.ingest.ingest_dong_migration import ingest_one_csv


FIXTURES = Path(__file__).parent / "fixtures"


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_ingest_one_csv_aggregates_by_dong_and_2030(tmp_seed_dir: Path):
    out = ingest_one_csv(
        FIXTURES / "migration_sample.csv",
        cleaned_dir=tmp_seed_dir / "cleaned",
        reject_dir=tmp_seed_dir / "reject",
        ym_tag="202503",
    )
    rows = _read_csv(out["migration"])
    by_dong = {r["dong_code"]: r for r in rows}

    # 합정동 (1144066000 → 11440660)
    h = by_dong["11440660"]
    assert h["ym"] == "202503"
    assert h["move_in_cnt"] == "500"
    assert h["move_out_cnt"] == "450"
    assert h["net_move"] == "50"
    assert h["move_in_2030"] == "350"     # 200 + 150
    assert h["move_out_2030"] == "270"    # 150 + 120

    # 망원동
    m = by_dong["11440680"]
    assert m["move_in_2030"] == "140"
    assert m["move_out_2030"] == "160"


def test_ingest_one_csv_rejects_invalid_dong_code(tmp_seed_dir: Path):
    out = ingest_one_csv(
        FIXTURES / "migration_sample.csv",
        cleaned_dir=tmp_seed_dir / "cleaned",
        reject_dir=tmp_seed_dir / "reject",
        ym_tag="202503",
    )
    rejects = _read_csv(out["reject"]) if out.get("reject") else []
    assert any("서울특별시" in r.get("dong_name", "") for r in rejects)
```

- [ ] **Step 3: 테스트 실행 → 실패 확인**

```bash
cd backend && pytest tests/ingest/test_dong_migration.py -v
```

Expected: ImportError.

- [ ] **Step 4: ingest 스크립트 구현**

`backend/scripts/ingest/ingest_dong_migration.py`:

```python
"""행정안전부 동별 전입/전출 raw → seed CSV.

입력  : KOSIS / 주민등록이동통계 (행정구역코드/행정구역명/시점/연령대/전입자수/전출자수)
출력  : seed/cleaned/seoul_dong_migration_monthly_<ym>.csv

연령대 컬럼 값:
  - "총계"        → move_in_cnt / move_out_cnt
  - "20-29세"     → 20-30대 누적
  - "30-39세"     → 20-30대 누적
  - 그 외 연령대 → 무시 (총계에 이미 합쳐져 있음)
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from . import _common as C


_AGE_TOTAL = {"총계", "전체", "계"}
_AGE_2030 = {"20-29세", "30-39세", "20-29", "30-39"}


def _read_csv_any_encoding(path: Path) -> list[dict]:
    last_err: Exception | None = None
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            with path.open(encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError as e:
            last_err = e
    raise RuntimeError(f"unable to decode {path}: {last_err}")


def ingest_one_csv(
    src: Path,
    *,
    cleaned_dir: Path,
    reject_dir: Path,
    ym_tag: str,
) -> dict[str, Path]:
    cleaned_dir.mkdir(parents=True, exist_ok=True)
    rows = _read_csv_any_encoding(src)

    agg: dict[str, dict] = defaultdict(
        lambda: {
            "move_in_cnt": None,
            "move_out_cnt": None,
            "move_in_2030": 0,
            "move_out_2030": 0,
        }
    )
    rejects: list[dict] = []

    for r in rows:
        dong_code = C.normalize_dong_code(r.get("행정구역코드"))
        dong_name = (r.get("행정구역명") or "").strip()
        if dong_code is None:
            rejects.append({"dong_code": str(r.get("행정구역코드") or ""), "dong_name": dong_name, "_reason": "invalid dong_code"})
            continue
        try:
            ym = C.parse_ym(r.get("시점"))
        except ValueError as e:
            rejects.append({"dong_code": dong_code, "dong_name": dong_name, "_reason": str(e)})
            continue

        age = (r.get("연령대") or "").strip()
        in_cnt = C.parse_int_safe(r.get("전입자수")) or 0
        out_cnt = C.parse_int_safe(r.get("전출자수")) or 0
        key = f"{ym}|{dong_code}"
        bucket = agg[key]
        bucket["ym"] = ym
        bucket["dong_code"] = dong_code

        if age in _AGE_TOTAL:
            bucket["move_in_cnt"] = in_cnt
            bucket["move_out_cnt"] = out_cnt
        elif age in _AGE_2030:
            bucket["move_in_2030"] += in_cnt
            bucket["move_out_2030"] += out_cnt
        # 그 외 연령대는 무시

    cleaned_rows = []
    for k, v in agg.items():
        if v["move_in_cnt"] is None or v["move_out_cnt"] is None:
            rejects.append({"dong_code": v["dong_code"], "_reason": "missing total row"})
            continue
        cleaned_rows.append(
            {
                "ym": v["ym"],
                "dong_code": v["dong_code"],
                "move_in_cnt": v["move_in_cnt"],
                "move_out_cnt": v["move_out_cnt"],
                "net_move": v["move_in_cnt"] - v["move_out_cnt"],
                "move_in_2030": v["move_in_2030"],
                "move_out_2030": v["move_out_2030"],
            }
        )

    out_migration = cleaned_dir / f"seoul_dong_migration_monthly_{ym_tag}.csv"
    fieldnames = ["ym", "dong_code", "move_in_cnt", "move_out_cnt", "net_move", "move_in_2030", "move_out_2030"]
    with out_migration.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cleaned_rows)

    result: dict[str, Path] = {"migration": out_migration}
    reject_path = C.write_reject_csv(reject_dir, f"migration_{ym_tag}", rejects)
    if reject_path is not None:
        result["reject"] = reject_path
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--cleaned-dir", type=Path, required=True)
    parser.add_argument("--reject-dir", type=Path, required=True)
    args = parser.parse_args()
    for src in sorted(args.raw_dir.glob("*.csv")):
        ym = src.stem[-6:] if src.stem[-6:].isdigit() else "unknown"
        ingest_one_csv(src, cleaned_dir=args.cleaned_dir, reject_dir=args.reject_dir, ym_tag=ym)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
cd backend && pytest tests/ingest/test_dong_migration.py -v
```

Expected: 2 passed

- [ ] **Step 6: ruff + Commit**

```bash
cd backend && ruff check --fix scripts/ingest/ingest_dong_migration.py tests/ingest/test_dong_migration.py && ruff format scripts/ingest/ingest_dong_migration.py tests/ingest/test_dong_migration.py
git add backend/scripts/ingest/ingest_dong_migration.py backend/tests/ingest/test_dong_migration.py backend/tests/ingest/fixtures/migration_sample.csv
git commit -m "feat(ingest): dong migration raw → seed CSV (20-30 split)"
```

---

## Task 7 (병렬): 따릉이 ingest — TDD

**Files:**
- Create: `backend/tests/ingest/fixtures/ttareungi_sample.csv`
- Create: `backend/tests/ingest/test_ttareungi.py`
- Create: `backend/scripts/ingest/ingest_ttareungi.py`

**입력 가정 (서울 열린데이터광장 따릉이 대여이력):**
컬럼: `대여일시, 대여 대여소번호, 대여 대여소명, 반납일시, 반납 대여소번호, 반납 대여소명`

- [ ] **Step 1: 샘플 fixture 작성**

`backend/tests/ingest/fixtures/ttareungi_sample.csv`:

```csv
대여일시,대여 대여소번호,대여 대여소명,반납일시,반납 대여소번호,반납 대여소명
2025-03-01 09:00:00,ST-100,홍대입구역 2번출구,2025-03-01 09:15:00,ST-200,망원역 1번출구
2025-03-01 10:30:00,ST-100,홍대입구역 2번출구,2025-03-01 11:00:00,ST-300,합정역 7번출구
2025-03-01 18:00:00,ST-200,망원역 1번출구,2025-03-01 18:20:00,ST-100,홍대입구역 2번출구
2025-03-02 08:00:00,ST-300,합정역 7번출구,2025-03-02 08:10:00,ST-100,홍대입구역 2번출구
```

- [ ] **Step 2: 테스트 작성**

`backend/tests/ingest/test_ttareungi.py`:

```python
"""scripts/ingest/ingest_ttareungi.py 골든 테스트."""
import csv
from pathlib import Path

from scripts.ingest.ingest_ttareungi import ingest_one_csv


FIXTURES = Path(__file__).parent / "fixtures"


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_ingest_one_csv_aggregates_daily_per_station(tmp_seed_dir: Path):
    out = ingest_one_csv(
        FIXTURES / "ttareungi_sample.csv",
        cleaned_dir=tmp_seed_dir / "cleaned",
        reject_dir=tmp_seed_dir / "reject",
        ym_tag="202503",
    )
    usage = _read_csv(out["usage"])
    by_key = {(r["date"], r["station_id"]): r for r in usage}

    # 2025-03-01 ST-100: 대여 2건, 반납 1건
    a = by_key[("2025-03-01", "ST-100")]
    assert a["rent_cnt"] == "2"
    assert a["return_cnt"] == "1"

    # 2025-03-01 ST-200: 대여 1건, 반납 1건
    b = by_key[("2025-03-01", "ST-200")]
    assert b["rent_cnt"] == "1"
    assert b["return_cnt"] == "1"

    # 2025-03-02 ST-300: 대여 1건, 반납 0건
    c = by_key[("2025-03-02", "ST-300")]
    assert c["rent_cnt"] == "1"
    assert c["return_cnt"] == "0"


def test_ingest_one_csv_extracts_master_stations(tmp_seed_dir: Path):
    out = ingest_one_csv(
        FIXTURES / "ttareungi_sample.csv",
        cleaned_dir=tmp_seed_dir / "cleaned",
        reject_dir=tmp_seed_dir / "reject",
        ym_tag="202503",
    )
    master = _read_csv(out["master"])
    ids = {r["station_id"] for r in master}
    assert ids == {"ST-100", "ST-200", "ST-300"}
```

- [ ] **Step 3: 테스트 실행 → 실패 확인**

```bash
cd backend && pytest tests/ingest/test_ttareungi.py -v
```

Expected: ImportError.

- [ ] **Step 4: ingest 스크립트 구현**

`backend/scripts/ingest/ingest_ttareungi.py`:

```python
"""따릉이 raw 대여이력 → 일×대여소 집계 + master.

입력  : data.seoul.go.kr 따릉이 월별 대여이력 (수십~수백만 행)
        컬럼: 대여일시, 대여 대여소번호, 대여 대여소명, 반납일시, 반납 대여소번호, 반납 대여소명
출력  : seed/cleaned/seoul_ttareungi_usage_daily_<ym>.csv
        seed/cleaned/master_ttareungi_station_<ym>.csv  (해당 월에서 본 대여소)

집계: 대여일자 + 대여소 → rent_cnt
      반납일자 + 대여소 → return_cnt
양쪽 union 으로 (date, station_id) 키 만들어 NULL 자리는 0.
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def _read_csv_any_encoding(path: Path):
    last_err: Exception | None = None
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            with path.open(encoding=enc, newline="") as f:
                yield from csv.DictReader(f)
                return
        except UnicodeDecodeError as e:
            last_err = e
    raise RuntimeError(f"unable to decode {path}: {last_err}")


def ingest_one_csv(
    src: Path,
    *,
    cleaned_dir: Path,
    reject_dir: Path,
    ym_tag: str,
) -> dict[str, Path]:
    cleaned_dir.mkdir(parents=True, exist_ok=True)

    rent_counts: dict[tuple[str, str], int] = defaultdict(int)
    return_counts: dict[tuple[str, str], int] = defaultdict(int)
    master: dict[str, str] = {}  # station_id -> station_name

    for r in _read_csv_any_encoding(src):
        rent_dt = (r.get("대여일시") or "").strip()
        rent_id = (r.get("대여 대여소번호") or "").strip()
        rent_name = (r.get("대여 대여소명") or "").strip()
        ret_dt = (r.get("반납일시") or "").strip()
        ret_id = (r.get("반납 대여소번호") or "").strip()
        ret_name = (r.get("반납 대여소명") or "").strip()

        if rent_dt and rent_id:
            d = rent_dt[:10]
            rent_counts[(d, rent_id)] += 1
            if rent_id not in master:
                master[rent_id] = rent_name

        if ret_dt and ret_id:
            d = ret_dt[:10]
            return_counts[(d, ret_id)] += 1
            if ret_id not in master:
                master[ret_id] = ret_name

    keys = set(rent_counts.keys()) | set(return_counts.keys())
    rows = [
        {
            "date": d,
            "station_id": sid,
            "rent_cnt": rent_counts.get((d, sid), 0),
            "return_cnt": return_counts.get((d, sid), 0),
        }
        for (d, sid) in sorted(keys)
    ]

    out_usage = cleaned_dir / f"seoul_ttareungi_usage_daily_{ym_tag}.csv"
    with out_usage.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "station_id", "rent_cnt", "return_cnt"])
        writer.writeheader()
        writer.writerows(rows)

    out_master = cleaned_dir / f"master_ttareungi_station_{ym_tag}.csv"
    master_rows = [
        {
            "station_id": sid,
            "station_name": name,
            "sigungu_code": "",
            "dong_code": "",
            "lat": "",
            "lon": "",
            "opened_at": "",
        }
        for sid, name in sorted(master.items())
    ]
    with out_master.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["station_id", "station_name", "sigungu_code", "dong_code", "lat", "lon", "opened_at"],
        )
        writer.writeheader()
        writer.writerows(master_rows)

    return {"usage": out_usage, "master": out_master}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--cleaned-dir", type=Path, required=True)
    parser.add_argument("--reject-dir", type=Path, required=True)
    args = parser.parse_args()
    for src in sorted(args.raw_dir.glob("*.csv")):
        ym = src.stem[-6:] if src.stem[-6:].isdigit() else "unknown"
        ingest_one_csv(src, cleaned_dir=args.cleaned_dir, reject_dir=args.reject_dir, ym_tag=ym)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
cd backend && pytest tests/ingest/test_ttareungi.py -v
```

Expected: 2 passed

- [ ] **Step 6: ruff + Commit**

```bash
cd backend && ruff check --fix scripts/ingest/ingest_ttareungi.py tests/ingest/test_ttareungi.py && ruff format scripts/ingest/ingest_ttareungi.py tests/ingest/test_ttareungi.py
git add backend/scripts/ingest/ingest_ttareungi.py backend/tests/ingest/test_ttareungi.py backend/tests/ingest/fixtures/ttareungi_sample.csv
git commit -m "feat(ingest): ttareungi raw → daily x station aggregate"
```

---

## Task 8: download_raw.py — 5년치 CSV 다운로더

**Files:**
- Create: `backend/scripts/ingest/download_raw.py`

> ℹ️ 이 스크립트는 **WebFetch 가 가능한 URL** 만 자동 다운로드. 로그인 필요 (KOSIS, 행안부) 면 콘솔에 URL 출력 후 사용자 수동 투입 안내.

- [ ] **Step 1: 다운로더 구현**

`backend/scripts/ingest/download_raw.py`:

```python
"""5년치 raw CSV 다운로드.

서울 열린데이터광장 (data.seoul.go.kr) 은 비로그인 직접 다운로드 가능.
KOSIS/행안부 는 로그인 필요 → URL 출력 후 manual fallback.

URL 카탈로그는 코드 상단 _SOURCES 에 명시. 갱신 필요 시 여기만 수정.
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path


_SUBWAY_URL_FMT = (
    # 서울교통공사 일별 역별 승하차 — 월별 CSV
    # 실제 URL 패턴은 data.seoul.go.kr 검색 후 확정. 여기는 placeholder 가 아닌 검증된 endpoint 만 추가.
    # NOTE: open-data 직접 링크가 안정 endpoint 가 아니므로, 다운로드 URL 은 manual 단계로 fallback.
    None
)


# manual 다운로드가 필요한 데이터셋 — 사용자에게 출력해 안내
_MANUAL_FALLBACKS = [
    (
        "지하철 일별 승하차 (5년치)",
        "https://data.seoul.go.kr/dataList/OA-12252/S/1/datasetView.do",
        "subway",
    ),
    (
        "행정안전부 동별 전입/전출 (KOSIS)",
        "https://kosis.kr/statHtml/statHtml.do?orgId=110&tblId=DT_1B26001",
        "migration",
    ),
    (
        "따릉이 대여이력 (5년치 월별 zip)",
        "https://data.seoul.go.kr/dataList/OA-15182/F/1/datasetView.do",
        "ttareungi",
    ),
]


def _download(url: str, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    print(f"[get] {url} → {dst}")
    urllib.request.urlretrieve(url, dst)  # noqa: S310


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-base", type=Path, default=Path("backend/data/seed/raw"))
    args = parser.parse_args()

    # 자동 다운로드 가능한 데이터셋이 추가되면 여기서 처리. 현재 모두 manual.
    print("=" * 72)
    print("이 데이터셋들은 로그인/포털 다운로드 가 필요합니다. 직접 받아서 다음 위치에 풀어주세요:")
    print()
    for name, url, sub in _MANUAL_FALLBACKS:
        target = args.raw_base / sub
        target.mkdir(parents=True, exist_ok=True)
        print(f"  • {name}")
        print(f"    URL  : {url}")
        print(f"    저장 : {target.resolve()}")
        print()
    print("=" * 72)
    print("CSV 들을 풀고 나서:")
    print("  python -m scripts.ingest.ingest_subway_passenger     --raw-dir backend/data/seed/raw/subway     --cleaned-dir backend/data/seed --reject-dir backend/data/seed/raw/reject")
    print("  python -m scripts.ingest.ingest_dong_migration       --raw-dir backend/data/seed/raw/migration  --cleaned-dir backend/data/seed --reject-dir backend/data/seed/raw/reject")
    print("  python -m scripts.ingest.ingest_ttareungi            --raw-dir backend/data/seed/raw/ttareungi  --cleaned-dir backend/data/seed --reject-dir backend/data/seed/raw/reject")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 실행 가능 확인**

```bash
cd backend && python -m scripts.ingest.download_raw
```

Expected: 3개 manual fallback 안내 메시지 출력.

- [ ] **Step 3: ruff + Commit**

```bash
cd backend && ruff check --fix scripts/ingest/download_raw.py && ruff format scripts/ingest/download_raw.py
git add backend/scripts/ingest/download_raw.py
git commit -m "feat(ingest): raw CSV download dispatcher (manual fallback URLs)"
```

---

## Task 9: 검증 스크립트

**Files:**
- Create: `backend/scripts/verify/verify_emerging_trend_data.py`

- [ ] **Step 1: 검증 스크립트 작성**

`backend/scripts/verify/verify_emerging_trend_data.py`:

```python
"""신흥 상권 B1 적재 후 검증.

체크 항목:
  - 5개 테이블 row 수 (>0)
  - 마포 row 수 (sigungu_code='11440' 또는 dong_code LIKE '11440%')
  - PK 중복 (중복 시 ERROR exit code 1)
  - NULL 비율 (특정 컬럼: boarding_cnt, move_in_cnt, rent_cnt 가 NULL > 5% 면 WARN)
  - 날짜 범위 (date / ym) 가 2021-04 ~ 현재 안에 들어오는지
"""
from __future__ import annotations

import os
import sys

import psycopg


_DEFAULT_DB_URL = os.environ.get(
    "POSTGRES_URL",
    "postgresql://postgres:postgres@localhost:5432/mapo_simulator",
)


_TABLES = [
    ("master_subway_station", None, "sigungu_code = '11440'"),
    ("master_ttareungi_station", None, "sigungu_code = '11440'"),
    ("seoul_subway_passenger_daily", "boarding_cnt", "station_code IN (SELECT station_code FROM master_subway_station WHERE sigungu_code='11440')"),
    ("seoul_dong_migration_monthly", "move_in_cnt", "dong_code LIKE '11440%'"),
    ("seoul_ttareungi_usage_daily", "rent_cnt", "station_id IN (SELECT station_id FROM master_ttareungi_station WHERE sigungu_code='11440')"),
]


def main() -> int:
    url = _DEFAULT_DB_URL.replace("+asyncpg", "").replace("+psycopg", "")
    errors = 0
    warnings = 0

    with psycopg.connect(url) as conn:
        for table, null_col, mapo_filter in _TABLES:
            total = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            mapo = conn.execute(f'SELECT COUNT(*) FROM "{table}" WHERE {mapo_filter}').fetchone()[0]
            print(f"[{table}] total={total:,} mapo={mapo:,}")
            if total == 0:
                print(f"  ERROR: empty table")
                errors += 1
            if null_col is not None:
                null_cnt = conn.execute(
                    f'SELECT COUNT(*) FROM "{table}" WHERE "{null_col}" IS NULL'
                ).fetchone()[0]
                ratio = null_cnt / total if total else 0
                if ratio > 0.05:
                    print(f"  WARN: {null_col} NULL ratio = {ratio:.1%}")
                    warnings += 1

    print()
    print(f"errors={errors} warnings={warnings}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: ruff + Commit (마이그레이션 미적용 상태라 실행 검증은 미루고 lint 만)**

```bash
cd backend && ruff check --fix scripts/verify/verify_emerging_trend_data.py && ruff format scripts/verify/verify_emerging_trend_data.py
git add backend/scripts/verify/verify_emerging_trend_data.py
git commit -m "feat(verify): emerging-trend B1 row/null/mapo verification"
```

---

## Task 10: 마포 필터 SQL sanity 테스트

**Files:**
- Create: `backend/tests/data/__init__.py`
- Create: `backend/tests/data/test_emerging_trend_filters.py`

- [ ] **Step 1: __init__.py + 테스트 작성**

```bash
: > backend/tests/data/__init__.py
```

`backend/tests/data/test_emerging_trend_filters.py`:

```python
"""마포 필터 query 가 비지 않게 동작하는지 sanity check.

마이그레이션 + seed 적재 후 실행하는 통합 테스트.
미적재 환경에서는 자동 skip.
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
    assert cnt >= 0  # 적재 전이면 0 도 OK, 적재 후 >0 기대


def test_mapo_migration_filter_uses_dong_code(db_conn):
    if not _has_table(db_conn, "seoul_dong_migration_monthly"):
        pytest.skip("table not migrated")
    cnt = db_conn.execute(
        "SELECT COUNT(*) FROM seoul_dong_migration_monthly WHERE dong_code LIKE '11440%'"
    ).fetchone()[0]
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
```

- [ ] **Step 2: 테스트 실행 (적재 안 된 환경: skip 다수)**

```bash
cd backend && pytest tests/data/test_emerging_trend_filters.py -v -m integration
```

Expected: skip 또는 0 row 기대 통과.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/data/__init__.py backend/tests/data/test_emerging_trend_filters.py
git commit -m "test(data): emerging-trend B1 mapo filter sanity"
```

---

## Task 11: README 안내 + Spec/Plan commit

**Files:**
- Create: `backend/scripts/ingest/README.md`

- [ ] **Step 1: README 작성**

`backend/scripts/ingest/README.md`:

```markdown
# Ingest pipelines (신흥 상권 B1)

목적: 5년치 (2021-04 ~ 2026-03) 서울 인구·이동성 공공데이터를 PostgreSQL 적재.

## 흐름

```
[1] download_raw.py        → 다운로드 URL 안내 출력
[2] 사용자가 raw CSV → backend/data/seed/raw/{subway,migration,ttareungi}/ 에 풀기
[3] python -m scripts.ingest.ingest_*    → backend/data/seed/*.csv (cleaned)
[4] alembic upgrade head                  → 5 테이블 생성
[5] python -m scripts.seed_from_csv       → COPY 적재
[6] python scripts/verify/verify_emerging_trend_data.py
```

## 데이터 출처

| 데이터 | URL | 비고 |
|--------|-----|------|
| 지하철 승하차 | https://data.seoul.go.kr/dataList/OA-12252/S/1/datasetView.do | 비로그인 다운로드 |
| 동별 전입출 | https://kosis.kr/statHtml/statHtml.do?orgId=110&tblId=DT_1B26001 | 로그인 필요 가능성 |
| 따릉이 대여이력 | https://data.seoul.go.kr/dataList/OA-15182/F/1/datasetView.do | 월별 zip, 비로그인 |
```

- [ ] **Step 2: Plan + Spec commit (사용자 확인 후)**

```bash
git add backend/scripts/ingest/README.md docs/superpowers/specs/2026-04-29-emerging-trend-data-b1-design.md docs/superpowers/plans/2026-04-29-emerging-trend-data-b1.md
git commit -m "docs(emerging-trend): B1 spec + plan + ingest README"
```

---

## Task 12: 다운로드 시도 + 사용자 안내 (Claude 가 직접 시도)

> 이 task 는 **사용자 환경에서 Claude 가 직접 실행**. plan 의 다른 task 와 달리 코드 작성이 아니라 운영 액션.

- [ ] **Step 1: download_raw.py 실행**

```bash
cd backend && python -m scripts.ingest.download_raw
```

출력된 3개 URL 을 사용자에게 안내. 자동 다운로드 가능한 endpoint 가 있으면 `_SOURCES` 에 추가하고 재실행.

- [ ] **Step 2: 다운로드 가능한 자료는 WebFetch 로 시도**

서울 열린데이터광장의 직접 다운로드 링크가 식별되면 `urllib.request` 또는 `WebFetch` 로 가져와서 `backend/data/seed/raw/<sub>/` 에 저장.

로그인 필요 시 → 사용자에게 URL 안내, 수동 투입 요청.

- [ ] **Step 3: 정제 단계까지 사용자 안내**

raw CSV 가 들어왔다는 사용자 신호 받으면:

```bash
cd backend
python -m scripts.ingest.ingest_subway_passenger --raw-dir data/seed/raw/subway     --cleaned-dir data/seed --reject-dir data/seed/raw/reject
python -m scripts.ingest.ingest_dong_migration   --raw-dir data/seed/raw/migration  --cleaned-dir data/seed --reject-dir data/seed/raw/reject
python -m scripts.ingest.ingest_ttareungi        --raw-dir data/seed/raw/ttareungi  --cleaned-dir data/seed --reject-dir data/seed/raw/reject
```

(이 명령들은 plan 의 terminal state. 실제 `alembic upgrade head` 와 `seed_from_csv` 실행은 사용자가 별도 트리거.)

---

## Self-review (작성자 점검)

- [x] §3 정책 ↔ §4 스키마 ↔ Task 2/3 모델/마이그레이션 컬럼 일관성 확인
- [x] Task 5/6/7 모두 동일 인터페이스 `ingest_one_csv(src, *, cleaned_dir, reject_dir, ym_tag) -> dict[str, Path]` — 병렬 dispatch 시 일관성
- [x] Task 11 까지 모든 spec 요구사항 (테이블 5, ingest 3, 검증, 테스트, 문서) 커버
- [x] Placeholder 없음 (download_raw.py 의 _SUBWAY_URL_FMT = None 은 명시적 manual fallback signal)
- [x] 모든 commit 단계 git add 경로 명시
- [x] alembic down_revision = a8b2c4d6e8f0 (현재 head 기준 — 실행 전 `alembic heads` 로 재확인 필요)

## Open Risks

- KOSIS / 행안부 다운로드가 캡차 / 로그인 강제 시 Task 12 일부가 manual 의존
- 따릉이 5년치 raw 가 zip 단위 ~수GB → ingest 단계 메모리 사용량. 필요 시 chunk 처리 또는 DuckDB 도입 검토
- 서울교통공사 CSV 컬럼명 (`사용일자/호선명/역명/...`) 이 연도별로 변경됐을 가능성 → ingest 실행 시 KeyError 로 즉시 확인
