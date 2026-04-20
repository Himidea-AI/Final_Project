# CSV → PostgreSQL 시드 로더 설계

## 배경

팀원 각자 로컬 PostgreSQL에서 개발해야 하는데, 현재 DB 덤프를 공유하는 자동화된 방법이 없다. DBeaver로 익스포트한 CSV 파일 세트(`C:\Users\804\Desktop\dbeaber\`, 32개)를 zip으로 배포하고, 팀원이 자기 로컬 DB에 한 번에 적재할 수 있는 CLI 스크립트가 필요하다.

Docker 사용을 중단했기 때문에 현재 `backend/src/database/seed.py` (docker-compose 기동 시 자동 실행, 단일 테이블만 처리)는 이 요구를 만족하지 못한다.

## 목표 / 비목표

**목표**
- 신규 팀원이 빈 PostgreSQL DB → 완전히 채워진 개발 DB로 만드는 과정을 3단계로 단순화
- 이미 데이터가 있는 테이블은 스킵 (최초 1회 셋업 시나리오)
- FK 제약이나 테이블 로드 순서에 신경 쓰지 않아도 되게 함

**비목표**
- 증분 업데이트 / upsert 지원 (YAGNI — 시나리오 아님)
- 재시드(`--force` wipe) 지원 (YAGNI)
- 임베딩 벡터(`langchain_pg_embedding`) 복원 — 앱에서 재생성

## 아키텍처

**신규 파일**: `backend/scripts/seed_from_csv.py` (단일 모듈, ~200 LOC)

**의존성**: `psycopg` (이미 설치됨), `sqlalchemy` (URL 파싱용), 그 외 표준 라이브러리.

**팀원 온보딩 절차**:
```bash
# 1) 빈 DB 생성
createdb mapo_simulator

# 2) 스키마 마이그레이션
cd backend && alembic upgrade head

# 3) CSV 시드 (받은 zip을 backend/data/seed/ 에 풀고)
python -m scripts.seed_from_csv
```

**.gitignore 추가**: `backend/data/seed/` (CSV는 절대 repo에 들어가지 않음)

## 컴포넌트

### 1. CSV 디스커버리

- 입력 디렉토리: `--dir` 인자, 기본값 `backend/data/seed/`
- 파일명 규칙: `<table_name>_YYYYMMDDHHMM.csv` (DBeaver 기본 익스포트 포맷)
- 정규식 `^(.+?)_\d{12}\.csv$` 로 테이블명 추출

### 2. 제외 대상 (하드코딩)

```python
SKIP_TABLES = {
    "alembic_version",          # alembic이 upgrade head로 관리
    "langchain_pg_collection",  # RAG 임베딩, 앱에서 재생성
    "langchain_pg_embedding",   # pgvector 타입, 재생성
}
```

### 3. 로드 엔진

`psycopg` 동기 드라이버 사용 (스크립트는 async 불필요). 하나의 커넥션, 하나의 트랜잭션.

```python
with conn.transaction():
    conn.execute("SET session_replication_role = replica")  # FK/trigger 비활성화
    for table, csv_path in csv_map.items():
        if should_skip(conn, table):
            continue
        copy_csv(conn, table, csv_path)
    conn.execute("SET session_replication_role = DEFAULT")
```

**COPY 구문**:
```python
with open(csv_path, "rb") as f, \
     conn.cursor().copy(f"COPY {table} FROM STDIN WITH (FORMAT CSV, HEADER)") as cp:
    while chunk := f.read(8192):
        cp.write(chunk)
```

### 4. 스킵 로직

테이블별로 `SELECT COUNT(*)` 실행 → 1 이상이면 `[skip]` 로그 + 다음 테이블.

### 5. 로깅

stdout에 한국어 프리픽스 로그:
- `[seed]` — 시작/종료 메타 정보
- `[load]` — 실제 적재 (건수 포함)
- `[skip]` — 이미 데이터 있음
- `[warn]` — CSV 누락, 테이블 누락
- `[error]` — 연결 실패, COPY 실패

## 데이터 흐름

```
사용자 실행 → env에서 POSTGRES_URL 읽기 → psycopg 연결
  → CSV 디렉토리 스캔 → 파일명 → 테이블명 매핑
  → BEGIN
  → session_replication_role = replica
  → for each (table, csv):
       skip if table in SKIP_TABLES
       skip if CSV 없음 (warn)
       skip if 테이블 없음 (warn)
       skip if COUNT(*) > 0
       COPY FROM STDIN
  → session_replication_role = DEFAULT
  → COMMIT
  → 요약 출력
```

## 에러 처리

| 상황 | 동작 |
|------|------|
| `POSTGRES_URL` 미설정 또는 연결 실패 | `[error]` + `exit 1` |
| CSV 디렉토리 없음 또는 비어있음 | `[error]` + `exit 1` |
| 테이블 없음 (alembic 미실행) | `[error]` + 힌트 메시지 + `exit 1` |
| 특정 CSV 누락 (DB에 테이블은 있음) | `[warn]` + 다음 테이블로 계속 |
| 특정 CSV는 있는데 DB에 테이블 없음 | `[warn]` + 해당 파일 스킵 |
| COPY 실패 (컬럼 불일치 등) | 트랜잭션 전체 롤백 + `[error]` 상세 + `exit 1` |
| 이미 데이터 있음 | `[skip]` + 계속 |

## CLI

```
python -m scripts.seed_from_csv [--dir PATH] [--dry-run]
```

- `--dir PATH`: CSV 디렉토리 경로 (기본 `backend/data/seed/`)
- `--dry-run`: 로드 없이 어떤 테이블이 로드될지만 출력

## 설정

- `POSTGRES_URL` 환경변수 (기존 패턴 재사용, 기본값 `postgresql://postgres:postgres@localhost:5432/mapo_simulator`)
- 기존 `backend/src/database/seed.py` 는 그대로 두되 deprecated 주석 추가 (Docker 경로에서만 호출되니 당장 제거는 안 함)

## 테스트

- **수동 smoke test**: 로컬에서 빈 DB 생성 → `alembic upgrade head` → 바탕화면 `dbeaber/` 디렉토리를 `--dir`로 지정해 실행 → 각 테이블 row 수 확인
- 실패 케이스: 테이블 없는 상태에서 실행 → 올바른 에러 메시지 확인
- 재실행 케이스: 한 번 성공 후 다시 실행 → 모든 테이블 스킵되는지 확인
