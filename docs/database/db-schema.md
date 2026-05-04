# PostgreSQL 테이블·컬럼 정의서 (DB 실측)

> DB: `mapo_simulator` | **87개 테이블**
> 출처: `information_schema` 직접 dump (자동 생성)
> 갱신: `python backend/scripts/diagnostics/gen_db_schema_doc.py`

---

## ORM ↔ DB 정합

- DB 실제 테이블: **87**
- ORM 모델: **78**
- 공통: **77**
- ORM zombie (DB 없음): simulation_history
- DB only (ORM 없음): alembic_version, langchain_pg_collection, langchain_pg_embedding, living_population_grid, mapo_schools, password_reset_tokens, seoul_district_sales_imputed_v4, seoul_district_sales_imputed_v4_detail, seoul_resident_pop_quarterly, user_usage

---

## 도메인별 테이블 목록

### Vector DB (2)

| 테이블 | row 수 | ORM | PK |
|---|---|---|---|
| `langchain_pg_collection` | 1 | — | uuid |
| `langchain_pg_embedding` | 10,255 | — | id |

### 공공 통계 (4)

| 테이블 | row 수 | ORM | PK |
|---|---|---|---|
| `ecos_key_statistics` | 101 | ✓ | keystat_name, cycle |
| `ecos_timeseries` | 2,783 | ✓ | stat_code, item_code1, item_code2, period |
| `kosis_regional_income` | 1,116 | ✓ | id |
| `molit_nrg_trade` | 8,731 | ✓ | id |

### 네이버 외부수집 (4)

| 테이블 | row 수 | ORM | PK |
|---|---|---|---|
| `naver_trend_industry` | 319 | ✓ | id |
| `naver_trend_monthly` | 33,985 | ✓ | id |
| `naver_trend_quarterly` | 9,205 | ✓ | id |
| `naver_vacancy` | 1,341 | ✓ | id |

### 마스터 (7)

| 테이블 | row 수 | ORM | PK |
|---|---|---|---|
| `dong_centroid` | 16 | ✓ | dong_code |
| `dong_mapping` | 16 | ✓ | dong_code |
| `holiday_calendar` | 3,287 | ✓ | date |
| `industry_master` | 101 | ✓ | industry_code |
| `jeonse_dong_master` | 399 | ✓ | dong_code |
| `master_subway_station` | 292 | ✓ | station_code |
| `master_ttareungi_station` | 5,541 | ✓ | station_id |

### 마포 전용 (3)

| 테이블 | row 수 | ORM | PK |
|---|---|---|---|
| `mapo_resident_pop` | 408 | ✓ | — |
| `mapo_schools` | 0 | — | id |
| `mapo_sns_sentiment` | 377 | ✓ | id |

### 메타 (1)

| 테이블 | row 수 | ORM | PK |
|---|---|---|---|
| `alembic_version` | 1 | — | version_num |

### 법률 RAG (2)

| 테이블 | row 수 | ORM | PK |
|---|---|---|---|
| `law_legislations` | 57 | ✓ | item_id |
| `law_precedents` | 222 | ✓ | item_id |

### 서울 상권 (3)

| 테이블 | row 수 | ORM | PK |
|---|---|---|---|
| `seoul_trdar_change_ix` | 1,932 | ✓ | quarter, trdar_code |
| `seoul_trdar_fclty` | 1,365 | ✓ | quarter, trdar_code |
| `seoul_trdar_flpop` | 1,932 | ✓ | quarter, trdar_code |

### 서울 시군구 (5)

| 테이블 | row 수 | ORM | PK |
|---|---|---|---|
| `seoul_signgu_change_ix` | 700 | ✓ | quarter, signgu_code |
| `seoul_signgu_fclty` | 525 | ✓ | quarter, signgu_code |
| `seoul_signgu_flpop` | 700 | ✓ | quarter, signgu_code |
| `seoul_signgu_selng` | 43,043 | ✓ | quarter, signgu_code, industry_code |
| `seoul_signgu_stor` | 69,704 | ✓ | quarter, signgu_code, industry_code |

### 서울 전역 (13)

| 테이블 | row 수 | ORM | PK |
|---|---|---|---|
| `seoul_district_sales` | 87,938 | ✓ | quarter, dong_code, industry_code |
| `seoul_district_sales_imputed_v4` | 137 | — | quarter, dong_code, industry_code |
| `seoul_district_sales_imputed_v4_detail` | 6,439 | — | quarter, dong_code, industry_code, column_name |
| `seoul_district_stores` | 100,587 | ✓ | quarter, dong_code, industry_code |
| `seoul_dong_master` | 431 | ✓ | dong_code |
| `seoul_dong_migration_monthly` | 1,360 | ✓ | ym, dong_code |
| `seoul_golmok_rent` | 11,900 | ✓ | year, quarter, dong_code |
| `seoul_population_quarterly` | 10,176 | ✓ | quarter, dong_code |
| `seoul_realtime_hotspots` | 1,876 | ✓ | id |
| `seoul_resident_pop_quarterly` | 13,508 | — | quarter, dong_code |
| `seoul_subway_passenger_daily` | 199,340 | ✓ | date, station_code |
| `seoul_training_dataset` | 87,938 | ✓ | quarter, dong_code, industry_code |
| `seoul_ttareungi_usage_daily` | 985,653 | ✓ | date, station_id |

### 서울 행정동 (4)

| 테이블 | row 수 | ORM | PK |
|---|---|---|---|
| `seoul_adstrd_change_ix` | 11,900 | ✓ | quarter, dong_code |
| `seoul_adstrd_fclty` | 336 | ✓ | quarter, dong_code |
| `seoul_adstrd_flpop` | 11,900 | ✓ | quarter, dong_code |
| `seoul_adstrd_stor` | 849,552 | ✓ | quarter, dong_code, industry_code |

### 시뮬 결과/고객 (3)

| 테이블 | row 수 | ORM | PK |
|---|---|---|---|
| `customers` | 0 | ✓ | customer_id |
| `simulation_ai` | 3 | ✓ | id |
| `simulation_foresee` | 4 | ✓ | id |

### 카카오 외부수집 (3)

| 테이블 | row 수 | ORM | PK |
|---|---|---|---|
| `kakao_store` | 4,413 | ✓ | kakao_id |
| `kakao_store_hours` | 3,995 | ✓ | kakao_id |
| `kakao_store_menu` | 81,037 | ✓ | id |

### 통계청 SGIS (3)

| 테이블 | row 수 | ORM | PK |
|---|---|---|---|
| `sgis_business` | 137,356 | ✓ | year, area_code, indicator |
| `sgis_household` | 25,550 | ✓ | year, area_code, indicator |
| `sgis_population` | 224,517 | ✓ | year, area_code, indicator |

### 프로덕션 데이터 (24)

| 테이블 | row 수 | ORM | PK |
|---|---|---|---|
| `apt_trade_real` | 8,578 | ✓ | id |
| `bus_boarding_daily` | 3,710,508 | ✓ | id |
| `cpi_dining_quarterly` | 24 | ✓ | quarter |
| `district_sales` | 3,703 | ✓ | quarter, dong_code, industry_code |
| `district_sales_seoul` | 475,334 | ✓ | id |
| `dong_subway_access` | 424 | ✓ | dong_name |
| `elderly_ratio_region` | 1,566 | ✓ | id |
| `ftc_brand_franchise` | 34,708 | ✓ | id |
| `golmok_commercial` | 178,840 | ✓ | id |
| `golmok_rent` | 472 | ✓ | id |
| `golmok_sales` | 9,599 | ✓ | quarter, trdar_code, industry_code |
| `golmok_stores` | 15,800 | ✓ | quarter, trdar_code, industry_code |
| `jeonse_monthly_rent` | 168,342 | ✓ | id |
| `living_population` | 961,071 | ✓ | date, time_zone, dong_code |
| `living_population_grid` | 10,538,127 | — | cell_id, ymd, tt |
| `mart_brand_territory` | 11,849 | ✓ | id |
| `rent_cost` | 248 | ✓ | id |
| `rent_cost_summary_2025` | 148 | ✓ | id |
| `resident_pop_monthly` | 1,479 | ✓ | region_full, ym |
| `small_store_rent_q` | 10,020 | ✓ | id |
| `store_info` | 30,488 | ✓ | store_id |
| `store_quarterly` | 3,840 | ✓ | quarter, dong_code, industry_code |
| `vacancy_enriched` | 111 | ✓ | id |
| `weather_daily` | 2,665 | ✓ | date, stn |

### 회원/인증 (6)

| 테이블 | row 수 | ORM | PK |
|---|---|---|---|
| `biz_brand_mapping` | 5,867 | ✓ | biz_number |
| `invite_codes` | 16 | ✓ | id |
| `manager_users` | 12 | ✓ | id |
| `password_reset_tokens` | 0 | — | id |
| `user_usage` | 0 | — | id |
| `users` | 20 | ✓ | id |

---

## 테이블별 상세

### `alembic_version` — 1 rows

- 도메인: 메타
- ORM 정의: ✗
- PK: `version_num`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `version_num` | character varying(32) | — | — |

### `apt_trade_real` — 8,578 rows

- 도메인: 프로덕션 데이터
- ORM 정의: ✓
- PK: `id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | bigint | — | nextval('apt_trade_real_id_seq… |
| `sigungu` | text | ✓ | — |
| `jibun_addr` | text | ✓ | — |
| `bon_beon` | text | ✓ | — |
| `bu_beon` | text | ✓ | — |
| `apt_name` | text | ✓ | — |
| `area_sqm` | double precision | ✓ | — |
| `deal_ym` | integer | ✓ | — |
| `deal_day` | integer | ✓ | — |
| `price_won` | bigint | ✓ | — |
| `cancel_date` | text | ✓ | — |
| `floor` | integer | ✓ | — |
| `seller` | text | ✓ | — |
| `buyer` | text | ✓ | — |
| `build_year` | integer | ✓ | — |
| `road_addr` | text | ✓ | — |
| `realty_type` | text | ✓ | — |
| `deal_type` | text | ✓ | — |
| `region_full` | text | ✓ | — |
| `cancel_reason` | text | ✓ | — |
| `property_type` | text | ✓ | — |

### `biz_brand_mapping` — 5,867 rows

- 도메인: 회원/인증
- ORM 정의: ✓
- PK: `biz_number`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `biz_number` | character varying(12) | — | — |
| `company_name` | character varying(100) | — | — |
| `brand_name` | character varying(100) | ✓ | — |
| `industry_large` | character varying(50) | ✓ | — |
| `industry_medium` | character varying(50) | ✓ | — |
| `franchise_count` | integer | ✓ | — |
| `avg_sales` | bigint | ✓ | — |
| `mapo_store_count` | integer | ✓ | — |
| `created_at` | timestamp with time zone | ✓ | now() |

### `bus_boarding_daily` — 3,710,508 rows

- 도메인: 프로덕션 데이터
- ORM 정의: ✓
- PK: `id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | bigint | — | nextval('bus_boarding_daily_id… |
| `use_date` | date | — | — |
| `route_no` | character varying(20) | ✓ | — |
| `route_name` | text | ✓ | — |
| `ars_id` | character varying(15) | ✓ | — |
| `station_name` | text | ✓ | — |
| `boarding_count` | integer | ✓ | — |
| `alighting_count` | integer | ✓ | — |

### `cpi_dining_quarterly` — 24 rows

- 도메인: 프로덕션 데이터
- ORM 정의: ✓
- PK: `quarter`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `quarter` | bigint | — | — |
| `cpi_index` | double precision | ✓ | — |

### `customers` — 0 rows

- 도메인: 시뮬 결과/고객
- ORM 정의: ✓
- PK: `customer_id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `customer_id` | character varying(20) | — | — |
| `customer_name` | text | — | — |
| `visit_date` | date | ✓ | — |

### `district_sales` — 3,703 rows

- 도메인: 프로덕션 데이터
- ORM 정의: ✓
- PK: `quarter, dong_code, industry_code`
- FK:
  - `industry_code` → `industry_master.industry_code`
  - `dong_code` → `dong_mapping.dong_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `quarter` | integer | — | — |
| `dong_code` | character varying(10) | — | — |
| `industry_code` | character varying(20) | — | — |
| `dong_name` | character varying(20) | ✓ | — |
| `industry_name` | character varying(50) | ✓ | — |
| `monthly_sales` | bigint | ✓ | — |
| `monthly_count` | integer | ✓ | — |
| `weekday_sales` | bigint | ✓ | — |
| `weekend_sales` | bigint | ✓ | — |
| `mon_sales` | bigint | ✓ | — |
| `tue_sales` | bigint | ✓ | — |
| `wed_sales` | bigint | ✓ | — |
| `thu_sales` | bigint | ✓ | — |
| `fri_sales` | bigint | ✓ | — |
| `sat_sales` | bigint | ✓ | — |
| `sun_sales` | bigint | ✓ | — |
| `time_00_06_sales` | bigint | ✓ | — |
| `time_06_11_sales` | bigint | ✓ | — |
| `time_11_14_sales` | bigint | ✓ | — |
| `time_14_17_sales` | bigint | ✓ | — |
| `time_17_21_sales` | bigint | ✓ | — |
| `time_21_24_sales` | bigint | ✓ | — |
| `male_sales` | bigint | ✓ | — |
| `female_sales` | bigint | ✓ | — |
| `age_10_sales` | bigint | ✓ | — |
| `age_20_sales` | bigint | ✓ | — |
| `age_30_sales` | bigint | ✓ | — |
| `age_40_sales` | bigint | ✓ | — |
| `age_50_sales` | bigint | ✓ | — |
| `age_60_above_sales` | bigint | ✓ | — |
| `weekday_count` | integer | ✓ | — |
| `weekend_count` | integer | ✓ | — |
| `mon_count` | integer | ✓ | — |
| `tue_count` | integer | ✓ | — |
| `wed_count` | integer | ✓ | — |
| `thu_count` | integer | ✓ | — |
| `fri_count` | integer | ✓ | — |
| `sat_count` | integer | ✓ | — |
| `sun_count` | integer | ✓ | — |
| `time_00_06_count` | integer | ✓ | — |
| `time_06_11_count` | integer | ✓ | — |
| `time_11_14_count` | integer | ✓ | — |
| `time_14_17_count` | integer | ✓ | — |
| `time_17_21_count` | integer | ✓ | — |
| `time_21_24_count` | integer | ✓ | — |
| `male_count` | integer | ✓ | — |
| `female_count` | integer | ✓ | — |
| `age_10_count` | integer | ✓ | — |
| `age_20_count` | integer | ✓ | — |
| `age_30_count` | integer | ✓ | — |
| `age_40_count` | integer | ✓ | — |
| `age_50_count` | integer | ✓ | — |
| `age_60_above_count` | integer | ✓ | — |

### `district_sales_seoul` — 475,334 rows

- 도메인: 프로덕션 데이터
- ORM 정의: ✓
- PK: `id`
- FK:
  - `dong_code` → `seoul_dong_master.dong_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | bigint | — | nextval('district_sales_seoul_… |
| `quarter` | integer | — | — |
| `dong_code` | character varying(15) | — | — |
| `dong_name` | text | ✓ | — |
| `industry_code` | character varying(20) | — | — |
| `industry_name` | text | ✓ | — |
| `monthly_sales` | bigint | ✓ | — |
| `monthly_count` | integer | ✓ | — |
| `raw_json` | jsonb | ✓ | — |

### `dong_centroid` — 16 rows

- 도메인: 마스터
- ORM 정의: ✓
- PK: `dong_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `dong_code` | character varying(8) | — | — |
| `dong_name` | text | ✓ | — |
| `lat` | double precision | — | — |
| `lon` | double precision | — | — |
| `source` | character varying(32) | — | 'store_info_avg'::character va… |
| `n_stores` | integer | ✓ | — |
| `created_at` | timestamp without time zone | ✓ | now() |
| `updated_at` | timestamp without time zone | ✓ | now() |

### `dong_mapping` — 16 rows

- 도메인: 마스터
- ORM 정의: ✓
- PK: `dong_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `dong_code` | character varying(10) | — | — |
| `dong_name` | character varying(20) | ✓ | — |
| `resident_pop` | integer | ✓ | — |
| `floating_pop` | double precision | ✓ | — |
| `avg_age` | double precision | ✓ | — |
| `total_households` | integer | ✓ | — |
| `trdar_codes` | jsonb | ✓ | — |

### `dong_subway_access` — 424 rows

- 도메인: 프로덕션 데이터
- ORM 정의: ✓
- PK: `dong_name`
- FK:
  - `dong_code` → `seoul_dong_master.dong_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `dong_name` | character varying(30) | — | — |
| `center_lat` | double precision | ✓ | — |
| `center_lon` | double precision | ✓ | — |
| `nearest_subway` | character varying(50) | ✓ | — |
| `subway_distance_m` | integer | ✓ | — |
| `subway_count_1km` | integer | ✓ | — |
| `dong_code` | character varying(10) | ✓ | — |

### `ecos_key_statistics` — 101 rows

- 도메인: 공공 통계
- ORM 정의: ✓
- PK: `keystat_name, cycle`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `class_name` | text | ✓ | — |
| `keystat_name` | text | — | — |
| `data_value` | double precision | ✓ | — |
| `cycle` | character varying(20) | — | — |
| `unit_name` | text | ✓ | — |
| `collected_at` | timestamp with time zone | ✓ | now() |

### `ecos_timeseries` — 2,783 rows

- 도메인: 공공 통계
- ORM 정의: ✓
- PK: `stat_code, item_code1, item_code2, period`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `stat_code` | character varying(20) | — | — |
| `stat_name` | text | ✓ | — |
| `item_code1` | character varying(30) | — | — |
| `item_name1` | text | ✓ | — |
| `item_code2` | character varying(30) | — | — |
| `item_name2` | text | ✓ | — |
| `cycle` | character varying(10) | ✓ | — |
| `period` | character varying(20) | — | — |
| `data_value` | double precision | ✓ | — |
| `unit_name` | text | ✓ | — |

### `elderly_ratio_region` — 1,566 rows

- 도메인: 프로덕션 데이터
- ORM 정의: ✓
- PK: `id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | bigint | — | nextval('elderly_ratio_region_… |
| `region` | text | — | — |
| `ym` | integer | — | — |
| `elderly_ratio` | double precision | ✓ | — |
| `elderly_pop` | bigint | ✓ | — |
| `total_pop` | bigint | ✓ | — |

### `ftc_brand_franchise` — 34,708 rows

- 도메인: 프로덕션 데이터
- ORM 정의: ✓
- PK: `id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | bigint | — | — |
| `yr` | bigint | ✓ | — |
| `corpNm` | text | ✓ | — |
| `brandNm` | text | ✓ | — |
| `indutyLclasNm` | text | ✓ | — |
| `indutyMlsfcNm` | text | ✓ | — |
| `frcsCnt` | bigint | ✓ | — |
| `newFrcsRgsCnt` | bigint | ✓ | — |
| `ctrtEndCnt` | bigint | ✓ | — |
| `ctrtCncltnCnt` | bigint | ✓ | — |
| `nmChgCnt` | bigint | ✓ | — |
| `avrgSlsAmt` | bigint | ✓ | — |
| `arUnitAvrgSlsAmt` | bigint | ✓ | — |

### `golmok_commercial` — 178,840 rows

- 도메인: 프로덕션 데이터
- ORM 정의: ✓
- PK: `id`
- FK:
  - `industry_code` → `industry_master.industry_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | integer | — | nextval('golmok_commercial_id_… |
| `quarter` | integer | ✓ | — |
| `trdar_code` | character varying(10) | ✓ | — |
| `data_type` | character varying(20) | ✓ | — |
| `industry_code` | character varying(20) | ✓ | — |
| `metrics` | jsonb | ✓ | — |

### `golmok_rent` — 472 rows

- 도메인: 프로덕션 데이터
- ORM 정의: ✓
- PK: `id`
- FK:
  - `dong_code` → `dong_mapping.dong_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | integer | — | nextval('golmok_rent_id_seq'::… |
| `year` | smallint | ✓ | — |
| `quarter` | smallint | ✓ | — |
| `dong_code` | character varying(10) | ✓ | — |
| `dong_name` | character varying(20) | ✓ | — |
| `gubun` | character varying(10) | ✓ | — |
| `rent_1f` | integer | ✓ | — |
| `rent_other` | integer | ✓ | — |
| `rent_total` | integer | ✓ | — |

### `golmok_sales` — 9,599 rows

- 도메인: 프로덕션 데이터
- ORM 정의: ✓
- PK: `quarter, trdar_code, industry_code`
- FK:
  - `industry_code` → `industry_master.industry_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `quarter` | bigint | — | — |
| `trdar_code` | text | — | — |
| `industry_code` | text | — | — |
| `monthly_sales` | bigint | ✓ | — |
| `monthly_count` | bigint | ✓ | — |
| `weekday_sales` | bigint | ✓ | — |
| `weekend_sales` | bigint | ✓ | — |
| `mon_sales` | bigint | ✓ | — |
| `tue_sales` | bigint | ✓ | — |
| `wed_sales` | bigint | ✓ | — |
| `thu_sales` | bigint | ✓ | — |
| `fri_sales` | bigint | ✓ | — |
| `sat_sales` | bigint | ✓ | — |
| `sun_sales` | bigint | ✓ | — |
| `time_00_06_sales` | bigint | ✓ | — |
| `time_06_11_sales` | bigint | ✓ | — |
| `time_11_14_sales` | bigint | ✓ | — |
| `time_14_17_sales` | bigint | ✓ | — |
| `time_17_21_sales` | bigint | ✓ | — |
| `time_21_24_sales` | bigint | ✓ | — |
| `male_sales` | bigint | ✓ | — |
| `female_sales` | bigint | ✓ | — |
| `age_10_sales` | bigint | ✓ | — |
| `age_20_sales` | bigint | ✓ | — |
| `age_30_sales` | bigint | ✓ | — |
| `age_40_sales` | bigint | ✓ | — |
| `age_50_sales` | bigint | ✓ | — |
| `age_60_above_sales` | bigint | ✓ | — |
| `weekday_count` | bigint | ✓ | — |
| `weekend_count` | bigint | ✓ | — |
| `mon_count` | bigint | ✓ | — |
| `tue_count` | bigint | ✓ | — |
| `wed_count` | bigint | ✓ | — |
| `thu_count` | bigint | ✓ | — |
| `fri_count` | bigint | ✓ | — |
| `sat_count` | bigint | ✓ | — |
| `sun_count` | bigint | ✓ | — |
| `time_00_06_count` | bigint | ✓ | — |
| `time_06_11_count` | bigint | ✓ | — |
| `time_11_14_count` | bigint | ✓ | — |
| `time_14_17_count` | bigint | ✓ | — |
| `time_17_21_count` | bigint | ✓ | — |
| `time_21_24_count` | bigint | ✓ | — |
| `male_count` | bigint | ✓ | — |
| `female_count` | bigint | ✓ | — |
| `age_10_count` | bigint | ✓ | — |
| `age_20_count` | bigint | ✓ | — |
| `age_30_count` | bigint | ✓ | — |
| `age_40_count` | bigint | ✓ | — |
| `age_50_count` | bigint | ✓ | — |
| `age_60_above_count` | bigint | ✓ | — |

### `golmok_stores` — 15,800 rows

- 도메인: 프로덕션 데이터
- ORM 정의: ✓
- PK: `quarter, trdar_code, industry_code`
- FK:
  - `industry_code` → `industry_master.industry_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `quarter` | bigint | — | — |
| `trdar_code` | text | — | — |
| `industry_code` | text | — | — |
| `store_count` | bigint | ✓ | — |
| `similar_store_count` | bigint | ✓ | — |
| `open_rate` | bigint | ✓ | — |
| `open_count` | bigint | ✓ | — |
| `close_rate` | bigint | ✓ | — |
| `close_count` | bigint | ✓ | — |
| `franchise_count` | bigint | ✓ | — |

### `holiday_calendar` — 3,287 rows

- 도메인: 마스터
- ORM 정의: ✓
- PK: `date`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `date` | date | — | — |
| `year` | integer | — | — |
| `month` | integer | — | — |
| `day` | integer | — | — |
| `dow` | integer | — | — |
| `dow_name` | character varying(10) | ✓ | — |
| `is_weekend` | boolean | — | — |
| `is_holiday` | boolean | — | — |
| `holiday_name` | character varying(50) | ✓ | — |
| `is_substitute` | boolean | ✓ | false |
| `day_type` | character varying(15) | ✓ | — |

### `industry_master` — 101 rows

- 도메인: 마스터
- ORM 정의: ✓
- PK: `industry_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `industry_code` | character varying(20) | — | — |
| `industry_name` | character varying(100) | — | — |
| `industry_name_alt` | character varying(100) | ✓ | — |
| `created_at` | timestamp with time zone | ✓ | now() |

### `invite_codes` — 16 rows

- 도메인: 회원/인증
- ORM 정의: ✓
- PK: `id`
- FK:
  - `owner_id` → `users.id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | integer | — | nextval('invite_codes_id_seq':… |
| `code` | character varying(20) | — | — |
| `owner_id` | uuid | — | — |
| `max_uses` | integer | ✓ | — |
| `used_count` | integer | ✓ | — |
| `is_active` | boolean | ✓ | — |
| `created_at` | timestamp with time zone | ✓ | now() |
| `expires_at` | timestamp with time zone | ✓ | — |

### `jeonse_dong_master` — 399 rows

- 도메인: 마스터
- ORM 정의: ✓
- PK: `dong_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `dong_code` | character varying(10) | — | — |
| `dong_name` | text | ✓ | — |
| `gu_code` | character varying(5) | ✓ | — |
| `gu_name` | text | ✓ | — |
| `created_at` | timestamp without time zone | ✓ | now() |

### `jeonse_monthly_rent` — 168,342 rows

- 도메인: 프로덕션 데이터
- ORM 정의: ✓
- PK: `id`
- FK:
  - `dong_code` → `jeonse_dong_master.dong_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | bigint | — | nextval('jeonse_monthly_rent_i… |
| `rcpt_year` | integer | ✓ | — |
| `gu_code` | character varying(10) | ✓ | — |
| `gu_name` | text | ✓ | — |
| `dong_code` | character varying(15) | ✓ | — |
| `dong_name` | text | ✓ | — |
| `jibun_type` | integer | ✓ | — |
| `jibun_type_name` | text | ✓ | — |
| `bon_beon` | integer | ✓ | — |
| `bu_beon` | integer | ✓ | — |
| `floor` | integer | ✓ | — |
| `contract_date` | integer | ✓ | — |
| `trade_type` | character varying(10) | ✓ | — |
| `area_sqm` | double precision | ✓ | — |
| `deposit_manwon` | bigint | ✓ | — |
| `monthly_rent_manwon` | bigint | ✓ | — |
| `building_name` | text | ✓ | — |
| `build_year` | integer | ✓ | — |
| `building_type` | text | ✓ | — |
| `contract_period` | text | ✓ | — |
| `new_renew` | text | ✓ | — |
| `renew_right_used` | text | ✓ | — |
| `prev_deposit` | double precision | ✓ | — |
| `prev_monthly_rent` | double precision | ✓ | — |

### `kakao_store` — 4,413 rows

- 도메인: 카카오 외부수집
- ORM 정의: ✓
- PK: `kakao_id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `kakao_id` | character varying(20) | — | — |
| `place_name` | character varying(200) | ✓ | — |
| `brand_name` | character varying(100) | ✓ | — |
| `category` | character varying(30) | ✓ | — |
| `category_detail` | character varying(200) | ✓ | — |
| `address` | text | ✓ | — |
| `road_address` | text | ✓ | — |
| `dong_name` | character varying(20) | ✓ | — |
| `lat` | double precision | ✓ | — |
| `lon` | double precision | ✓ | — |
| `phone` | character varying(20) | ✓ | — |
| `place_url` | text | ✓ | — |
| `collected_at` | timestamp with time zone | ✓ | now() |
| `is_franchise` | boolean | — | false |

### `kakao_store_hours` — 3,995 rows

- 도메인: 카카오 외부수집
- ORM 정의: ✓
- PK: `kakao_id`
- FK:
  - `kakao_id` → `kakao_store.kakao_id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `kakao_id` | character varying(20) | — | — |
| `headline_code` | character varying(20) | ✓ | — |
| `headline_text` | text | ✓ | — |
| `mon_hours` | text | ✓ | — |
| `tue_hours` | text | ✓ | — |
| `wed_hours` | text | ✓ | — |
| `thu_hours` | text | ✓ | — |
| `fri_hours` | text | ✓ | — |
| `sat_hours` | text | ✓ | — |
| `sun_hours` | text | ✓ | — |
| `hours_json` | jsonb | ✓ | — |
| `collected_at` | timestamp with time zone | ✓ | now() |

### `kakao_store_menu` — 81,037 rows

- 도메인: 카카오 외부수집
- ORM 정의: ✓
- PK: `id`
- FK:
  - `kakao_id` → `kakao_store.kakao_id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | bigint | — | nextval('kakao_store_menu_id_s… |
| `kakao_id` | character varying(20) | — | — |
| `product_id` | integer | ✓ | — |
| `menu_name` | text | — | — |
| `price` | integer | ✓ | — |
| `description` | text | ✓ | — |
| `photo_url` | text | ✓ | — |
| `mod_at` | timestamp without time zone | ✓ | — |
| `collected_at` | timestamp with time zone | ✓ | now() |

### `kosis_regional_income` — 1,116 rows

- 도메인: 공공 통계
- ORM 정의: ✓
- PK: `id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | bigint | — | nextval('kosis_regional_income… |
| `tbl_id` | character varying(30) | — | — |
| `tbl_name` | text | ✓ | — |
| `region_code` | character varying(20) | ✓ | — |
| `region_name` | text | ✓ | — |
| `item_code` | character varying(20) | ✓ | — |
| `item_name` | text | ✓ | — |
| `unit` | text | ✓ | — |
| `period_code` | character varying(10) | ✓ | — |
| `period_name` | character varying(20) | ✓ | — |
| `period_value` | character varying(20) | ✓ | — |
| `value_num` | double precision | ✓ | — |
| `src_last_chn_de` | date | ✓ | — |

### `langchain_pg_collection` — 1 rows

- 도메인: Vector DB
- ORM 정의: ✗
- PK: `uuid`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `uuid` | uuid | — | — |
| `name` | character varying | — | — |
| `cmetadata` | json | ✓ | — |

### `langchain_pg_embedding` — 10,255 rows

- 도메인: Vector DB
- ORM 정의: ✗
- PK: `id`
- FK:
  - `collection_id` → `langchain_pg_collection.uuid`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | character varying | — | — |
| `collection_id` | uuid | ✓ | — |
| `embedding` | USER-DEFINED | ✓ | — |
| `document` | character varying | ✓ | — |
| `cmetadata` | jsonb | ✓ | — |

### `law_legislations` — 57 rows

- 도메인: 법률 RAG
- ORM 정의: ✓
- PK: `item_id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `item_id` | character varying(50) | — | — |
| `title` | text | — | — |
| `law_short_name` | text | ✓ | — |
| `promulgation_date` | date | ✓ | — |
| `enforce_date` | date | ✓ | — |
| `promulgation_no` | character varying(50) | ✓ | — |
| `ministry_name` | text | ✓ | — |
| `law_type` | text | ✓ | — |
| `law_revision_type` | text | ✓ | — |
| `detail_link` | text | ✓ | — |
| `raw_json` | jsonb | ✓ | — |
| `queries` | text | ✓ | — |
| `collected_at` | timestamp with time zone | ✓ | now() |
| `body_text` | text | ✓ | — |
| `body_fetched_at` | timestamp with time zone | ✓ | — |

### `law_precedents` — 222 rows

- 도메인: 법률 RAG
- ORM 정의: ✓
- PK: `item_id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `item_id` | character varying(50) | — | — |
| `case_number` | character varying(100) | ✓ | — |
| `case_name` | text | ✓ | — |
| `case_type_code` | character varying(20) | ✓ | — |
| `case_type_name` | character varying(50) | ✓ | — |
| `sentence` | character varying(20) | ✓ | — |
| `sentence_date` | date | ✓ | — |
| `court_name` | text | ✓ | — |
| `judgment_type` | character varying(50) | ✓ | — |
| `detail_link` | text | ✓ | — |
| `data_source` | text | ✓ | — |
| `raw_json` | jsonb | ✓ | — |
| `queries` | text | ✓ | — |
| `collected_at` | timestamp with time zone | ✓ | now() |
| `body_text` | text | ✓ | — |
| `body_fetched_at` | timestamp with time zone | ✓ | — |

### `living_population` — 961,071 rows

- 도메인: 프로덕션 데이터
- ORM 정의: ✓
- PK: `date, time_zone, dong_code`
- FK:
  - `dong_code` → `dong_mapping.dong_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `date` | date | — | — |
| `time_zone` | smallint | — | — |
| `dong_code` | character varying(10) | — | — |
| `dong_name` | character varying(20) | ✓ | — |
| `total_pop` | double precision | ✓ | — |
| `male_0_9` | double precision | ✓ | — |
| `male_10_14` | double precision | ✓ | — |
| `male_15_19` | double precision | ✓ | — |
| `male_20_24` | double precision | ✓ | — |
| `male_25_29` | double precision | ✓ | — |
| `male_30_34` | double precision | ✓ | — |
| `male_35_39` | double precision | ✓ | — |
| `male_40_44` | double precision | ✓ | — |
| `male_45_49` | double precision | ✓ | — |
| `male_50_54` | double precision | ✓ | — |
| `male_55_59` | double precision | ✓ | — |
| `male_60_64` | double precision | ✓ | — |
| `male_65_69` | double precision | ✓ | — |
| `male_70_74` | double precision | ✓ | — |
| `male_70_plus` | double precision | ✓ | — |
| `female_0_9` | double precision | ✓ | — |
| `female_10_14` | double precision | ✓ | — |
| `female_15_19` | double precision | ✓ | — |
| `female_20_24` | double precision | ✓ | — |
| `female_25_29` | double precision | ✓ | — |
| `female_30_34` | double precision | ✓ | — |
| `female_35_39` | double precision | ✓ | — |
| `female_40_44` | double precision | ✓ | — |
| `female_45_49` | double precision | ✓ | — |
| `female_50_54` | double precision | ✓ | — |
| `female_55_59` | double precision | ✓ | — |
| `female_60_64` | double precision | ✓ | — |
| `female_65_69` | double precision | ✓ | — |
| `female_70_74` | double precision | ✓ | — |
| `female_70_plus` | double precision | ✓ | — |

### `living_population_grid` — 10,538,127 rows

- 도메인: 프로덕션 데이터
- ORM 정의: ✗
- PK: `cell_id, ymd, tt`
- FK:
  - `dong_code` → `dong_mapping.dong_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `ymd` | date | — | — |
| `tt` | smallint | — | — |
| `dong_code` | character varying(15) | — | — |
| `cell_id` | character varying(30) | — | — |
| `spop` | numeric | — | — |
| `m_0_9` | numeric | ✓ | — |
| `m_10_14` | numeric | ✓ | — |
| `m_15_19` | numeric | ✓ | — |
| `m_20_24` | numeric | ✓ | — |
| `m_25_29` | numeric | ✓ | — |
| `m_30_34` | numeric | ✓ | — |
| `m_35_39` | numeric | ✓ | — |
| `m_40_44` | numeric | ✓ | — |
| `m_45_49` | numeric | ✓ | — |
| `m_50_54` | numeric | ✓ | — |
| `m_55_59` | numeric | ✓ | — |
| `m_60_64` | numeric | ✓ | — |
| `m_65_69` | numeric | ✓ | — |
| `m_70_plus` | numeric | ✓ | — |
| `f_0_9` | numeric | ✓ | — |
| `f_10_14` | numeric | ✓ | — |
| `f_15_19` | numeric | ✓ | — |
| `f_20_24` | numeric | ✓ | — |
| `f_25_29` | numeric | ✓ | — |
| `f_30_34` | numeric | ✓ | — |
| `f_35_39` | numeric | ✓ | — |
| `f_40_44` | numeric | ✓ | — |
| `f_45_49` | numeric | ✓ | — |
| `f_50_54` | numeric | ✓ | — |
| `f_55_59` | numeric | ✓ | — |
| `f_60_64` | numeric | ✓ | — |
| `f_65_69` | numeric | ✓ | — |
| `f_70_plus` | numeric | ✓ | — |

### `manager_users` — 12 rows

- 도메인: 회원/인증
- ORM 정의: ✓
- PK: `id`
- FK:
  - `invite_code_id` → `invite_codes.id`
  - `owner_id` → `users.id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | uuid | — | — |
| `owner_id` | uuid | — | — |
| `invite_code_id` | integer | ✓ | — |
| `contact_name` | character varying(50) | — | — |
| `position` | character varying(50) | ✓ | — |
| `email` | character varying(100) | — | — |
| `phone` | character varying(20) | — | — |
| `password_hash` | character varying(255) | — | — |
| `is_active` | boolean | ✓ | — |
| `created_at` | timestamp with time zone | ✓ | now() |
| `is_approved` | boolean | ✓ | false |
| `assigned_gu` | character varying(20) | ✓ | — |
| `assigned_dongs` | json | ✓ | — |
| `updated_at` | timestamp with time zone | ✓ | now() |
| `last_login_at` | timestamp with time zone | ✓ | — |
| `email_verified` | boolean | ✓ | false |

### `mapo_resident_pop` — 408 rows

- 도메인: 마포 전용
- ORM 정의: ✓
- PK: `(없음)`
- FK:
  - `dong_code` → `dong_mapping.dong_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `quarter` | bigint | ✓ | — |
| `dong_code` | text | ✓ | — |
| `dong_name` | text | ✓ | — |
| `resident_pop` | double precision | ✓ | — |

### `mapo_schools` — 0 rows

- 도메인: 마포 전용
- ORM 정의: ✗
- PK: `id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | integer | — | nextval('mapo_schools_id_seq':… |
| `name` | character varying(200) | — | — |
| `school_type` | character varying(50) | ✓ | — |
| `address` | text | ✓ | — |
| `lat` | double precision | — | — |
| `lon` | double precision | — | — |
| `district` | character varying(50) | ✓ | — |
| `fetched_at` | timestamp with time zone | ✓ | now() |

### `mapo_sns_sentiment` — 377 rows

- 도메인: 마포 전용
- ORM 정의: ✓
- PK: `id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | bigint | — | nextval('mapo_sns_sentiment_id… |
| `place_name` | text | — | — |
| `date` | date | — | — |
| `positive_count` | integer | ✓ | — |
| `negative_count` | integer | ✓ | — |
| `neutral_count` | integer | ✓ | — |

### `mart_brand_territory` — 11,849 rows

- 도메인: 프로덕션 데이터
- ORM 정의: ✓
- PK: `id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | bigint | — | nextval('mart_brand_territory_… |
| `brand_name` | text | — | — |
| `corp_name` | text | ✓ | — |
| `yr` | integer | — | — |
| `territory_text` | text | ✓ | — |
| `territory_distance_m` | double precision | ✓ | — |
| `extraction_method` | text | ✓ | — |
| `extraction_confidence` | double precision | ✓ | — |
| `extracted_at` | timestamp with time zone | ✓ | now() |

### `master_subway_station` — 292 rows

- 도메인: 마스터
- ORM 정의: ✓
- PK: `station_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `station_code` | character varying(10) | — | — |
| `station_name` | character varying(50) | — | — |
| `line_name` | character varying(20) | ✓ | — |
| `sigungu_code` | character varying(5) | ✓ | — |
| `lat` | double precision | ✓ | — |
| `lon` | double precision | ✓ | — |
| `created_at` | timestamp without time zone | ✓ | now() |

### `master_ttareungi_station` — 5,541 rows

- 도메인: 마스터
- ORM 정의: ✓
- PK: `station_id`
- FK:
  - `dong_code` → `seoul_dong_master.dong_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `station_id` | character varying(20) | — | — |
| `station_name` | character varying(100) | — | — |
| `sigungu_code` | character varying(5) | ✓ | — |
| `dong_code` | character varying(8) | ✓ | — |
| `lat` | double precision | ✓ | — |
| `lon` | double precision | ✓ | — |
| `opened_at` | date | ✓ | — |
| `created_at` | timestamp without time zone | ✓ | now() |

### `molit_nrg_trade` — 8,731 rows

- 도메인: 공공 통계
- ORM 정의: ✓
- PK: `id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | bigint | — | nextval('molit_nrg_trade_id_se… |
| `lawd_cd` | character varying(10) | — | — |
| `gu_name` | character varying(20) | ✓ | — |
| `deal_ym` | integer | — | — |
| `deal_day` | integer | ✓ | — |
| `deal_amount` | bigint | ✓ | — |
| `building_use` | text | ✓ | — |
| `building_ar` | double precision | ✓ | — |
| `plottage_ar` | double precision | ✓ | — |
| `building_type` | text | ✓ | — |
| `realty_type` | text | ✓ | — |
| `floor` | text | ✓ | — |
| `build_year` | text | ✓ | — |
| `sgg_nm` | text | ✓ | — |
| `umd_nm` | text | ✓ | — |
| `jibun` | text | ✓ | — |
| `cdeal_type` | text | ✓ | — |
| `cdeal_day` | text | ✓ | — |
| `dealing_gbn` | text | ✓ | — |

### `naver_trend_industry` — 319 rows

- 도메인: 네이버 외부수집
- ORM 정의: ✓
- PK: `id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | bigint | — | nextval('naver_trend_industry_… |
| `industry` | text | — | — |
| `period` | date | — | — |
| `ratio` | double precision | ✓ | — |

### `naver_trend_monthly` — 33,985 rows

- 도메인: 네이버 외부수집
- ORM 정의: ✓
- PK: `id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | bigint | — | nextval('naver_trend_monthly_i… |
| `keyword` | text | — | — |
| `period` | date | — | — |
| `ratio` | double precision | ✓ | — |
| `scope` | character varying(10) | — | — |

### `naver_trend_quarterly` — 9,205 rows

- 도메인: 네이버 외부수집
- ORM 정의: ✓
- PK: `id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | bigint | — | nextval('naver_trend_quarterly… |
| `quarter` | integer | — | — |
| `dong_name` | character varying(30) | — | — |
| `trend_score` | double precision | ✓ | — |
| `scope` | character varying(10) | — | — |

### `naver_vacancy` — 1,341 rows

- 도메인: 네이버 외부수집
- ORM 정의: ✓
- PK: `id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | integer | — | nextval('naver_vacancy_id_seq'… |
| `trade_type` | character varying(10) | ✓ | — |
| `trade_code` | character varying(5) | ✓ | — |
| `lat` | double precision | ✓ | — |
| `lon` | double precision | ✓ | — |
| `listing_count` | integer | ✓ | — |
| `dong_name` | character varying(20) | ✓ | — |
| `lgeo` | character varying(30) | ✓ | — |
| `collected_at` | timestamp with time zone | ✓ | now() |

### `password_reset_tokens` — 0 rows

- 도메인: 회원/인증
- ORM 정의: ✗
- PK: `id`
- FK:
  - `user_id` → `users.id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | integer | — | nextval('password_reset_tokens… |
| `user_id` | uuid | — | — |
| `user_type` | character varying(10) | — | 'master'::character varying |
| `token` | character varying(64) | — | — |
| `expires_at` | timestamp with time zone | — | — |
| `used` | boolean | ✓ | false |
| `created_at` | timestamp with time zone | ✓ | now() |

### `rent_cost` — 248 rows

- 도메인: 프로덕션 데이터
- ORM 정의: ✓
- PK: `id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | integer | — | nextval('rent_cost_id_seq'::re… |
| `data_type` | character varying(20) | ✓ | — |
| `area_name` | character varying(50) | ✓ | — |
| `year` | smallint | ✓ | — |
| `quarter` | smallint | ✓ | — |
| `rent` | double precision | ✓ | — |
| `vacancy_rate` | double precision | ✓ | — |
| `investment_return` | double precision | ✓ | — |
| `income_return` | double precision | ✓ | — |
| `capital_return` | double precision | ✓ | — |
| `transaction_date` | character varying(10) | ✓ | — |
| `price` | bigint | ✓ | — |
| `floor_area` | double precision | ✓ | — |
| `floor` | character varying(10) | ✓ | — |
| `source` | character varying(20) | ✓ | — |

### `rent_cost_summary_2025` — 148 rows

- 도메인: 프로덕션 데이터
- ORM 정의: ✓
- PK: `id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | bigint | — | nextval('rent_cost_summary_202… |
| `region1` | text | ✓ | — |
| `region2` | text | ✓ | — |
| `rent_1000won_sqm` | double precision | ✓ | — |
| `vacancy_rate_pct` | double precision | ✓ | — |
| `investment_return_pct` | double precision | ✓ | — |
| `income_return_pct` | double precision | ✓ | — |
| `capital_return_pct` | double precision | ✓ | — |
| `source_file` | text | ✓ | — |

### `resident_pop_monthly` — 1,479 rows

- 도메인: 프로덕션 데이터
- ORM 정의: ✓
- PK: `region_full, ym`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `region_full` | text | — | — |
| `region_code` | character varying(15) | ✓ | — |
| `ym` | integer | — | — |
| `total_pop` | integer | ✓ | — |
| `households` | integer | ✓ | — |
| `pop_per_household` | double precision | ✓ | — |
| `male_pop` | integer | ✓ | — |
| `female_pop` | integer | ✓ | — |
| `male_female_ratio` | double precision | ✓ | — |

### `seoul_adstrd_change_ix` — 11,900 rows

- 도메인: 서울 행정동
- ORM 정의: ✓
- PK: `quarter, dong_code`
- FK:
  - `dong_code` → `seoul_dong_master.dong_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `quarter` | integer | — | — |
| `dong_code` | character varying(15) | — | — |
| `dong_name` | text | ✓ | — |
| `change_ix` | character varying(10) | ✓ | — |
| `change_ix_name` | character varying(50) | ✓ | — |
| `opr_sale_mt_avg` | double precision | ✓ | — |
| `cls_sale_mt_avg` | double precision | ✓ | — |
| `su_opr_sale_mt_avg` | double precision | ✓ | — |
| `su_cls_sale_mt_avg` | double precision | ✓ | — |

### `seoul_adstrd_fclty` — 336 rows

- 도메인: 서울 행정동
- ORM 정의: ✓
- PK: `quarter, dong_code`
- FK:
  - `dong_code` → `dong_mapping.dong_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `quarter` | integer | — | — |
| `dong_code` | character varying(15) | — | — |
| `dong_name` | text | ✓ | — |
| `viatr_fclty_co` | integer | ✓ | — |
| `pblofc_co` | integer | ✓ | — |
| `bank_co` | integer | ✓ | — |
| `gehspt_co` | integer | ✓ | — |
| `gnrl_hsptl_co` | integer | ✓ | — |
| `parmacy_co` | integer | ✓ | — |
| `kndrgr_co` | integer | ✓ | — |
| `elesch_co` | integer | ✓ | — |
| `mskul_co` | integer | ✓ | — |
| `hgschl_co` | integer | ✓ | — |
| `univ_co` | integer | ✓ | — |
| `drts_co` | integer | ✓ | — |
| `supmk_co` | integer | ✓ | — |
| `theat_co` | integer | ✓ | — |
| `stayng_fclty_co` | integer | ✓ | — |
| `arprt_co` | integer | ✓ | — |
| `rlroad_statn_co` | integer | ✓ | — |
| `bus_trminl_co` | integer | ✓ | — |
| `subway_statn_co` | integer | ✓ | — |
| `bus_sttn_co` | integer | ✓ | — |

### `seoul_adstrd_flpop` — 11,900 rows

- 도메인: 서울 행정동
- ORM 정의: ✓
- PK: `quarter, dong_code`
- FK:
  - `dong_code` → `seoul_dong_master.dong_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `quarter` | integer | — | — |
| `dong_code` | character varying(15) | — | — |
| `dong_name` | text | ✓ | — |
| `total_flpop` | integer | ✓ | — |
| `male_flpop` | integer | ✓ | — |
| `female_flpop` | integer | ✓ | — |
| `age_10` | integer | ✓ | — |
| `age_20` | integer | ✓ | — |
| `age_30` | integer | ✓ | — |
| `age_40` | integer | ✓ | — |
| `age_50` | integer | ✓ | — |
| `age_60_above` | integer | ✓ | — |
| `time_00_06` | integer | ✓ | — |
| `time_06_11` | integer | ✓ | — |
| `time_11_14` | integer | ✓ | — |
| `time_14_17` | integer | ✓ | — |
| `time_17_21` | integer | ✓ | — |
| `time_21_24` | integer | ✓ | — |
| `mon` | integer | ✓ | — |
| `tue` | integer | ✓ | — |
| `wed` | integer | ✓ | — |
| `thu` | integer | ✓ | — |
| `fri` | integer | ✓ | — |
| `sat` | integer | ✓ | — |
| `sun` | integer | ✓ | — |

### `seoul_adstrd_stor` — 849,552 rows

- 도메인: 서울 행정동
- ORM 정의: ✓
- PK: `quarter, dong_code, industry_code`
- FK:
  - `industry_code` → `industry_master.industry_code`
  - `dong_code` → `seoul_dong_master.dong_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `quarter` | integer | — | — |
| `dong_code` | character varying(15) | — | — |
| `dong_name` | text | ✓ | — |
| `industry_code` | character varying(20) | — | — |
| `industry_name` | text | ✓ | — |
| `store_count` | integer | ✓ | — |
| `similar_store_count` | integer | ✓ | — |
| `open_rate` | double precision | ✓ | — |
| `open_count` | integer | ✓ | — |
| `close_rate` | double precision | ✓ | — |
| `close_count` | integer | ✓ | — |
| `franchise_count` | integer | ✓ | — |

### `seoul_district_sales` — 87,938 rows

- 도메인: 서울 전역
- ORM 정의: ✓
- PK: `quarter, dong_code, industry_code`
- FK:
  - `industry_code` → `industry_master.industry_code`
  - `dong_code` → `seoul_dong_master.dong_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `quarter` | bigint | — | — |
| `dong_code` | text | — | — |
| `dong_name` | text | ✓ | — |
| `industry_code` | text | — | — |
| `industry_name` | text | ✓ | — |
| `monthly_sales` | bigint | ✓ | — |
| `monthly_count` | bigint | ✓ | — |
| `weekday_sales` | bigint | ✓ | — |
| `weekend_sales` | bigint | ✓ | — |
| `mon_sales` | bigint | ✓ | — |
| `tue_sales` | bigint | ✓ | — |
| `wed_sales` | bigint | ✓ | — |
| `thu_sales` | bigint | ✓ | — |
| `fri_sales` | bigint | ✓ | — |
| `sat_sales` | bigint | ✓ | — |
| `sun_sales` | bigint | ✓ | — |
| `time_00_06_sales` | bigint | ✓ | — |
| `time_06_11_sales` | bigint | ✓ | — |
| `time_11_14_sales` | bigint | ✓ | — |
| `time_14_17_sales` | bigint | ✓ | — |
| `time_17_21_sales` | bigint | ✓ | — |
| `time_21_24_sales` | bigint | ✓ | — |
| `male_sales` | bigint | ✓ | — |
| `female_sales` | bigint | ✓ | — |
| `age_10_sales` | bigint | ✓ | — |
| `age_20_sales` | bigint | ✓ | — |
| `age_30_sales` | bigint | ✓ | — |
| `age_40_sales` | bigint | ✓ | — |
| `age_50_sales` | bigint | ✓ | — |
| `age_60_above_sales` | bigint | ✓ | — |
| `weekday_count` | bigint | ✓ | — |
| `weekend_count` | bigint | ✓ | — |
| `mon_count` | bigint | ✓ | — |
| `tue_count` | bigint | ✓ | — |
| `wed_count` | bigint | ✓ | — |
| `thu_count` | bigint | ✓ | — |
| `fri_count` | bigint | ✓ | — |
| `sat_count` | bigint | ✓ | — |
| `sun_count` | bigint | ✓ | — |
| `time_00_06_count` | bigint | ✓ | — |
| `time_06_11_count` | bigint | ✓ | — |
| `time_11_14_count` | bigint | ✓ | — |
| `time_14_17_count` | bigint | ✓ | — |
| `time_17_21_count` | bigint | ✓ | — |
| `time_21_24_count` | bigint | ✓ | — |
| `male_count` | bigint | ✓ | — |
| `female_count` | bigint | ✓ | — |
| `age_10_count` | bigint | ✓ | — |
| `age_20_count` | bigint | ✓ | — |
| `age_30_count` | bigint | ✓ | — |
| `age_40_count` | bigint | ✓ | — |
| `age_50_count` | bigint | ✓ | — |
| `age_60_above_count` | bigint | ✓ | — |

### `seoul_district_sales_imputed_v4` — 137 rows

- 도메인: 서울 전역
- ORM 정의: ✗
- PK: `quarter, dong_code, industry_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `quarter` | bigint | — | — |
| `dong_code` | text | — | — |
| `industry_code` | text | — | — |
| `monthly_sales` | bigint | ✓ | — |
| `weekday_sales` | bigint | ✓ | — |
| `weekend_sales` | bigint | ✓ | — |
| `mon_sales` | bigint | ✓ | — |
| `tue_sales` | bigint | ✓ | — |
| `wed_sales` | bigint | ✓ | — |
| `thu_sales` | bigint | ✓ | — |
| `fri_sales` | bigint | ✓ | — |
| `sat_sales` | bigint | ✓ | — |
| `sun_sales` | bigint | ✓ | — |
| `time_00_06_sales` | bigint | ✓ | — |
| `time_06_11_sales` | bigint | ✓ | — |
| `time_11_14_sales` | bigint | ✓ | — |
| `time_14_17_sales` | bigint | ✓ | — |
| `time_17_21_sales` | bigint | ✓ | — |
| `time_21_24_sales` | bigint | ✓ | — |
| `male_sales` | bigint | ✓ | — |
| `female_sales` | bigint | ✓ | — |
| `age_10_sales` | bigint | ✓ | — |
| `age_20_sales` | bigint | ✓ | — |
| `age_30_sales` | bigint | ✓ | — |
| `age_40_sales` | bigint | ✓ | — |
| `age_50_sales` | bigint | ✓ | — |
| `age_60_above_sales` | bigint | ✓ | — |
| `monthly_count` | integer | ✓ | — |
| `weekday_count` | integer | ✓ | — |
| `weekend_count` | integer | ✓ | — |
| `mon_count` | integer | ✓ | — |
| `tue_count` | integer | ✓ | — |
| `wed_count` | integer | ✓ | — |
| `thu_count` | integer | ✓ | — |
| `fri_count` | integer | ✓ | — |
| `sat_count` | integer | ✓ | — |
| `sun_count` | integer | ✓ | — |
| `time_00_06_count` | integer | ✓ | — |
| `time_06_11_count` | integer | ✓ | — |
| `time_11_14_count` | integer | ✓ | — |
| `time_14_17_count` | integer | ✓ | — |
| `time_17_21_count` | integer | ✓ | — |
| `time_21_24_count` | integer | ✓ | — |
| `male_count` | integer | ✓ | — |
| `female_count` | integer | ✓ | — |
| `age_10_count` | integer | ✓ | — |
| `age_20_count` | integer | ✓ | — |
| `age_30_count` | integer | ✓ | — |
| `age_40_count` | integer | ✓ | — |
| `age_50_count` | integer | ✓ | — |
| `age_60_above_count` | integer | ✓ | — |
| `extrapolation_flag` | boolean | — | false |
| `confidence` | double precision | — | 1.0 |
| `source` | text | — | — |
| `created_at` | timestamp without time zone | — | now() |

### `seoul_district_sales_imputed_v4_detail` — 6,439 rows

- 도메인: 서울 전역
- ORM 정의: ✗
- PK: `quarter, dong_code, industry_code, column_name`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `quarter` | bigint | — | — |
| `dong_code` | text | — | — |
| `industry_code` | text | — | — |
| `column_name` | text | — | — |
| `imputed_value` | bigint | — | — |
| `lower_95` | bigint | — | — |
| `upper_95` | bigint | — | — |
| `std` | double precision | ✓ | — |
| `ci_width_ratio` | double precision | ✓ | — |
| `confidence` | double precision | — | 1.0 |

### `seoul_district_stores` — 100,587 rows

- 도메인: 서울 전역
- ORM 정의: ✓
- PK: `quarter, dong_code, industry_code`
- FK:
  - `dong_code` → `seoul_dong_master.dong_code`
  - `industry_code` → `industry_master.industry_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `quarter` | bigint | — | — |
| `dong_code` | text | — | — |
| `dong_name` | text | ✓ | — |
| `industry_code` | text | — | — |
| `industry_name` | text | ✓ | — |
| `store_count` | bigint | ✓ | — |
| `similar_store_count` | bigint | ✓ | — |
| `open_count` | bigint | ✓ | — |
| `close_count` | bigint | ✓ | — |
| `franchise_count` | bigint | ✓ | — |
| `closure_rate` | bigint | ✓ | — |

### `seoul_dong_master` — 431 rows

- 도메인: 서울 전역
- ORM 정의: ✓
- PK: `dong_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `dong_code` | character varying(8) | — | — |
| `dong_name` | text | ✓ | — |
| `sgg_code` | character varying(5) | ✓ | — |
| `comment` | text | ✓ | — |
| `created_at` | timestamp without time zone | ✓ | now() |

### `seoul_dong_migration_monthly` — 1,360 rows

- 도메인: 서울 전역
- ORM 정의: ✓
- PK: `ym, dong_code`
- FK:
  - `dong_code` → `seoul_dong_master.dong_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `ym` | integer | — | — |
| `dong_code` | character varying(8) | — | — |
| `move_in_cnt` | integer | ✓ | — |
| `move_out_cnt` | integer | ✓ | — |
| `net_move` | integer | ✓ | — |
| `move_in_2030` | integer | ✓ | — |
| `move_out_2030` | integer | ✓ | — |

### `seoul_golmok_rent` — 11,900 rows

- 도메인: 서울 전역
- ORM 정의: ✓
- PK: `year, quarter, dong_code`
- FK:
  - `dong_code` → `seoul_dong_master.dong_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `year` | bigint | — | — |
| `quarter` | bigint | — | — |
| `dong_code` | text | — | — |
| `dong_name` | text | ✓ | — |
| `gubun` | text | ✓ | — |
| `rent_1f` | double precision | ✓ | — |
| `rent_other` | double precision | ✓ | — |
| `rent_total` | double precision | ✓ | — |
| `quarter_code` | bigint | ✓ | — |

### `seoul_population_quarterly` — 10,176 rows

- 도메인: 서울 전역
- ORM 정의: ✓
- PK: `quarter, dong_code`
- FK:
  - `dong_code` → `seoul_dong_master.dong_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `quarter` | bigint | — | — |
| `dong_code` | text | — | — |
| `total_pop` | double precision | ✓ | — |

### `seoul_realtime_hotspots` — 1,876 rows

- 도메인: 서울 전역
- ORM 정의: ✓
- PK: `id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | bigint | — | nextval('seoul_realtime_hotspo… |
| `area_cd` | character varying(20) | — | — |
| `area_nm` | character varying(50) | — | — |
| `collected_at` | timestamp with time zone | — | now() |
| `congest_level` | character varying(10) | ✓ | — |
| `congest_msg` | text | ✓ | — |
| `pop_min` | integer | ✓ | — |
| `pop_max` | integer | ✓ | — |
| `male_rate` | double precision | ✓ | — |
| `female_rate` | double precision | ✓ | — |
| `age_0_10` | double precision | ✓ | — |
| `age_10s` | double precision | ✓ | — |
| `age_20s` | double precision | ✓ | — |
| `age_30s` | double precision | ✓ | — |
| `age_40s` | double precision | ✓ | — |
| `age_50s` | double precision | ✓ | — |
| `age_60s` | double precision | ✓ | — |
| `age_70_plus` | double precision | ✓ | — |
| `resident_rate` | double precision | ✓ | — |
| `visitor_rate` | double precision | ✓ | — |
| `cmrc_total_level` | character varying(10) | ✓ | — |
| `cmrc_payment_cnt` | character varying(20) | ✓ | — |
| `cmrc_payment_amt_min` | character varying(30) | ✓ | — |
| `cmrc_payment_amt_max` | character varying(30) | ✓ | — |

### `seoul_resident_pop_quarterly` — 13,508 rows

- 도메인: 서울 전역
- ORM 정의: ✗
- PK: `quarter, dong_code`
- FK:
  - `dong_code` → `seoul_dong_master.dong_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `quarter` | integer | — | — |
| `dong_code` | character varying(10) | — | — |
| `dong_name` | character varying(50) | — | — |
| `resident_pop` | integer | ✓ | — |

### `seoul_signgu_change_ix` — 700 rows

- 도메인: 서울 시군구
- ORM 정의: ✓
- PK: `quarter, signgu_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `quarter` | integer | — | — |
| `signgu_code` | character varying(10) | — | — |
| `signgu_name` | text | ✓ | — |
| `change_ix` | character varying(10) | ✓ | — |
| `change_ix_name` | character varying(50) | ✓ | — |
| `opr_sale_mt_avg` | double precision | ✓ | — |
| `cls_sale_mt_avg` | double precision | ✓ | — |
| `su_opr_sale_mt_avg` | double precision | ✓ | — |
| `su_cls_sale_mt_avg` | double precision | ✓ | — |

### `seoul_signgu_fclty` — 525 rows

- 도메인: 서울 시군구
- ORM 정의: ✓
- PK: `quarter, signgu_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `quarter` | integer | — | — |
| `signgu_code` | character varying(10) | — | — |
| `signgu_name` | text | ✓ | — |
| `viatr_fclty_co` | integer | ✓ | — |
| `pblofc_co` | integer | ✓ | — |
| `bank_co` | integer | ✓ | — |
| `gehspt_co` | integer | ✓ | — |
| `gnrl_hsptl_co` | integer | ✓ | — |
| `parmacy_co` | integer | ✓ | — |
| `kndrgr_co` | integer | ✓ | — |
| `elesch_co` | integer | ✓ | — |
| `mskul_co` | integer | ✓ | — |
| `hgschl_co` | integer | ✓ | — |
| `univ_co` | integer | ✓ | — |
| `drts_co` | integer | ✓ | — |
| `supmk_co` | integer | ✓ | — |
| `theat_co` | integer | ✓ | — |
| `stayng_fclty_co` | integer | ✓ | — |
| `arprt_co` | integer | ✓ | — |
| `rlroad_statn_co` | integer | ✓ | — |
| `bus_trminl_co` | integer | ✓ | — |
| `subway_statn_co` | integer | ✓ | — |
| `bus_sttn_co` | integer | ✓ | — |

### `seoul_signgu_flpop` — 700 rows

- 도메인: 서울 시군구
- ORM 정의: ✓
- PK: `quarter, signgu_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `quarter` | integer | — | — |
| `signgu_code` | character varying(10) | — | — |
| `signgu_name` | text | ✓ | — |
| `total_flpop` | integer | ✓ | — |
| `male_flpop` | integer | ✓ | — |
| `female_flpop` | integer | ✓ | — |
| `age_10` | integer | ✓ | — |
| `age_20` | integer | ✓ | — |
| `age_30` | integer | ✓ | — |
| `age_40` | integer | ✓ | — |
| `age_50` | integer | ✓ | — |
| `age_60_above` | integer | ✓ | — |
| `time_00_06` | integer | ✓ | — |
| `time_06_11` | integer | ✓ | — |
| `time_11_14` | integer | ✓ | — |
| `time_14_17` | integer | ✓ | — |
| `time_17_21` | integer | ✓ | — |
| `time_21_24` | integer | ✓ | — |
| `mon` | integer | ✓ | — |
| `tue` | integer | ✓ | — |
| `wed` | integer | ✓ | — |
| `thu` | integer | ✓ | — |
| `fri` | integer | ✓ | — |
| `sat` | integer | ✓ | — |
| `sun` | integer | ✓ | — |

### `seoul_signgu_selng` — 43,043 rows

- 도메인: 서울 시군구
- ORM 정의: ✓
- PK: `quarter, signgu_code, industry_code`
- FK:
  - `industry_code` → `industry_master.industry_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `quarter` | integer | — | — |
| `signgu_code` | character varying(10) | — | — |
| `signgu_name` | text | ✓ | — |
| `industry_code` | character varying(20) | — | — |
| `industry_name` | text | ✓ | — |
| `monthly_sales` | bigint | ✓ | — |
| `monthly_count` | bigint | ✓ | — |
| `weekday_sales` | bigint | ✓ | — |
| `weekend_sales` | bigint | ✓ | — |
| `mon_sales` | bigint | ✓ | — |
| `tue_sales` | bigint | ✓ | — |
| `wed_sales` | bigint | ✓ | — |
| `thu_sales` | bigint | ✓ | — |
| `fri_sales` | bigint | ✓ | — |
| `sat_sales` | bigint | ✓ | — |
| `sun_sales` | bigint | ✓ | — |

### `seoul_signgu_stor` — 69,704 rows

- 도메인: 서울 시군구
- ORM 정의: ✓
- PK: `quarter, signgu_code, industry_code`
- FK:
  - `industry_code` → `industry_master.industry_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `quarter` | integer | — | — |
| `signgu_code` | character varying(10) | — | — |
| `signgu_name` | text | ✓ | — |
| `industry_code` | character varying(20) | — | — |
| `industry_name` | text | ✓ | — |
| `store_count` | integer | ✓ | — |
| `similar_store_count` | integer | ✓ | — |
| `open_rate` | double precision | ✓ | — |
| `open_count` | integer | ✓ | — |
| `close_rate` | double precision | ✓ | — |
| `close_count` | integer | ✓ | — |
| `franchise_count` | integer | ✓ | — |

### `seoul_subway_passenger_daily` — 199,340 rows

- 도메인: 서울 전역
- ORM 정의: ✓
- PK: `date, station_code`
- FK:
  - `station_code` → `master_subway_station.station_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `date` | date | — | — |
| `station_code` | character varying(10) | — | — |
| `boarding_cnt` | integer | ✓ | — |
| `alighting_cnt` | integer | ✓ | — |

### `seoul_training_dataset` — 87,938 rows

- 도메인: 서울 전역
- ORM 정의: ✓
- PK: `quarter, dong_code, industry_code`
- FK:
  - `dong_code` → `seoul_dong_master.dong_code`
  - `industry_code` → `industry_master.industry_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `quarter` | bigint | — | — |
| `dong_code` | text | — | — |
| `dong_name` | text | ✓ | — |
| `industry_code` | text | — | — |
| `industry_name` | text | ✓ | — |
| `monthly_sales` | bigint | ✓ | — |
| `monthly_count` | bigint | ✓ | — |
| `store_count` | bigint | ✓ | — |
| `open_count` | bigint | ✓ | — |
| `close_count` | bigint | ✓ | — |
| `total_pop` | double precision | ✓ | — |
| `cpi_index` | double precision | ✓ | — |

### `seoul_trdar_change_ix` — 1,932 rows

- 도메인: 서울 상권
- ORM 정의: ✓
- PK: `quarter, trdar_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `quarter` | integer | — | — |
| `trdar_code` | character varying(15) | — | — |
| `trdar_name` | text | ✓ | — |
| `trdar_se` | character varying(10) | ✓ | — |
| `trdar_se_name` | character varying(30) | ✓ | — |
| `change_ix` | character varying(10) | ✓ | — |
| `change_ix_name` | character varying(50) | ✓ | — |
| `opr_sale_mt_avg` | double precision | ✓ | — |
| `cls_sale_mt_avg` | double precision | ✓ | — |
| `su_opr_sale_mt_avg` | double precision | ✓ | — |
| `su_cls_sale_mt_avg` | double precision | ✓ | — |

### `seoul_trdar_fclty` — 1,365 rows

- 도메인: 서울 상권
- ORM 정의: ✓
- PK: `quarter, trdar_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `quarter` | integer | — | — |
| `trdar_code` | character varying(15) | — | — |
| `trdar_name` | text | ✓ | — |
| `trdar_se` | character varying(10) | ✓ | — |
| `trdar_se_name` | character varying(30) | ✓ | — |
| `viatr_fclty_co` | integer | ✓ | — |
| `pblofc_co` | integer | ✓ | — |
| `bank_co` | integer | ✓ | — |
| `gehspt_co` | integer | ✓ | — |
| `gnrl_hsptl_co` | integer | ✓ | — |
| `parmacy_co` | integer | ✓ | — |
| `kndrgr_co` | integer | ✓ | — |
| `elesch_co` | integer | ✓ | — |
| `mskul_co` | integer | ✓ | — |
| `hgschl_co` | integer | ✓ | — |
| `univ_co` | integer | ✓ | — |
| `drts_co` | integer | ✓ | — |
| `supmk_co` | integer | ✓ | — |
| `theat_co` | integer | ✓ | — |
| `stayng_fclty_co` | integer | ✓ | — |
| `arprt_co` | integer | ✓ | — |
| `rlroad_statn_co` | integer | ✓ | — |
| `bus_trminl_co` | integer | ✓ | — |
| `subway_statn_co` | integer | ✓ | — |
| `bus_sttn_co` | integer | ✓ | — |

### `seoul_trdar_flpop` — 1,932 rows

- 도메인: 서울 상권
- ORM 정의: ✓
- PK: `quarter, trdar_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `quarter` | integer | — | — |
| `trdar_code` | character varying(15) | — | — |
| `trdar_name` | text | ✓ | — |
| `trdar_se` | character varying(10) | ✓ | — |
| `trdar_se_name` | character varying(30) | ✓ | — |
| `total_flpop` | integer | ✓ | — |
| `male_flpop` | integer | ✓ | — |
| `female_flpop` | integer | ✓ | — |
| `age_10` | integer | ✓ | — |
| `age_20` | integer | ✓ | — |
| `age_30` | integer | ✓ | — |
| `age_40` | integer | ✓ | — |
| `age_50` | integer | ✓ | — |
| `age_60_above` | integer | ✓ | — |
| `time_00_06` | integer | ✓ | — |
| `time_06_11` | integer | ✓ | — |
| `time_11_14` | integer | ✓ | — |
| `time_14_17` | integer | ✓ | — |
| `time_17_21` | integer | ✓ | — |
| `time_21_24` | integer | ✓ | — |
| `mon` | integer | ✓ | — |
| `tue` | integer | ✓ | — |
| `wed` | integer | ✓ | — |
| `thu` | integer | ✓ | — |
| `fri` | integer | ✓ | — |
| `sat` | integer | ✓ | — |
| `sun` | integer | ✓ | — |

### `seoul_ttareungi_usage_daily` — 985,653 rows

- 도메인: 서울 전역
- ORM 정의: ✓
- PK: `date, station_id`
- FK:
  - `station_id` → `master_ttareungi_station.station_id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `date` | date | — | — |
| `station_id` | character varying(20) | — | — |
| `rent_cnt` | integer | ✓ | — |
| `return_cnt` | integer | ✓ | — |

### `sgis_business` — 137,356 rows

- 도메인: 통계청 SGIS
- ORM 정의: ✓
- PK: `year, area_code, indicator`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `year` | smallint | — | — |
| `area_code` | character varying(14) | — | — |
| `indicator` | character varying(30) | — | — |
| `value` | double precision | ✓ | — |

### `sgis_household` — 25,550 rows

- 도메인: 통계청 SGIS
- ORM 정의: ✓
- PK: `year, area_code, indicator`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `year` | smallint | — | — |
| `area_code` | character varying(14) | — | — |
| `indicator` | character varying(30) | — | — |
| `value` | double precision | ✓ | — |

### `sgis_population` — 224,517 rows

- 도메인: 통계청 SGIS
- ORM 정의: ✓
- PK: `year, area_code, indicator`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `year` | smallint | — | — |
| `area_code` | character varying(14) | — | — |
| `indicator` | character varying(30) | — | — |
| `value` | double precision | ✓ | — |

### `simulation_ai` — 3 rows

- 도메인: 시뮬 결과/고객
- ORM 정의: ✓
- PK: `id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | bigint | — | nextval('simulation_ai_id_seq'… |
| `manager_id` | uuid | — | — |
| `user_type` | character varying(10) | ✓ | 'manager'::character varying |
| `client_name` | character varying(100) | — | — |
| `brand_name` | character varying(100) | — | — |
| `business_type` | character varying(50) | ✓ | — |
| `target_district` | character varying(50) | ✓ | — |
| `winner_district` | character varying(50) | ✓ | — |
| `top_3_candidates` | jsonb | ✓ | — |
| `analysis_report` | text | ✓ | — |
| `ai_recommendation` | text | ✓ | — |
| `ai_verdict_summary` | text | ✓ | — |
| `market_entry_signal` | character varying(10) | ✓ | — |
| `overall_legal_risk` | character varying(10) | ✓ | — |
| `legal_risks` | jsonb | ✓ | — |
| `market_report` | jsonb | ✓ | — |
| `trend_forecast` | jsonb | ✓ | — |
| `competitor_intel` | jsonb | ✓ | — |
| `demographic_report` | jsonb | ✓ | — |
| `district_rankings` | jsonb | ✓ | — |
| `agent_attributions` | jsonb | ✓ | — |
| `vacancy_applied` | boolean | ✓ | false |
| `all_competitor_locations` | jsonb | ✓ | — |
| `created_at` | timestamp with time zone | — | now() |
| `scenario` | jsonb | ✓ | — |

### `simulation_foresee` — 4 rows

- 도메인: 시뮬 결과/고객
- ORM 정의: ✓
- PK: `id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | bigint | — | nextval('simulation_foresee_id… |
| `manager_id` | uuid | — | — |
| `user_type` | character varying(10) | ✓ | 'manager'::character varying |
| `client_name` | character varying(100) | — | — |
| `brand_name` | character varying(100) | — | — |
| `business_type` | character varying(50) | ✓ | — |
| `districts` | jsonb | ✓ | — |
| `target_district` | character varying(50) | ✓ | — |
| `winner_district` | character varying(50) | ✓ | — |
| `district_predictions` | jsonb | ✓ | — |
| `quarterly_projection` | jsonb | ✓ | — |
| `scenarios` | jsonb | ✓ | — |
| `shap_result` | jsonb | ✓ | — |
| `bep_months` | integer | ✓ | — |
| `predicted_monthly_revenue` | bigint | ✓ | — |
| `closure_rate` | jsonb | ✓ | — |
| `closure_risk` | jsonb | ✓ | — |
| `final_report` | jsonb | ✓ | — |
| `market_report` | jsonb | ✓ | — |
| `customer_segment` | jsonb | ✓ | — |
| `living_pop_forecast` | jsonb | ✓ | — |
| `created_at` | timestamp with time zone | — | now() |
| `scenario` | jsonb | ✓ | — |

### `small_store_rent_q` — 10,020 rows

- 도메인: 프로덕션 데이터
- ORM 정의: ✓
- PK: `id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | bigint | — | nextval('small_store_rent_q_id… |
| `cls_id` | integer | — | — |
| `cls_full_nm` | text | — | — |
| `cls_nm` | text | ✓ | — |
| `region` | text | — | — |
| `year` | integer | — | — |
| `quarter` | integer | — | — |
| `rent` | double precision | ✓ | — |
| `statbl_id` | text | ✓ | — |

### `store_info` — 30,488 rows

- 도메인: 프로덕션 데이터
- ORM 정의: ✓
- PK: `store_id`
- FK:
  - `dong_code` → `dong_mapping.dong_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `store_id` | character varying(20) | — | — |
| `store_name` | character varying(100) | ✓ | — |
| `dong_code` | character varying(10) | ✓ | — |
| `dong_name` | character varying(20) | ✓ | — |
| `address` | text | ✓ | — |
| `road_address` | text | ✓ | — |
| `lat` | double precision | ✓ | — |
| `lon` | double precision | ✓ | — |
| `industry_l_code` | character varying(20) | ✓ | — |
| `industry_l` | character varying(50) | ✓ | — |
| `industry_m_code` | character varying(20) | ✓ | — |
| `industry_m` | character varying(50) | ✓ | — |
| `industry_s_code` | character varying(20) | ✓ | — |
| `industry_s` | character varying(50) | ✓ | — |
| `building_name` | character varying(100) | ✓ | — |
| `floor_info` | character varying(20) | ✓ | — |

### `store_quarterly` — 3,840 rows

- 도메인: 프로덕션 데이터
- ORM 정의: ✓
- PK: `quarter, dong_code, industry_code`
- FK:
  - `dong_code` → `dong_mapping.dong_code`
  - `industry_code` → `industry_master.industry_code`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `quarter` | integer | — | — |
| `dong_code` | character varying(10) | — | — |
| `industry_code` | character varying(20) | — | — |
| `dong_name` | character varying(20) | ✓ | — |
| `industry_name` | character varying(50) | ✓ | — |
| `store_count` | integer | ✓ | — |
| `open_count` | integer | ✓ | — |
| `close_count` | integer | ✓ | — |
| `closure_rate` | double precision | ✓ | — |
| `franchise_count` | integer | ✓ | — |

### `user_usage` — 0 rows

- 도메인: 회원/인증
- ORM 정의: ✗
- PK: `id`
- FK:
  - `user_id` → `users.id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | integer | — | nextval('user_usage_id_seq'::r… |
| `user_id` | uuid | — | — |
| `user_type` | character varying(10) | — | 'master'::character varying |
| `usage_date` | date | — | — |
| `simulation_count` | integer | ✓ | 0 |
| `created_at` | timestamp with time zone | ✓ | now() |

### `users` — 20 rows

- 도메인: 회원/인증
- ORM 정의: ✓
- PK: `id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | uuid | — | — |
| `company_name` | text | ✓ | — |
| `biz_number` | text | ✓ | — |
| `contact_name` | text | ✓ | — |
| `position` | text | ✓ | — |
| `email` | text | ✓ | — |
| `phone` | text | ✓ | — |
| `store_count` | bigint | ✓ | — |
| `password_hash` | text | ✓ | — |
| `plan` | text | ✓ | — |
| `agree_terms` | boolean | ✓ | — |
| `created_at` | timestamp with time zone | ✓ | — |
| `updated_at` | timestamp with time zone | ✓ | now() |
| `last_login_at` | timestamp with time zone | ✓ | — |
| `is_active` | boolean | ✓ | true |
| `email_verified` | boolean | ✓ | false |

### `vacancy_enriched` — 111 rows

- 도메인: 프로덕션 데이터
- ORM 정의: ✓
- PK: `id`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `id` | bigint | — | nextval('vacancy_enriched_id_s… |
| `lat` | double precision | ✓ | — |
| `lon` | double precision | ✓ | — |
| `dong_name` | character varying(30) | ✓ | — |
| `nearest_subway` | character varying(50) | ✓ | — |
| `subway_distance` | integer | ✓ | — |
| `restaurant_500m` | integer | ✓ | — |
| `cafe_500m` | integer | ✓ | — |
| `mart_500m` | integer | ✓ | — |
| `address` | text | ✓ | — |
| `road_address` | text | ✓ | — |
| `building_name` | character varying(200) | ✓ | — |
| `listing_count` | integer | ✓ | — |

### `weather_daily` — 2,665 rows

- 도메인: 프로덕션 데이터
- ORM 정의: ✓
- PK: `date, stn`

| 컬럼 | 타입 | NULL | 기본값 |
|---|---|---|---|
| `date` | date | — | — |
| `stn` | character varying(10) | — | — |
| `stn_name` | character varying(20) | ✓ | — |
| `wind_avg` | double precision | ✓ | — |
| `wind_max` | double precision | ✓ | — |
| `temp_avg` | double precision | ✓ | — |
| `temp_max` | double precision | ✓ | — |
| `temp_min` | double precision | ✓ | — |
| `humidity_avg` | double precision | ✓ | — |
| `humidity_min` | double precision | ✓ | — |
| `pressure_avg` | double precision | ✓ | — |
| `cloud_avg` | double precision | ✓ | — |
| `sunshine_hours` | double precision | ✓ | — |
| `insolation` | double precision | ✓ | — |
| `rain_day` | double precision | ✓ | — |
| `rain_60m_max` | double precision | ✓ | — |
| `snow_new` | double precision | ✓ | — |
| `snow_max` | double precision | ✓ | — |
