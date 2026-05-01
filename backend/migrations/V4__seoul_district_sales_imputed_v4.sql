-- backend/migrations/V4__seoul_district_sales_imputed_v4.sql

CREATE TABLE IF NOT EXISTS seoul_district_sales_imputed_v4 (
    quarter             BIGINT          NOT NULL,
    dong_code           TEXT            NOT NULL,
    industry_code       TEXT            NOT NULL,
    monthly_sales       BIGINT,
    weekday_sales       BIGINT,  weekend_sales       BIGINT,
    mon_sales BIGINT, tue_sales BIGINT, wed_sales BIGINT, thu_sales BIGINT,
    fri_sales BIGINT, sat_sales BIGINT, sun_sales BIGINT,
    time_00_06_sales BIGINT, time_06_11_sales BIGINT, time_11_14_sales BIGINT,
    time_14_17_sales BIGINT, time_17_21_sales BIGINT, time_21_24_sales BIGINT,
    male_sales BIGINT, female_sales BIGINT,
    age_10_sales BIGINT, age_20_sales BIGINT, age_30_sales BIGINT,
    age_40_sales BIGINT, age_50_sales BIGINT, age_60_above_sales BIGINT,
    monthly_count INTEGER,
    weekday_count INTEGER, weekend_count INTEGER,
    mon_count INTEGER, tue_count INTEGER, wed_count INTEGER, thu_count INTEGER,
    fri_count INTEGER, sat_count INTEGER, sun_count INTEGER,
    time_00_06_count INTEGER, time_06_11_count INTEGER, time_11_14_count INTEGER,
    time_14_17_count INTEGER, time_17_21_count INTEGER, time_21_24_count INTEGER,
    male_count INTEGER, female_count INTEGER,
    age_10_count INTEGER, age_20_count INTEGER, age_30_count INTEGER,
    age_40_count INTEGER, age_50_count INTEGER, age_60_above_count INTEGER,
    extrapolation_flag  BOOLEAN         NOT NULL DEFAULT FALSE,
    confidence          DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    source              TEXT            NOT NULL,
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW(),
    PRIMARY KEY (quarter, dong_code, industry_code)
);
COMMENT ON TABLE seoul_district_sales_imputed_v4 IS
  '담당: 찬영(A1) | 137 결측 셀 48 컬럼 Multi-Output ExtraTrees 6 seed 앙상블 복원 | 출처: KOSIS DT_1KC2023';
CREATE INDEX IF NOT EXISTS ix_v4_quarter_dong ON seoul_district_sales_imputed_v4(quarter, dong_code);

CREATE TABLE IF NOT EXISTS seoul_district_sales_imputed_v4_detail (
    quarter         BIGINT          NOT NULL,
    dong_code       TEXT            NOT NULL,
    industry_code   TEXT            NOT NULL,
    column_name     TEXT            NOT NULL,
    imputed_value   BIGINT          NOT NULL,
    lower_95        BIGINT          NOT NULL,
    upper_95        BIGINT          NOT NULL,
    std             DOUBLE PRECISION,
    ci_width_ratio  DOUBLE PRECISION,
    confidence      DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    PRIMARY KEY (quarter, dong_code, industry_code, column_name)
);
COMMENT ON TABLE seoul_district_sales_imputed_v4_detail IS
  '담당: 찬영(A1) | imputed_v4 의 47 세부 컬럼별 6 seed 95% CI long format | 행 수: 137 × 47 = 6,439';
CREATE INDEX IF NOT EXISTS ix_v4_detail_lookup ON seoul_district_sales_imputed_v4_detail(quarter, dong_code, industry_code);
