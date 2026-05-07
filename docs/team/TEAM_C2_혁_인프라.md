### C2 — 인프라 (혁)

**담당 영역**: Docker 컨테이너화, 기본 인프라 설정

#### Docker Compose 설정

**docker-compose.yml 구성**:
```yaml
version: '3.8'
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
  
  frontend:
    build: ./frontend
    ports: ["80:80"]
  
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

**컨테이너 3개**:
- Backend (Uvicorn)
- Frontend (Nginx)
- Redis 7

#### AWS RDS 연결 (찬영 마이그레이션)

- 로컬 postgres 컨테이너 제거
- `POSTGRES_URL` 환경변수로 외부 RDS endpoint 연결
- 네트워크 보안 그룹 설정

#### pgvector HNSW Index (찬영 마이그레이션)

- Alembic 마이그레이션 파일 작성
- `CREATE INDEX ... USING hnsw` SQL 실행

---

## Database Schema

**규모**: 78 ORM models / ~1,019 columns / 32 explicit FK (`backend/src/database/models.py`)

### Naming Convention

| Prefix | 용도 | 예시 |
|--------|------|------|
| `master_` | 코드/마스터 (정적 reference) | `master_subway_station`, `master_ttareungi_station`, `master_dong`, `master_industry` |
| `seoul_` | 서울 전역 시계열 데이터 | `seoul_district_sales`, `seoul_subway_passenger_daily`, `seoul_dong_migration_monthly`, `seoul_adstrd_flpop` |
| `mapo_` | 마포구 전용 | `mapo_resident_pop`, `mapo_sns_sentiment` |
| (없음) | 서비스 기능 | `users`, `manager_users`, `simulation_foresee`, `simulation_ai`, `customer`, `invite_codes` |

### 카테고리별 주요 테이블

| 카테고리 | 테이블 |
|---------|--------|
| Population | living_population, sgis_population, sgis_household, mapo_resident_pop, seoul_population_quarterly |
| Sales | district_sales, golmok_commercial, golmok_sales, golmok_stores, seoul_district_sales, seoul_district_stores, cpi_dining_quarterly |
| Rent | rent_cost, golmok_rent, seoul_golmok_rent, jeonse_dong_master, rent_cost_summary_2025, jeonse_monthly_rent, small_store_rent_q |
| Location Master | dong_mapping, seoul_dong_master, dong_centroid, master_subway_station, master_ttareungi_station |
| Business | industry_master, store_info, store_quarterly, kakao_store, kakao_store_hours, kakao_store_menu, seoul_adstrd_(change_ix/fclty/flpop/stor) |
| Franchise / Brand | ftc_brand_franchise (16K), biz_brand_mapping, mart_brand_territory, naver_vacancy, vacancy_enriched |
| Auth | users, manager_users, invite_codes, customer |
| Simulation | simulation_foresee, simulation_ai (분리 저장) |
| Trends | naver_trend_industry, naver_trend_monthly, naver_trend_quarterly, mapo_sns_sentiment, seoul_trdar_(change_ix/flpop/stor) |
| Legal | law_legislations, law_precedents |
| Economic | ecos_key_statistics, ecos_timeseries, kosis_regional_income, molit_nrg_trade |
| Transport | bus_boarding_daily, seoul_subway_passenger_daily, seoul_ttareungi_usage_daily, seoul_dong_migration_monthly |
| 기타 | apt_trade_real, elderly_ratio_region, dong_subway_access, holiday_calendar, weather_daily, seoul_realtime_hotspots |

---

## 실행 방법

### Docker Compose (권장)

```bash
# 환경 설정
cp .env.example .env
# .env 필수: POSTGRES_URL = AWS RDS endpoint (로컬 postgres 컨테이너 제거됨)
#          + API 키 (ANTHROPIC, OPENAI, GOOGLE, FTC, KAKAO, ECOS, NTS, ...)

# 전체 서비스 실행
docker compose up --build
```

- Frontend: http://localhost (Nginx)
- Backend API: http://localhost:8000
- Redis: localhost:6379
- PostgreSQL + pgvector: AWS RDS (외부) — `POSTGRES_URL` 환경 변수로 주입

> **참고**: 2026-04~05 기점으로 Postgres 컨테이너 제거 및 RDS 마이그레이션 완료. 로컬 개발은 `POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/mapo_simulator` fallback (settings.py default).

### 개발 모드 (로컬)

```bash
# 백엔드
cd backend
pip install -r requirements.txt
uvicorn src.main:app --reload  # 단일 worker (멀티 worker 시 _pending_pipelines/_async_job_tasks 분리됨)

# 프론트엔드
cd frontend
npm install
npm run dev
```

### 코드 품질 (commit 전 필수)

```bash
# 백엔드
cd backend && ruff check --fix && ruff format

# 프론트엔드
cd frontend && npx prettier --write .
```

### Alembic 마이그레이션

```bash
cd backend
alembic current                          # 현재 head
alembic upgrade head                     # 최신 적용
alembic revision -m "변경 내용"          # 새 revision (수동 작성)
```

---

## 주요 환경 변수

| 카테고리 | 변수 |
|---------|------|
| LLM | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY` |
| DB | `POSTGRES_URL`, `POSTGRES_PASSWORD`, `REDIS_URL` |
| RAG 벡터 | `EMBEDDING_MODE` (openai), pgvector 는 `POSTGRES_URL` 재사용 |
| 외부 API | `FTC_API_KEY`, `KAKAO_API_KEY`, `ECOS_API_KEY`, `NTS_API_KEY`, `SEOUL_OPENDATA_KEY`, `SGIS_API_KEY`, `SGIS_SECRET_KEY`, `MOLIT_API_KEY`, `SEMAS_API_KEY`, `LAW_OC` |
| 트렌드 | `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` |
| 관측성 | `LANGCHAIN_API_KEY`, `LANGCHAIN_TRACING_V2`, `LANGCHAIN_PROJECT` |
| 인증 | `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES` |
| RAG 튜닝 | `RRF_VECTOR_WEIGHT=0.4`, `RRF_BM25_WEIGHT=0.6`, `PRIMARY_LAW_BOOST=2.0`, `BM25_SUPPLEMENTARY_PENALTY=0.4` |
| 재정렬 | `RERANK_ENABLED=true`, `RERANK_PROVIDER=openai`, `RERANK_OPENAI_MODEL=gpt-4.1-mini` |
| Rate limit | `RATE_LIMIT_MAX=10` (시간당) |
| App 모드 | `APP_MODE=PROD`, `DEBUG=false`, `DEMO_MODE=false`, `LLM_AGENTS_DISABLED=0` |
