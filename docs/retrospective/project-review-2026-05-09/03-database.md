# 03 - 데이터베이스 종합 리뷰 (2026-05-09)

> 범위: `backend/src/database/`, `backend/alembic/`, `backend/src/services/`, `backend/src/ingest/`, `docs/database/`
> 기준 브랜치: `dev`
> 작성 시점 DB 통계 (2026-05-04 audit 기반): **88 테이블, 1,152 컬럼, 44 FK(외래키 — 다른 테이블의 PK 를 참조하는 컬럼. 관계를 표현)**

---

## 한 줄 진단

**SQL 테이블명 f-string(파이썬 변수를 SQL 문자열에 직접 박는 위험한 패턴. 인젝션 가능) 보간 1 건 + ORM(Object-Relational Mapping. 테이블을 클래스로 다루는 패턴) 관계 정의 0 개 + COMMENT(테이블에 메타 설명을 붙이는 PostgreSQL 명령) 표준 88 개 중 8 개만 준수.**

## 비전문가용 요약

- **무엇이 문제인가요?**
  - 비밀번호를 바꾸는 코드 안에서, "어느 테이블을 고칠지" 를 SQL 문장 안에 변수로 직접 끼워 넣고 있습니다. 만약 클라이언트(앱 사용자)가 "나는 master 권한이다" 라고 거짓 주장을 했을 때 그 말을 그대로 믿고 SQL 을 만들면, 공격자가 임의의 테이블을 건드릴 수 있는 통로(인젝션 — SQL 명령을 끼워 넣어 DB 를 조작하는 공격)가 됩니다.
  - 데이터베이스에는 테이블끼리 연결된 관계(외래키)가 44 개나 있는데, 파이썬 코드(ORM)에는 그 관계가 단 한 줄도 표현되어 있지 않습니다. 모두 raw SQL(ORM 을 우회하고 SQL 문자열을 직접 실행하는 방식)로 손수 JOIN 쿼리를 작성하는 상황이라, 컬럼 이름이 바뀌면 코드가 조용히 깨집니다.
  - 팀 규칙으로 "테이블마다 담당자/용도/출처 코멘트(설명)를 달자" 라고 의무화했는데, 88 개 중 8 개만 지켜졌습니다.
- **얼마나 위험한가요?** SQL 인젝션 1 건은 단독으로는 즉시 터지지 않지만, 다른 보안 이슈와 합쳐지면 운영 데이터를 위협할 수 있습니다. 나머지는 시간이 지날수록 천천히 쌓이는 부채입니다.
- **얼마나 걸리나요?** SQL 보간 화이트리스트화(허용된 값만 통과시키는 검증)는 0.5 일. ORM 관계 정비와 COMMENT 작성은 분기 단위로 천천히 진행하면 됩니다.

## 가장 시급한 3 가지

| # | 위치 | 문제 | 수정 |
|---|------|------|------|
| H-1 | `services/auth.py:887,899` | f-string 으로 테이블명 SQL 보간 | role(권한) → 테이블명 화이트리스트 매핑 |
| H-2 | `backend/alembic/versions/a9c2d3e4f5b6` | `.py` 없고 `.pyc` 만 있는 phantom revision(.py 가 사라지고 .pyc 만 남은 비정상 revision — revision 은 마이그레이션 한 단계의 식별자) | `.pyc` 제거 + 정상 revision 재생성 |
| M-1 | `database/models.py:786-789` | `GolmokStores.open_rate/close_rate` BigInteger(매우 큰 정수) ↔ 비율(0~1 소수) 부적합 | `Float`(실수 타입)로 타입 변경 |

---

## 1. 스택 현황

현재 데이터 계층은 PostgreSQL 16(오픈소스 관계형 데이터베이스 — 표 형태로 데이터를 저장하고 SQL 로 다룸), AWS RDS(아마존 클라우드의 관리형 데이터베이스 서비스. 백업·패치를 자동으로 처리)를 기반으로, SQLAlchemy 2.0(파이썬의 ORM 라이브러리. SQL 을 파이썬 객체로 다루게 해줌)의 비동기/동기 엔진을 동시에 운용하는 이중 엔진 구조다. 마이그레이션(스키마 변경을 단계별 스크립트로 적용·롤백하는 절차)은 Alembic(SQLAlchemy 의 마이그레이션 도구. 스키마 변경을 revision 단위로 기록)으로 관리되며 38 revision, 5 no-op merge revision(아무 일도 하지 않는 병합용 단계)이 누적되어 있다. 벡터 검색(텍스트의 의미를 숫자로 환산해 가까운 의미끼리 찾는 검색 방식)은 pgvector(PostgreSQL 의 벡터 검색 확장 모듈)의 `langchain_pg_embedding` 테이블에 BAAI/bge-m3(BGE-m3 — BAAI 가 만든 다국어 임베딩 모델) 로 만든 1024 차원 임베딩(텍스트를 숫자 벡터로 변환한 결과. 1024 차원이면 1024 개의 숫자 배열)을 HNSW(Hierarchical Navigable Small World. 벡터 근사 최근접 이웃 검색 알고리즘 — 가까운 의미를 빠르게 찾는 자료구조) 인덱스로 적재해 사용하고, 시민 시뮬레이션 작업 큐와 결과 캐시는 Redis 7(메모리에 빠르게 데이터를 캐시하는 NoSQL DB)을 활용한다(TTL 1 시간 — 1 시간 지나면 자동 삭제).

| 구성 요소 | 기술 | 비고 |
|-----------|------|------|
| RDBMS | PostgreSQL 16 (AWS RDS) | max_connections ≈ 191 (동시 연결 최대 191 개) |
| ORM | SQLAlchemy 2.0 (async + sync 이중) | asyncpg / psycopg(파이썬에서 PostgreSQL 에 연결하는 두 종류의 드라이버. 각각 비동기·동기) |
| 마이그레이션 | Alembic | 38 revision, 5 no-op merge |
| 벡터 DB | pgvector (HNSW) — `langchain_pg_embedding` | BAAI/bge-m3 1024-dim |
| 캐시 | Redis 7 | 시민 job 상태 + 결과 TTL 1h |

### 엔진 구성 — 왜 이중 엔진인가

비동기 엔진(`backend/src/database/postgres.py`)은 `asyncpg` 드라이버 위에 `pool_size=10, max_overflow=15, pool_timeout=30, pool_recycle=3600` 으로 구성되어 있다. 여기서 풀(커넥션 풀 — DB 연결을 모아두고 재사용하는 구조)은 미리 10 개의 연결을 만들어두고 부족하면 15 개까지 추가로 빌려주며, 1 시간(3600 초) 마다 연결을 새로 갱신한다. `PostgresClient.get_session()` 이 성공 시 commit(변경 확정), 예외 발생 시 rollback(변경 취소) 후 재발생시키는 표준 패턴을 따른다. agents/RAG 처럼 동시성이 높은(동시에 여러 요청을 처리하는) 워크로드에서 사용한다.

동기 엔진(`backend/src/database/sync_engine.py`)은 `psycopg` 드라이버를 쓰며 `pool_size=5, max_overflow=10` 으로 작게 설정되어 있고, URL 을 키로 하는 dict 싱글턴(매번 새로 만들지 않고 한 번 만든 것을 재사용하는 패턴 — `_engines: dict[str, Engine]`)으로 매 요청마다 엔진을 재생성하지 않는다. 인증/CRUD(생성·조회·수정·삭제) 같이 짧고 단순한 트랜잭션이 주 사용처다.

pgvector 전용 동기 엔진은 `backend/src/database/vector_db.py:82` 에 별도로 정의되어 있다(`pool_size=10, max_overflow=15, pool_recycle=1800`). 별도 풀로 분리한 이유는 Windows 의 ProactorEventLoop(윈도우 비동기 이벤트 처리 방식) 와 asyncpg + pgvector 조합이 충돌하는 이슈를 우회하기 위해서이며, 호출부에서는 `asyncio.to_thread`(동기 코드를 비동기 환경에서 안전하게 호출하는 래퍼) 로 감싸 비동기 컨텍스트에 맞춘다. 이중 엔진의 의도와 한계를 명확히 인지한 설계로 강점에 해당한다.

---

## 2. 스키마(데이터베이스의 표 구조 설계도) — 테이블/컬럼

총 88 개 테이블을 용도와 범위에 따라 분류하면 다음과 같다. 인구 도메인이 4 개, 서울 전역 상권이 7 개, 마포 전용이 2 개, 마스터/코드(코드 매핑용 기준 표)가 5 개, 그리고 서비스 기능 테이블이 6 개다. 나머지는 ETL(원본 → 정제 → DB 적재 파이프라인) 중간 산출물과 legacy(예전에 만들어 아직 남아 있는) 테이블이며 `simulation_abm` 이 2026-05-09 신설되어 현재는 89 개로 늘어났다.

### 인구 관련

| 테이블명 | ORM 클래스 | 주요 내용 |
|----------|-----------|----------|
| `living_population` | `LivingPopulation` | 서울 생활인구, 복합 PK(여러 컬럼을 합쳐 PK 로 쓰는 형태. 예: date+dong_code) (date, time_zone, dong_code) |
| `sgis_population` | `SgisPopulation` | SGIS 인구 지표, 복합 PK (year, area_code, indicator) |
| `sgis_household` | `SgisHousehold` | SGIS 가구 지표 |
| `mapo_resident_pop` | `MapoResidentPop` | 마포 분기 주민등록인구 |

### 서울 전역 상권 (`seoul_`)

| 테이블명 | 비고 |
|----------|------|
| `seoul_adstrd_flpop` | 행정동 유동인구 |
| `seoul_adstrd_fclty` | 집객시설 |
| `seoul_district_sales` | 동 단위 분기 매입 — ML 사전학습용 |
| `seoul_dong_master` | 서울 431동 마스터 (ML/analytics) |
| `seoul_subway_passenger_daily` | 일별 지하철 승하차 |
| `seoul_dong_migration_monthly` | 월별 인구 이동 |
| `seoul_ttareungi_usage_daily` | 따릅이 일별 사용량 |

### 마포 전용 (`mapo_`)

| 테이블명 | 비고 |
|----------|------|
| `mapo_resident_pop` | 분기 주민등록인구 |
| `mapo_golmok_stores` | 골목상권 점포 현황 |

### 마스터/코드 (`master_`)

| 테이블명 | 내용 |
|----------|------|
| `master_dong` (= `dong_mapping`) | 마포 16동 운영 마스터 |
| `master_industry` (= `industry_master`) | 업종 코드 101행 |
| `master_subway_station` | 지하철역 마스터 |
| `master_ttareungi_station` | 따릅이 정류장 마스터 |
| `master_brand_territory` | 브랜드별 권역 설정 |

### 서비스 기능 테이블 (prefix(접두사) 없음)

| 테이블명 | 주요 내용 |
|----------|----------|
| `users` | 팀장 계정, `is_superadmin` 컬럼 (2026-05-05 추가) |
| `manager_users` | 매니저 계정, `owner_id -> users.id` FK |
| `simulation_foresee` | Predict 탭 결과 이력 |
| `simulation_abm` | ABM 결과 JSONB(JSON 을 효율적으로 저장하는 PostgreSQL 타입) 이력 (2026-05-09 신설) |
| `langchain_pg_embedding` | pgvector 임베딩 — legal RAG(법률 검색 보강 생성 — 검색한 문서를 LLM 에 함께 넣어 답변 품질을 올리는 패턴) |
| `langchain_pg_collection` | pgvector 컬렉션 메타 |

### dong_code 이중 마스터 — 가장 헷갈리는 부분

`dong_mapping` 은 마포 16 동 만 담는 운영 마스터이고, `seoul_dong_master` 는 서울 431 동 전체를 담는 ML/analytics 용 마스터다. 두 테이블 모두 `dong_code` 컬럼을 가지지만 FK(외래키) 참조 대상이 서로 달라서, 신규 ETL 을 추가할 때 어느 쪽을 참조해야 하는지 헷갈리는 사례가 반복적으로 나왔다. `models.py:326-334` 에 이 혼선을 막기 위한 경고 주석을 명시적으로 달아두었으며, 신규 테이블 추가 시에는 반드시 scope(범위 — 마포 운영 vs 서울 분석)을 먼저 판단해야 한다.

---

## 3. 마이그레이션 (Alembic)

### Phantom Revision 2 건 — 즉시 처리 필요

총 38 개 revision(마이그레이션 한 단계의 식별자. 체인으로 연결되어 순서 결정) 중 두 건이 비정상 상태다. `18bfead869d5` 는 `.py` 파일은 존재하지만 `upgrade()`(스키마를 한 단계 앞으로 적용하는 함수) 가 단순 `pass`(아무 일도 하지 않음) 인 no-op merge 로, 위험도는 낮다. 반면 `a9c2d3e4f5b6` 는 phantom revision(.py 가 사라지고 .pyc 만 남은 비정상 revision — `.pyc` 는 파이썬이 자동 생성하는 컴파일 캐시 파일이라 원본 `.py` 없이 단독으로는 신뢰할 수 없음)으로, 신규 환경에서 `alembic upgrade head`(가장 최신 스키마까지 적용 명령) 가 실패할 가능성이 높다.

| ID | 상태 | 위험도 |
|----|------|--------|
| `18bfead869d5` | `.py` 파일 존재, `upgrade()=pass` — no-op | 낮음 (merge용) |
| `a9c2d3e4f5b6` | `.py` 없고 `.pyc`만 존재 | 높음 — `alembic upgrade head` 실패 가능 |

복구 절차는 `docs/database/alembic-recovery-guide.md` 에 Phase 0~3 으로 정리되어 있고, 현재 `IM3-alembic-user-lifecycle-catchup` 브랜치에서 작업 중이지만 아직 머지(다른 브랜치의 변경을 합치는 일)되지 않았다. 이번 sprint 의 H-2 우선순위로 처리해야 한다.

### 최신 revision 체인 (상위 5 개)

```
aa13d6029c4f  add_simulation_abm           2026-05-09  (현재 HEAD — 가장 최신)
a8f3d2e7c1b9  add_users_is_superadmin      2026-05-05
91b66e68ec18  drop_simulation_history      (이전)
...
```

### 비대칭 downgrade 패턴 — 롤백(과거 상태로 되돌리기) 시 주의

`a1cb1c39627a` 는 `upgrade()` 가 `pass` 인 반면, 후속 revision `c3c01b64fb39` 가 실제 DDL(테이블/컬럼 구조를 만들거나 바꾸는 SQL) 을 수행하는 패턴이 보인다. 즉 upgrade(앞으로 적용) 체인과 downgrade(뒤로 되돌리기) 체인이 비대칭이라서, 만약 운영 중 롤백이 필요해질 경우 자동 downgrade 만으로는 원상 복구가 보장되지 않는다. 롤백 작업은 반드시 수동으로 DDL 차이를 확인한 뒤 수행해야 한다.

---

## 4. 명명 규칙 준수 현황

CLAUDE.md 가 정의한 표준은 `{scope}_{topic}_{time}` 형식이며, 접두사는 `seoul_` / `mapo_` / `master_` 또는 (서비스 기능은) 접두사 없음 중 하나여야 한다. 이 규칙은 88 개 테이블 중 상당수가 만들어지기 전에 정해진 것이라 기존 테이블에는 위반 사례가 다수 남아 있다.

### 위반 사례

| 테이블명 | 문제 |
|----------|------|
| `living_population` | 서울 전역 데이터임에도 `seoul_` prefix 없음 |
| `sgis_population`, `sgis_household` | 출처명(SGIS) prefix — 범위 prefix 규칙 미적용 |
| `golmok_*` | 마포 데이터임에도 `mapo_` 없음 |
| `dong_mapping` | `master_dong` 이어야 규칙에 맞음 |
| `industry_master` | `master_industry` 이어야 함 (역순) |
| `district_sales`, `store_info` 등 | 서울 데이터에 `seoul_` 없음 |

### 어떻게 고치나

CLAUDE.md 에 "기존 테이블 변경 금지" 원칙이 명시되어 있어 무리한 rename(이름 변경)은 피하는 것이 맞다. 대신 신규 테이블에 한해 규칙을 적용하는 점진 정비 전략이 합리적이며, 현재 `seoul_*` prefix 신규 테이블 준수율은 약 70% 수준으로 개선 추세다. legacy 테이블은 view(원본 테이블을 가공해 보여주는 가상의 테이블) 로 alias(별칭) 를 만들어 새 이름을 노출하는 것도 옵션이지만, 코드 내 raw SQL 의존도가 높은 만큼 신중히 검토해야 한다.

---

## 5. COMMENT 준수 현황

### 왜 중요한가

CLAUDE.md 는 모든 테이블에 `COMMENT ON TABLE ... IS '담당: 이름 | 용도 | 출처: 소스'` 형식의 메타데이터(데이터를 설명하는 데이터)를 의무화하고 있다. 이 규칙이 지켜지면 신규 팀원이 `psql \d+ 테이블명`(PostgreSQL 의 표 구조 조회 명령) 한 줄로 누가 책임지는지, 어떤 데이터인지, 출처가 어디인지 파악할 수 있다. 반대로 미준수 시 매번 코드와 문서를 뒤져야 한다.

### 현황

DB 레벨 COMMENT 가 적용된 테이블은 88 개 중 단 8 개(9%)에 불과하다. 다행히 최근 신설된 5 개 테이블(`master_subway_station`, `master_ttareungi_station`, `seoul_subway_passenger_daily`, `seoul_dong_migration_monthly`, `seoul_ttareungi_usage_daily`)은 alembic revision `b9c1e3f5d7a2` 에서 모두 COMMENT 를 포함했고, 2026-05-09 신설된 `simulation_abm` 도 alembic DDL 의 `comment=` 파라미터로 준수했다. 즉 신규 테이블의 준수 추세는 양호하나 기존 80 개는 비어 있는 상태다.

ORM 레벨에서도 `__table_args__`(SQLAlchemy 에서 테이블 추가 옵션을 지정하는 자리) 에 `comment` 를 둔 클래스는 `simulation_foresee` 등 3 개에 그친다. 단기 처방으로는 alembic revision 하나에 `op.execute("COMMENT ON TABLE ...")` 를 일괄 배치하는 것이 가장 빠르며, 담당자 정보는 AGENTS.md 의 디렉토리별 owner 매핑을 참고해 채우면 된다.

---

## 6. 인덱스(검색을 빠르게 해주는 보조 자료구조 — 책의 색인과 같음)

### pgvector 인덱스 — legal RAG 의 핵심

법령/계약서 RAG 의 검색 성능과 데이터 정합성(데이터가 서로 모순 없이 일관된 상태)은 `langchain_pg_embedding` 테이블의 세 가지 인덱스로 보장된다.

```sql
-- HNSW (vector_cosine_ops, m=16, ef_construction=64)
-- 의미상 비슷한 벡터를 빠르게 찾는 인덱스. cosine 은 두 벡터 사이 각도로 유사도를 잼.
CREATE INDEX idx_legal_embedding_hnsw ON langchain_pg_embedding USING hnsw (embedding vector_cosine_ops);

-- 부분 UNIQUE (chunk_id 중복 방지)
-- chunk_id 가 있는 행에 한해서만 같은 값이 두 번 들어가지 못하게 막는 인덱스
CREATE UNIQUE INDEX ... ON langchain_pg_embedding ((cmetadata->>'chunk_id'))
  WHERE cmetadata ? 'chunk_id';

-- GIN (cmetadata 필터 검색)
-- JSON 같은 복합 데이터 안의 키/값 검색을 빠르게 하는 인덱스
CREATE INDEX ... ON langchain_pg_embedding USING gin (cmetadata jsonb_path_ops);
```

HNSW 는 cosine 유사도 검색을 평균 O(log N) 수준(데이터가 늘어나도 검색 시간이 거의 늘지 않는 빠른 속도) 으로 수행하고, 부분 UNIQUE 는 chunk_id 가 있는 행에 한해 중복 적재를 방지한다(2026-05-03 검증에서 10,341 건 중복 0). GIN 인덱스는 메타데이터 필터(예: `cmetadata @> '{"law_type": "근로기준법"}'`) 를 가속한다.

### 서비스 인덱스 — 적절성 점검

| 테이블 | 인덱스 | 적절성 |
|--------|--------|--------|
| `simulation_abm` | `(manager_id, created_at)` | 매니저별 최신 정렬 — 적합 |
| `living_population` | 복합 PK (date, time_zone, dong_code) | 적합 |
| `mapo_resident_pop` | `quarter`, `dong_code` 별도 index | 적합 |

### 누락 의심 인덱스

`simulation_foresee` 테이블의 `manager_id` 컬럼에는 인덱스가 없어, `list_foresee()` 호출 시 매니저별 필터링이 풀스캔(테이블 전체를 한 줄씩 다 훑는 느린 동작)으로 떨어질 수 있다. 데이터가 누적되기 전 단순 `CREATE INDEX` 한 줄로 해결 가능한 작은 부채다. `manager_users.owner_id` 도 FK 임에도 명시적 인덱스가 없어 JOIN(여러 테이블을 연결해 합치는 SQL 연산) 시 성능 저하가 우려된다. 두 건 모두 다음 sprint 우선순위에 포함했다.

---

## 7. ORM 사용 패턴

### relationship() 0 개 — 가장 큰 구조적 부채

DB 에는 44 개의 외래키가 정의되어 있지만 78 개 ORM 클래스 중 `relationship()`(SQLAlchemy 에서 두 클래스 사이 관계를 선언해 자동으로 JOIN 해주는 함수) 을 선언한 클래스는 단 하나도 없다. 결과적으로 `manager_users` 와 `users`, `simulation_foresee` 와 `manager_users` 같은 명확한 부모-자식 관계조차 모두 raw SQL JOIN 으로 처리된다.

### 왜 중요한가

ORM 관계가 없으면 (1) JOIN 쿼리를 매번 손으로 작성해야 하고, (2) 관련 객체 cascade(부모를 삭제하면 자식도 자동 삭제되는 연쇄 동작) 같은 패턴을 코드 수준에서 보장할 수 없으며, (3) 새로 합류한 개발자가 스키마를 읽기 어렵다. 현재는 raw SQL 의존도가 사실상 100% 다.

### ORM ↔ DDL 컬럼 불일치

`rent_cost` 모델은 실제 DDL 에 존재하는 `transaction_date`, `price`, `floor_area`, `floor` 컬럼을 ORM 에 매핑(연결)하지 않았다. 이 때문에 해당 테이블을 다루는 모든 코드가 raw SQL 을 강제로 사용해야 하는 상황이 발생한다. 신규 컬럼이 추가될 때마다 동기화하는 절차가 누락된 것으로 보인다.

### __init__.py export 제한

`backend/src/database/__init__.py`(파이썬 패키지의 진입 파일 — 외부에 무엇을 노출할지 정의) 는 12 개 클래스만 외부로 export(공개) 하고 있어, 나머지 66 개 모델을 사용하려면 호출부에서 `from backend.src.database.models import ...` 로 직접 import 해야 한다. 일관성이 없다.

### ORM 타입 오류 — `GolmokStores`

`models.py:786-789` 의 `GolmokStores.open_rate` 와 `close_rate` 가 `BigInteger`(64 비트 큰 정수 타입) 로 선언되어 있다.

```python
open_rate = Column(BigInteger, comment='개업률')
close_rate = Column(BigInteger, comment='폐업률')
```

개업률/폐업률은 0.0 ~ 1.0 비율 또는 퍼센트 값이므로 `Float`(소수점 숫자 타입) 가 맞고, 현재 타입은 집계 시 정수 절단(0.7 같은 소수가 0 으로 잘려 사라지는 현상) 으로 정밀도가 손실된다. 이번 sprint 의 M-1 우선순위로 잡혀 있다.

---

## 8. 트랜잭션(여러 SQL 을 묶어 "전부 성공 또는 전부 실패" 로 처리하는 단위)과 오류 처리

### auth.py 의 SQL Injection 위험 — H-1

`backend/src/services/auth.py:887` 과 `:899` 에서 `table` 변수를 f-string(파이썬 변수를 SQL 문자열에 직접 박는 위험한 패턴. 인젝션 가능) 으로 SQL 에 직접 보간한다. `table` 은 `role` 파라미터(`'master'` 또는 `'manager'`)에 따라 `'users'` 또는 `'manager_users'` 로 결정되지만, 함수 내부에 화이트리스트(허용 목록 — 이 안에 있는 값만 통과시킴) 검증이 없다. 현재 호출 경로에서 외부 입력이 직접 `table` 에 닿지 않으므로 즉시 exploit(공격 성공) 가능성은 낮으나, 다른 보안 이슈와 결합하면 운영 데이터를 위협할 수 있다.

### 어떻게 고치나

가장 빠른 처방은 함수 진입부에 인라인 화이트리스트 검사를 추가하는 것이다.

```python
if table not in ('users', 'manager_users'):
    raise ValueError(f'허용되지 않는 테이블: {table}')
```

추가로 `role` → 테이블명 매핑을 모듈 상수 dict(딕셔너리 — 키와 값을 짝으로 저장하는 자료구조) 로 빼두면 호출부 어디서도 임의 문자열이 들어가지 못하게 막을 수 있다.

### 안전한 사례 — 비교 기준

`auth.py:834`, `auth.py:867` 의 `set_clause`(UPDATE 문에서 어떤 컬럼을 어떻게 바꿀지 적는 부분) 조합은 `updates` 키가 화이트리스트를 통과한 값만 사용하므로 안전하다. `simulation_foresee_service.py:103-124` 도 `where_sql` 조각을 코드 상수 리터럴(소스 코드에 직접 적힌 고정 문자열) 로만 구성하고, 값은 `:param` 바인딩(SQL 과 값을 분리해 안전하게 끼워 넣는 방식 — 인젝션 차단) 으로 처리하므로 안전하다. 즉 auth.py 의 두 건만 개별 처방하면 된다.

### 트랜잭션 일관성

`auth.py:836-837` 은 `engine.connect()`(연결만 열고 트랜잭션은 수동 관리) 컨텍스트 안에서 `conn.commit()` 을 수동으로 호출한다. 이 패턴은 commit 전 예외가 나면 자동 rollback 되지 않는 함정이 있어, `engine.begin()`(연결을 열면서 트랜잭션도 함께 시작 — 블록을 벗어날 때 자동 commit/rollback) 으로 바꾸면 더 안전하다. `simulation_foresee_service.py:202` 는 `engine.begin()` 의 자동 커밋 패턴을 올바르게 사용하고 있어 비교 기준이 된다.

### 빈 finally 블록

`auth.py:844`, `auth.py:877`, `auth.py:906` 에 `finally: pass`(예외 발생 여부와 무관하게 항상 실행되는 블록인데, 그 안이 비어 있는 상태) 가 세 군데 있다. 의미 없는 코드 노이즈이므로 제거하거나 실제 cleanup(정리) 로직(예: 임시 변수 정리, 로깅)으로 채워야 한다.

---

## 9. pgvector 운영

벡터 스토어(임베딩 저장소)는 `legal_documents` 컬렉션 단일로 운영되고, 임베딩 모델은 BAAI/bge-m3 1024 차원, CPU 추론(GPU 없이 일반 CPU 로 모델을 돌리는 것 — 느리지만 비용이 싸다)이다. 검색은 HNSW 위에서 cosine similarity(두 벡터 사이 각도로 비슷한 정도를 재는 방식 — 1 에 가까울수록 비슷함) 로 동작하며 2026-05-03 검증 기준 10,341 / 10,341 (중복 0) 으로 정합성이 확보되어 있다. Windows 환경에서 ProactorEventLoop 와 asyncpg + pgvector 가 충돌하는 문제를 우회하기 위해 동기 엔진을 별도로 두고 호출부에서 `asyncio.to_thread` 로 감싸는 패턴을 사용한다.

### get_total_count() 풀 우회 — 사소하지만 의도하지 않은 동작

`vector_db.py:117` 의 `get_total_count()` 는 싱글턴 동기 엔진을 쓰지 않고 `psycopg2.connect(settings.postgres_url)`(드라이버를 거쳐 새 연결을 매번 직접 여는 호출) 을 직접 호출한다. `finally: conn.close()` 가 있어 누수(연결을 닫지 않고 방치하는 사고) 위험은 낮으나, RDS 의 max_connections 카운트에 잡히지 않아 풀 모니터링이 정확하지 않다. 함수 본문을 기존 vector 엔진의 `with engine.connect() as conn` 으로 바꾸기만 하면 해결된다.

---

## 10. 데이터 수집(Ingest)

`backend/src/ingest/_common.py` 가 ETL 의 공통 기반을 제공한다. `normalize_dong_code()` 는 모든 dong_code 를 8 자리 문자열로 정규화(형식을 통일하는 것)하고, `parse_ym()` 은 YYYYMM 형식을 정수로 변환하며, `parse_int_safe()` 는 안전 파싱(잘못된 값을 만나도 죽지 않고 None 으로 처리)을 담당한다. 파싱 실패 행은 `write_reject_csv()` 가 별도 CSV(쉼표로 구분된 표 데이터 파일) 로 기록해 디버깅 가능성을 확보한다.

`backend/src/database/seed.py` 에는 4 개의 시드(테이블에 기준이 되는 초기 데이터를 채워 넣는 스크립트) 함수가 있고 모두 `ON CONFLICT DO NOTHING` 멱등 패턴(여러 번 실행해도 결과가 같은 패턴 — 이미 있으면 그냥 건너뜀) 으로 작성되어 재실행이 안전하다. `seed.py:41` 에서 `create_engine(DB_URL)` 을 직접 호출하는데(싱글턴 미사용), 이는 1 회성 스크립트 특성상 허용 범위로 본다.

---

## 11. 백업/복구

현재 `docker-compose.yml`(여러 서비스를 함께 띄우는 도커 설정 파일) 의 PostgreSQL 서비스는 RDS 마이그레이션 완료 이후 주석 처리되어 있고, `docker-compose.prod.yml` 에는 `redis_data` named volume(이름 붙은 영구 저장 공간) 만 있다. **자동 pg_dump(PostgreSQL 의 표준 백업 명령 — 데이터를 파일로 내보냄) 가 없다는 점이 핵심 리스크**다. 데이터 보호는 RDS 스냅샷(특정 시점의 DB 전체 상태를 통째로 저장한 사본 — AWS 콘솔)에 전적으로 의존하는데, 스냅샷 주기가 분 단위가 아니므로 point-in-time(원하는 시각으로 정확히 되돌리기) 복구 정밀도가 부족하다.

### 어떻게 고치나

가장 가벼운 처방은 RDS 의 automated backup(자동 백업) 정책을 명시화하고 보존 기간을 7~14 일로 설정하는 것이다. 보다 적극적인 옵션은 AWS Lambda(서버 없이 코드를 실행하는 클라우드 서비스) + EventBridge(예약된 이벤트로 다른 서비스를 깨우는 트리거) 로 일일 `pg_dump` 를 S3(아마존의 파일 저장소) 에 적재하는 것이며, ML 모델 재학습용 raw 데이터는 `data/` 디렉토리에 원본 CSV/Excel 이 보존되어 있어 이론적으로 재적재 가능하지만 실제 시간 비용이 크다.

---

## 12. 운영 — docs/database/

| 파일 | 마지막 업데이트 | 상태 |
|------|----------------|------|
| `audit-2026-05-04.md` | 2026-05-04 | 88 테이블 기준 — `simulation_abm` 미포함 |
| `alembic-recovery-guide.md` | 2026-05-04 | Phantom 2 복구 절차 수록 |
| `db-erd.md` | 2026-05-04 | 88 테이블 — 현재 89 테이블로 1 뒤처짐 |

2026-05-09 의 `simulation_abm` 신설 이후 세 문서 모두 한 테이블씩 뒤처져 있다. 테이블 수 자체는 1 차이라 사소해 보이나, ERD(Entity-Relationship Diagram — 테이블과 관계를 시각화한 그림) 가 최신을 따라가지 못하면 새 테이블의 FK 의존성을 시각적으로 파악하기 어렵다. 다음 sprint 에 `db-erd.md` 갱신을 포함했다.

---

## 13. 강점

이중 엔진 분리는 단순한 분리가 아니라 Windows ProactorEventLoop 와 같은 환경 이슈를 명확히 의식하고 만든 설계라는 점에서 견고하다. Alembic 으로 38 revision 의 모든 DDL 변경을 추적하고 있고, pgvector 의 HNSW + GIN + 부분 UNIQUE 삼중 인덱스는 검색 성능과 데이터 정합성을 동시에 잡는 정석에 가까운 구성이다. 시드는 `ON CONFLICT DO NOTHING` 으로 재실행 안전성이 확보되어 있고, `vector_db.py` 의 풀 파라미터에는 RDS max_connections 맥락이 주석으로 함께 적혀 있어 유지보수성이 높다. 최근 5 개의 신설 테이블이 COMMENT 규칙을 모두 준수했다는 점, 그리고 dong_code 이중 마스터의 혼선을 `models.py:326-334` 에 명시적으로 경고한 점도 좋은 사례다.

---

## 14. 리스크 / 기술 부채(지금은 굴러가지만 나중에 갚아야 할 코드/구조의 빚)

| 항목 | 심각도 | 설명 |
|------|--------|------|
| Phantom revision `a9c2d3e4f5b6` | HIGH | `.pyc`만 존재, `alembic upgrade head` 실패 가능 |
| `auth.py` f-string 테이블명 보간 | MEDIUM | `role` 외부 주입 시 injection 가능 경로 |
| `GolmokStores.open_rate/close_rate` BigInteger | MEDIUM | 비율 컬럼 타입 오류, 집계 시 정밀도 손실 |
| 0개 `relationship()` | MEDIUM | ORM JOIN 미활용, raw SQL 의존도 100% |
| `get_total_count()` 직접 연결 | LOW | psycopg2 직접 호출, 풀 카운트 미포함 |
| COMMENT 미준수 80개 테이블 | LOW | 유지보수 어려움 |
| 자동 pg_dump 없음 | MEDIUM | RDS 스냅샷만 — point-in-time 복구 정밀도 부족 |
| `docs/database/` drift(문서가 실제 코드/스키마와 어긋난 상태) | LOW | `simulation_abm` 추가로 모든 docs 1 뒤처짐 |
| 빈 `finally: pass` | LOW | 코드 노이즈 |
| `rent_cost` ORM 컬럼 누락 | LOW | ORM-DDL 불일치 |

---

## 15. 개선 우선순위

### 즉시 (이번 sprint)

가장 먼저 처리해야 할 것은 phantom revision `a9c2d3e4f5b6` 복구다. `.pyc` 만 남은 상태에서 신규 환경의 `alembic upgrade head` 가 실패하면 배포(코드를 운영 서버로 올려 사용자에게 노출하는 절차) 자체가 막힐 수 있어, `docs/database/alembic-recovery-guide.md` 의 Phase 0~3 을 그대로 실행해 정상화해야 한다. 두 번째는 `auth.py:887,899` 의 f-string 보간을 화이트리스트 검증으로 막는 작업으로, 함수 한두 줄만 추가하면 끝난다. 세 번째는 `GolmokStores.open_rate/close_rate` 의 타입을 `BigInteger` 에서 `Float` 으로 바꾸는 ORM 수정이다.

### 단기 (다음 sprint)

`simulation_foresee.manager_id` 인덱스를 추가해 list 조회 성능을 확보하고, `auth.py` 의 빈 `finally: pass` 세 곳을 정리하며, `docs/database/db-erd.md` 에 `simulation_abm` 을 반영한다. 셋 다 반나절 이내 작업이다.

### 중기

자동 백업을 정식 도입한다. 가벼운 옵션은 RDS automated backup 정책 명시화이고, 적극적인 옵션은 AWS Lambda + pg_dump 의 S3 일일 적재다. 다음으로 핵심 ORM 관계를 최소 2 개(`manager_users <-> users`, `simulation_foresee <-> manager_users`)부터 `relationship()` 으로 추가해 raw SQL 의존도를 점진적으로 줄인다. 마지막으로 기존 80 개 테이블에 `COMMENT ON TABLE` 을 일괄 적용하는 alembic revision 을 한 번에 발행해 준수율을 9% → 100% 로 끌어올린다.

---

*작성: 코드 리뷰 자동화 (claude-sonnet-4-6) | 기준 브랜치: `dev` | 2026-05-10*
