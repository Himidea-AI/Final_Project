-- =============================================================================
-- V1: 초기 스키마 — 마포구 상권분석 시뮬레이터 (11개 테이블)
-- 생성일: 2026-04-06
-- 담당: A1 — 데이터 엔지니어 (찬영)
-- Alembic revision: c3c01b64fb39 (initial_schema_11_tables_v2)
-- =============================================================================

-- pgvector 확장 활성화 (pgvector/pgvector:pg16 이미지 사용 시 사전 설치됨)
CREATE EXTENSION IF NOT EXISTS vector;


-- =============================================================================
-- 1. 생활인구 (living_population)
-- 출처: 서울 열린데이터 광장
-- 단위: 행정동 × 날짜 × 시간대
-- =============================================================================
CREATE TABLE IF NOT EXISTS living_population (
    date        DATE        NOT NULL,           -- 기준 날짜
    time_zone   SMALLINT    NOT NULL,           -- 시간대 구분 (0~23)
    dong_code   VARCHAR(10) NOT NULL,           -- 행정동 코드

    dong_name   VARCHAR(20),                    -- 행정동명
    total_pop   FLOAT,                          -- 전체 생활인구

    -- 남성 연령대 (5세 단위)
    male_0_9    FLOAT,
    male_10_14  FLOAT,
    male_15_19  FLOAT,
    male_20_24  FLOAT,
    male_25_29  FLOAT,
    male_30_34  FLOAT,
    male_35_39  FLOAT,
    male_40_44  FLOAT,
    male_45_49  FLOAT,
    male_50_54  FLOAT,
    male_55_59  FLOAT,
    male_60_64  FLOAT,
    male_65_69  FLOAT,
    male_70_74  FLOAT,
    male_70_plus FLOAT,

    -- 여성 연령대 (5세 단위)
    female_0_9   FLOAT,
    female_10_14 FLOAT,
    female_15_19 FLOAT,
    female_20_24 FLOAT,
    female_25_29 FLOAT,
    female_30_34 FLOAT,
    female_35_39 FLOAT,
    female_40_44 FLOAT,
    female_45_49 FLOAT,
    female_50_54 FLOAT,
    female_55_59 FLOAT,
    female_60_64 FLOAT,
    female_65_69 FLOAT,
    female_70_74 FLOAT,
    female_70_plus FLOAT,

    PRIMARY KEY (date, time_zone, dong_code)
);


-- =============================================================================
-- 2. SGIS 인구 통계 (sgis_population)
-- 출처: 통계지리정보서비스(SGIS)
-- =============================================================================
CREATE TABLE IF NOT EXISTS sgis_population (
    year        SMALLINT    NOT NULL,           -- 기준 연도
    area_code   VARCHAR(14) NOT NULL,           -- 행정구역 코드
    indicator   VARCHAR(30) NOT NULL,           -- 지표명
    value       FLOAT,                          -- 지표 값
    PRIMARY KEY (year, area_code, indicator)
);


-- =============================================================================
-- 3. SGIS 가구 통계 (sgis_household)
-- 출처: 통계지리정보서비스(SGIS)
-- =============================================================================
CREATE TABLE IF NOT EXISTS sgis_household (
    year        SMALLINT    NOT NULL,
    area_code   VARCHAR(14) NOT NULL,
    indicator   VARCHAR(30) NOT NULL,
    value       FLOAT,
    PRIMARY KEY (year, area_code, indicator)
);


-- =============================================================================
-- 4. SGIS 사업체 통계 (sgis_business)
-- 출처: 통계지리정보서비스(SGIS)
-- =============================================================================
CREATE TABLE IF NOT EXISTS sgis_business (
    year        SMALLINT    NOT NULL,
    area_code   VARCHAR(14) NOT NULL,
    indicator   VARCHAR(30) NOT NULL,
    value       FLOAT,
    PRIMARY KEY (year, area_code, indicator)
);


-- =============================================================================
-- 5. 골목상권 상업 데이터 (golmok_commercial)
-- 출처: 서울시 우리마을가게 상권분석 서비스
-- metrics 컬럼: JSONB로 sales/store/population 등 유형별 지표 저장
-- =============================================================================
CREATE TABLE IF NOT EXISTS golmok_commercial (
    id              SERIAL          NOT NULL,   -- 자동증가 PK
    quarter         INTEGER,                    -- 기준 분기 (YYYYQ, 예: 20241)
    trdar_code      VARCHAR(10),                -- 상권 코드
    data_type       VARCHAR(20),                -- 데이터 유형 (sales/store/population 등)
    industry_code   VARCHAR(20),                -- 업종 코드 (기본값: ALL)
    metrics         JSONB,                      -- 지표 데이터 (JSON)
    PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS ix_golmok_commercial_quarter   ON golmok_commercial (quarter);
CREATE INDEX IF NOT EXISTS ix_golmok_commercial_data_type ON golmok_commercial (data_type);


-- =============================================================================
-- 6. 행정동별 매출 통계 (district_sales)
-- 출처: 서울 우리마을가게 상권분석 서비스 (신용보증재단)
-- 단위: 행정동 × 분기 × 업종
-- =============================================================================
CREATE TABLE IF NOT EXISTS district_sales (
    quarter         INTEGER         NOT NULL,   -- 기준 분기 (YYYYQ)
    dong_code       VARCHAR(10)     NOT NULL,   -- 행정동 코드
    industry_code   VARCHAR(20)     NOT NULL,   -- 업종 코드

    dong_name       VARCHAR(20),                -- 행정동명
    industry_name   VARCHAR(50),                -- 업종명

    -- 매출 금액
    monthly_sales       BIGINT,                 -- 월 매출 금액
    monthly_count       INTEGER,                -- 월 매출 건수
    weekday_sales       BIGINT,                 -- 평일 매출 금액
    weekend_sales       BIGINT,                 -- 주말 매출 금액
    mon_sales           BIGINT,
    tue_sales           BIGINT,
    wed_sales           BIGINT,
    thu_sales           BIGINT,
    fri_sales           BIGINT,
    sat_sales           BIGINT,
    sun_sales           BIGINT,
    time_00_06_sales    BIGINT,
    time_06_11_sales    BIGINT,
    time_11_14_sales    BIGINT,
    time_14_17_sales    BIGINT,
    time_17_21_sales    BIGINT,
    time_21_24_sales    BIGINT,
    male_sales          BIGINT,
    female_sales        BIGINT,
    age_10_sales        BIGINT,
    age_20_sales        BIGINT,
    age_30_sales        BIGINT,
    age_40_sales        BIGINT,
    age_50_sales        BIGINT,
    age_60_above_sales  BIGINT,

    -- 매출 건수
    weekday_count       INTEGER,
    weekend_count       INTEGER,
    mon_count           INTEGER,
    tue_count           INTEGER,
    wed_count           INTEGER,
    thu_count           INTEGER,
    fri_count           INTEGER,
    sat_count           INTEGER,
    sun_count           INTEGER,
    time_00_06_count    INTEGER,
    time_06_11_count    INTEGER,
    time_11_14_count    INTEGER,
    time_14_17_count    INTEGER,
    time_17_21_count    INTEGER,
    time_21_24_count    INTEGER,
    male_count          INTEGER,
    female_count        INTEGER,
    age_10_count        INTEGER,
    age_20_count        INTEGER,
    age_30_count        INTEGER,
    age_40_count        INTEGER,
    age_50_count        INTEGER,
    age_60_above_count  INTEGER,

    PRIMARY KEY (quarter, dong_code, industry_code)
);
CREATE INDEX IF NOT EXISTS ix_district_sales_dong_code ON district_sales (dong_code);


-- =============================================================================
-- 7. 점포 기본 정보 (store_info)
-- 출처: 서울 우리마을가게 상권분석 서비스
-- =============================================================================
CREATE TABLE IF NOT EXISTS store_info (
    store_id        VARCHAR(20)     NOT NULL,   -- 점포 고유 ID
    store_name      VARCHAR(100),               -- 점포명
    dong_code       VARCHAR(10),                -- 행정동 코드
    dong_name       VARCHAR(20),                -- 행정동명
    address         TEXT,                       -- 지번 주소
    road_address    TEXT,                       -- 도로명 주소
    lat             FLOAT,                      -- 위도
    lon             FLOAT,                      -- 경도
    industry_l_code VARCHAR(20),                -- 대분류 업종 코드
    industry_l      VARCHAR(50),                -- 대분류 업종명
    industry_m_code VARCHAR(20),                -- 중분류 업종 코드
    industry_m      VARCHAR(50),                -- 중분류 업종명
    industry_s_code VARCHAR(20),                -- 소분류 업종 코드
    industry_s      VARCHAR(50),                -- 소분류 업종명
    building_name   VARCHAR(100),               -- 건물명
    floor_info      VARCHAR(20),                -- 층 정보
    PRIMARY KEY (store_id)
);
CREATE INDEX IF NOT EXISTS ix_store_info_dong_code      ON store_info (dong_code);
CREATE INDEX IF NOT EXISTS ix_store_info_dong_name      ON store_info (dong_name);
CREATE INDEX IF NOT EXISTS ix_store_info_industry_m_code ON store_info (industry_m_code);
CREATE INDEX IF NOT EXISTS ix_store_info_industry_m     ON store_info (industry_m);


-- =============================================================================
-- 8. 점포 분기별 통계 (store_quarterly)
-- 출처: 서울 우리마을가게 상권분석 서비스
-- =============================================================================
CREATE TABLE IF NOT EXISTS store_quarterly (
    quarter         INTEGER         NOT NULL,   -- 기준 분기 (YYYYQ)
    dong_code       VARCHAR(10)     NOT NULL,   -- 행정동 코드
    industry_code   VARCHAR(20)     NOT NULL,   -- 업종 코드

    dong_name       VARCHAR(20),                -- 행정동명
    industry_name   VARCHAR(50),                -- 업종명
    store_count     INTEGER,                    -- 점포 수
    open_count      INTEGER,                    -- 개업 점포 수
    close_count     INTEGER,                    -- 폐업 점포 수
    closure_rate    FLOAT,                      -- 폐업률
    franchise_count INTEGER,                    -- 프랜차이즈 점포 수

    PRIMARY KEY (quarter, dong_code, industry_code)
);
CREATE INDEX IF NOT EXISTS ix_store_quarterly_dong_code ON store_quarterly (dong_code);


-- =============================================================================
-- 9. 임대료 데이터 (rent_cost)
-- 출처: 한국부동산원 상업용 부동산 임대 동향 조사
-- =============================================================================
CREATE TABLE IF NOT EXISTS rent_cost (
    id                  SERIAL          NOT NULL,   -- 자동증가 PK
    data_type           VARCHAR(20),                -- 데이터 유형 (building_rent/rent_small_store)
    area_name           VARCHAR(50),                -- 지역명
    year                SMALLINT,                   -- 기준 연도
    quarter             SMALLINT,                   -- 기준 분기
    rent                FLOAT,                      -- 임대료 (만원/m²)
    vacancy_rate        FLOAT,                      -- 공실률
    investment_return   FLOAT,                      -- 투자 수익률
    income_return       FLOAT,                      -- 소득 수익률
    capital_return      FLOAT,                      -- 자본 수익률
    transaction_date    VARCHAR(10),                -- 거래 일자 (YYYY-MM-DD)
    price               BIGINT,                     -- 거래 금액 (만원)
    floor_area          FLOAT,                      -- 전용 면적 (m²)
    floor               VARCHAR(10),                -- 층 정보
    source              VARCHAR(20),                -- 데이터 출처
    PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS ix_rent_cost_data_type ON rent_cost (data_type);


-- =============================================================================
-- 10. 행정동 매핑 테이블 (dong_mapping)
-- 동코드 ↔ 동명, 인구, 상권 코드 매핑
-- =============================================================================
CREATE TABLE IF NOT EXISTS dong_mapping (
    dong_code           VARCHAR(10)     NOT NULL,   -- 행정동 코드 (PK)
    dong_name           VARCHAR(20),                -- 행정동명
    resident_pop        INTEGER,                    -- 주민등록 인구
    floating_pop        FLOAT,                      -- 유동인구
    avg_age             FLOAT,                      -- 평균 연령
    total_households    INTEGER,                    -- 총 가구 수
    trdar_codes         JSONB,                      -- 상권 코드 목록 (JSON 배열, 예: ["3000081","3000082"])
    PRIMARY KEY (dong_code)
);


-- =============================================================================
-- 11. 시뮬레이션 결과 (simulation_result)
-- 프랜차이즈 출점 분석 요청 및 결과 저장
-- =============================================================================
CREATE TABLE IF NOT EXISTS simulation_result (
    request_id      UUID            NOT NULL DEFAULT gen_random_uuid(),  -- 요청 고유 ID (UUID v4)
    created_at      DATE            DEFAULT now(),                        -- 요청 생성 일시
    input_params    JSONB,                                                -- 시뮬레이션 입력 파라미터 (JSON)
    output_result   JSONB,                                                -- 시뮬레이션 분석 결과 (JSON)
    status          VARCHAR(20),                                          -- 처리 상태 (pending/running/done/error)
    PRIMARY KEY (request_id)
);
