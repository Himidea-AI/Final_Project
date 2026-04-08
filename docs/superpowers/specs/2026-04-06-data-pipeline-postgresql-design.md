# Data Pipeline + PostgreSQL Design

## Overview

CSV 41개 파일을 데이터 소스별로 통합하여 PostgreSQL 11개 테이블로 적재하는 데이터 파이프라인 설계.

## Architecture

```
data/processed/*.csv (41 files)
       |
  [ETL Pipeline] -- data/pipeline/load_to_db.py
       |
  PostgreSQL 16 (mapo_simulator) -- 11 tables
       |
  [Agent Nodes] -- SQLAlchemy 2.0 async ORM
       |
  simulation_result table
```

## Tech Stack

| Component | Choice | Reason |
|-----------|--------|--------|
| ORM | SQLAlchemy 2.0 (async) | Already in requirements.txt |
| Migration | Alembic | SQLAlchemy standard |
| DB Driver | asyncpg (agent) + psycopg2 (ETL) | Async for agents, sync for bulk load |
| ETL | pandas + SQLAlchemy bulk insert | CSV already processed with pandas |

## Tables (11)

### 1. living_population (968K rows)

Source: `living_population_dong_mapo.csv`

| Column | Type | Description |
|--------|------|-------------|
| date | DATE | PK. 기준일 |
| time_zone | SMALLINT | PK. 시간대 (0~23) |
| dong_code | VARCHAR(10) | PK. 행정동코드 |
| dong_name | VARCHAR(20) | 행정동명 |
| total_pop | FLOAT | 총 생활인구 |
| male_0_9 ~ male_70_plus | FLOAT x15 | 남성 연령대별 |
| female_0_9 ~ female_70_plus | FLOAT x15 | 여성 연령대별 |

Index: `(dong_code, date)` for time-series queries.

### 2. sgis_population (~190K rows)

Source: `sgis_population_*.csv` 5개 + `district_resident_pop` + `district_avg_age` + `district_demographics`

| Column | Type | Description |
|--------|------|-------------|
| year | SMALLINT | PK. 연도 |
| area_code | VARCHAR(14) | PK. 소지역/집계구 코드 |
| indicator | VARCHAR(20) | PK. 지표 (total, avg_age, density, aging, age_gender_*) |
| value | FLOAT | 값 |

### 3. sgis_household (~23K rows)

Source: `sgis_household_*.csv` 2개 + `district_households`

Same structure as sgis_population.

### 4. sgis_business (~55K rows)

Source: `sgis_business_*.csv` 4개

Same structure as sgis_population.

### 5. golmok_commercial (~178K rows)

Source: `golmok_sales/stores/floating_pop/worker_pop/index_mapo.csv` + `commercial_change_mapo.csv`

| Column | Type | Description |
|--------|------|-------------|
| quarter | INTEGER | PK. 분기 (20191 format) |
| trdar_code | VARCHAR(10) | PK. 상권코드 |
| data_type | VARCHAR(20) | PK. sales/stores/floating_pop/worker_pop/index/change |
| industry_code | VARCHAR(20) | PK. 업종코드 (없으면 'ALL') |
| metrics | JSONB | 데이터 (data_type별 구조 상이) |

Index: `(data_type, quarter)` for type-filtered queries.

### 6. district_sales (17K rows)

Source: `district_sales.csv` (district_trend_timeseries 흡수)

| Column | Type | Description |
|--------|------|-------------|
| quarter | INTEGER | PK. 분기 |
| dong_code | VARCHAR(10) | PK. 행정동코드 |
| industry_code | VARCHAR(20) | PK. 업종코드 |
| dong_name | VARCHAR(20) | |
| industry_name | VARCHAR(50) | |
| monthly_sales | BIGINT | 당월 매출 금액 |
| monthly_count | INTEGER | 당월 매출 건수 |
| weekday_sales | BIGINT | 주중 매출 |
| weekend_sales | BIGINT | 주말 매출 |
| mon~sun_sales | BIGINT x7 | 요일별 매출 |
| time_00_06 ~ time_21_24_sales | BIGINT x6 | 시간대별 매출 |
| male_sales / female_sales | BIGINT | 성별 매출 |
| age_10 ~ age_60_above_sales | BIGINT x6 | 연령대별 매출 |
| (same for _count variants) | INTEGER | 건수 |

Index: `(dong_code, quarter)` for dong-based queries.

### 7. store_info (30K rows)

Source: `store_info_mapo.csv`

| Column | Type | Description |
|--------|------|-------------|
| store_id | VARCHAR(20) | PK. 상가업소번호 |
| dong_name | VARCHAR(20) | 행정동명 |
| address | TEXT | 도로명주소 |
| lat | FLOAT | 위도 |
| lon | FLOAT | 경도 |
| industry_l | VARCHAR(50) | 대분류 |
| industry_m | VARCHAR(50) | 중분류 |
| industry_s | VARCHAR(50) | 소분류 |
| floor_info | VARCHAR(20) | 층정보 |
| store_name | VARCHAR(100) | 상호명 |

Index: `(dong_name)`, `(industry_m)` for filtering.

### 8. store_quarterly (33K rows)

Source: `district_stores.csv` + `district_store_timeseries.csv`

| Column | Type | Description |
|--------|------|-------------|
| quarter | INTEGER | PK. 분기 |
| dong_code | VARCHAR(10) | PK. 행정동코드 |
| industry_code | VARCHAR(20) | PK. 업종코드 |
| dong_name | VARCHAR(20) | |
| industry_name | VARCHAR(50) | |
| store_count | INTEGER | 점포수 |
| open_count | INTEGER | 개업수 |
| close_count | INTEGER | 폐업수 |
| closure_rate | FLOAT | 폐업률 |
| franchise_count | INTEGER | 프랜차이즈수 |

### 9. rent_cost (~5K rows)

Source: `rent_building_mapo.csv` + `rent_small_store_mapo.csv` + `commercial_trade_mapo.csv`

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | PK |
| data_type | VARCHAR(20) | building_rent / trade |
| area_name | VARCHAR(30) | 지역명/주소 |
| year | SMALLINT | 연도 |
| quarter | SMALLINT | 분기 (임대료) |
| rent | FLOAT | 임대료 (천원/m2) |
| vacancy_rate | FLOAT | 공실률 |
| investment_return | FLOAT | 투자수익률 |
| income_return | FLOAT | 소득수익률 |
| capital_return | FLOAT | 자본수익률 |
| transaction_date | VARCHAR(10) | 거래일 (실거래) |
| price | BIGINT | 거래금액 만원 (실거래) |
| floor_area | FLOAT | 전용면적 m2 (실거래) |
| floor | VARCHAR(10) | 층 (실거래) |
| source | VARCHAR(20) | 데이터 출처 |

### 10. dong_mapping (16 rows)

Source: `trdar_dong_mapping.csv` + `district_population.csv` + `district_commercial_summary.csv`

| Column | Type | Description |
|--------|------|-------------|
| dong_code | VARCHAR(10) | PK. 행정동코드 |
| dong_name | VARCHAR(20) | 행정동명 |
| resident_pop | INTEGER | 주민등록인구 |
| floating_pop | FLOAT | 평균 생활인구 |
| avg_age | FLOAT | 평균나이 |
| total_households | INTEGER | 총 가구수 |
| trdar_codes | JSONB | 해당 동의 상권코드 목록 |

### 11. simulation_result (variable)

New table for storing simulation inputs and outputs.

| Column | Type | Description |
|--------|------|-------------|
| request_id | UUID | PK |
| created_at | TIMESTAMP | 생성 시각 |
| input_params | JSONB | SimulationInput |
| output_result | JSONB | SimulationOutput |
| status | VARCHAR(20) | pending/running/completed/failed |

## CSV-to-Table Mapping

| Table | Source CSVs | Merge Strategy |
|-------|-----------|----------------|
| living_population | living_population_dong_mapo.csv | Direct load (drop living_population_mapo.csv) |
| sgis_population | sgis_population_*.csv (5) + district_resident_pop + district_avg_age + district_demographics | Concat with indicator column |
| sgis_household | sgis_household_*.csv (2) + district_households | Concat with indicator column |
| sgis_business | sgis_business_*.csv (4) | Concat with indicator column |
| golmok_commercial | golmok_*_mapo.csv (5) + commercial_change_mapo | Union with data_type + JSONB |
| district_sales | district_sales.csv | Direct (trend_timeseries is subset) |
| store_info | store_info_mapo.csv | Direct load, select columns |
| store_quarterly | district_stores.csv + district_store_timeseries.csv | Merge on (quarter, dong, industry) |
| rent_cost | rent_building_mapo + rent_small_store_mapo + commercial_trade_mapo | Union with data_type |
| dong_mapping | trdar_dong_mapping + district_population + district_commercial_summary | Aggregate to 16-row master |
| simulation_result | (new) | Empty at creation |

**Excluded**: golmok_*_seoul.csv (6 files), living_population_mapo.csv (replaced by dong-level)

## File Structure

```
backend/src/database/
  models.py           -- SQLAlchemy ORM models (11 tables)
  postgres.py         -- Async DB client (replace existing stub)
  alembic.ini
  alembic/
    env.py
    versions/
      001_initial_schema.py

data/pipeline/
  load_to_db.py       -- CSV -> PostgreSQL ETL script
```

## Pipeline Commands

```bash
# 1. Create/migrate tables
cd backend && alembic upgrade head

# 2. Load CSV data
cd data && python pipeline/load_to_db.py

# 3. Verify
cd backend && python -c "from src.database.postgres import PostgresClient; ..."
```
