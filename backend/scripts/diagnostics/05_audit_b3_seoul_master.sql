-- =============================================================================
-- B-3 진단: 서울 전체 동 마스터 신설 의사결정용
-- 작성: 2026-04-25
--
-- 목적:
--   1. 자식 테이블 distinct dong_code 분포 파악 (총 동 수, 코드 형식)
--   2. jeonse_monthly_rent의 dong_code 정체 확인 (100% 고아였음)
--   3. 자식 테이블 union 시 dong_name 충돌 여부
--   4. seoul_dong_master 후보 데이터 추출 가능성
--
-- 안전성: 100% read-only
-- =============================================================================


-- -----------------------------------------------------------------------------
-- [1] 그룹 B/C 자식 테이블별 dong_code 길이/자치구 분포
-- -----------------------------------------------------------------------------
WITH samples AS (
    SELECT 'seoul_district_sales' AS tbl, dong_code FROM seoul_district_sales WHERE dong_code IS NOT NULL
    UNION ALL SELECT 'seoul_district_stores', dong_code FROM seoul_district_stores WHERE dong_code IS NOT NULL
    UNION ALL SELECT 'seoul_population_quarterly', dong_code FROM seoul_population_quarterly WHERE dong_code IS NOT NULL
    UNION ALL SELECT 'seoul_golmok_rent', dong_code FROM seoul_golmok_rent WHERE dong_code IS NOT NULL
    UNION ALL SELECT 'seoul_training_dataset', dong_code FROM seoul_training_dataset WHERE dong_code IS NOT NULL
    UNION ALL SELECT 'district_sales_seoul', dong_code FROM district_sales_seoul WHERE dong_code IS NOT NULL
    UNION ALL SELECT 'seoul_adstrd_change_ix', dong_code FROM seoul_adstrd_change_ix WHERE dong_code IS NOT NULL
    UNION ALL SELECT 'seoul_adstrd_flpop', dong_code FROM seoul_adstrd_flpop WHERE dong_code IS NOT NULL
    UNION ALL SELECT 'seoul_adstrd_stor', dong_code FROM seoul_adstrd_stor WHERE dong_code IS NOT NULL
    UNION ALL SELECT 'dong_subway_access', dong_code FROM dong_subway_access WHERE dong_code IS NOT NULL
    UNION ALL SELECT 'seoul_resident_pop_quarterly', dong_code FROM seoul_resident_pop_quarterly WHERE dong_code IS NOT NULL
)
SELECT
    tbl                                              AS "테이블",
    COUNT(*)                                         AS "총행수",
    COUNT(DISTINCT dong_code)                        AS "고유코드수",
    MIN(LENGTH(dong_code))                           AS "최소길이",
    MAX(LENGTH(dong_code))                           AS "최대길이",
    COUNT(DISTINCT LEFT(dong_code, 5))               AS "자치구수"
FROM samples
GROUP BY tbl
ORDER BY tbl;


-- -----------------------------------------------------------------------------
-- [2] jeonse_monthly_rent: dong_code 정체 확인
--     100% 고아였는데 어떤 형식인지 + gu_code와 관계
-- -----------------------------------------------------------------------------
SELECT
    LENGTH(dong_code)                AS code_len,
    COUNT(*)                         AS rows,
    COUNT(DISTINCT dong_code)        AS distinct_codes,
    MIN(dong_code)                   AS sample_min,
    MAX(dong_code)                   AS sample_max
FROM jeonse_monthly_rent
WHERE dong_code IS NOT NULL
GROUP BY LENGTH(dong_code)
ORDER BY code_len;


-- jeonse_monthly_rent: gu_code + dong_code 조합 샘플
SELECT
    gu_code,
    gu_name,
    LEFT(dong_code, 8) AS dong_prefix,
    dong_code,
    dong_name,
    COUNT(*) AS cnt
FROM jeonse_monthly_rent
WHERE dong_code IS NOT NULL
GROUP BY gu_code, gu_name, dong_code, dong_name
ORDER BY cnt DESC
LIMIT 10;


-- -----------------------------------------------------------------------------
-- [3] dong_name 충돌 검사 — 같은 dong_code에 다른 dong_name?
-- -----------------------------------------------------------------------------
WITH all_pairs AS (
    SELECT dong_code, dong_name FROM seoul_district_sales WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
    UNION ALL SELECT dong_code, dong_name FROM seoul_district_stores WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
    UNION ALL SELECT dong_code, dong_name FROM seoul_golmok_rent WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
    UNION ALL SELECT dong_code, dong_name FROM seoul_adstrd_change_ix WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
    UNION ALL SELECT dong_code, dong_name FROM seoul_adstrd_flpop WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
    UNION ALL SELECT dong_code, dong_name FROM seoul_adstrd_stor WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
    UNION ALL SELECT dong_code, dong_name FROM seoul_adstrd_fclty WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
)
SELECT COUNT(*) AS "충돌_dong_code수"
FROM (
    SELECT dong_code
    FROM all_pairs
    GROUP BY dong_code
    HAVING COUNT(DISTINCT dong_name) > 1
) conflicts;


-- 충돌 샘플 (최대 10개)
WITH all_pairs AS (
    SELECT dong_code, dong_name FROM seoul_district_sales WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
    UNION ALL SELECT dong_code, dong_name FROM seoul_district_stores WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
    UNION ALL SELECT dong_code, dong_name FROM seoul_golmok_rent WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
    UNION ALL SELECT dong_code, dong_name FROM seoul_adstrd_change_ix WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
    UNION ALL SELECT dong_code, dong_name FROM seoul_adstrd_flpop WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
    UNION ALL SELECT dong_code, dong_name FROM seoul_adstrd_stor WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
)
SELECT
    dong_code,
    ARRAY_AGG(DISTINCT dong_name) AS distinct_names
FROM all_pairs
GROUP BY dong_code
HAVING COUNT(DISTINCT dong_name) > 1
LIMIT 10;


-- -----------------------------------------------------------------------------
-- [4] seoul_dong_master 후보 — distinct (dong_code, dong_name) union
-- -----------------------------------------------------------------------------
WITH all_pairs AS (
    SELECT DISTINCT dong_code, dong_name FROM seoul_district_sales WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
    UNION SELECT DISTINCT dong_code, dong_name FROM seoul_district_stores WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
    UNION SELECT DISTINCT dong_code, dong_name FROM seoul_golmok_rent WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
    UNION SELECT DISTINCT dong_code, dong_name FROM seoul_adstrd_change_ix WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
    UNION SELECT DISTINCT dong_code, dong_name FROM seoul_adstrd_flpop WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
    UNION SELECT DISTINCT dong_code, dong_name FROM seoul_adstrd_stor WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
    UNION SELECT DISTINCT dong_code, dong_name FROM seoul_adstrd_fclty WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
)
SELECT
    COUNT(*)                                   AS "총_(code,name)_쌍",
    COUNT(DISTINCT dong_code)                  AS "고유_dong_code",
    COUNT(DISTINCT LEFT(dong_code, 5))         AS "자치구수",
    MIN(LENGTH(dong_code))                     AS "최소길이",
    MAX(LENGTH(dong_code))                     AS "최대길이"
FROM all_pairs;


-- -----------------------------------------------------------------------------
-- [5] dong_name 없는 테이블의 dong_code 매칭 가능성
--     (master 만든 후 이 테이블들이 그 master로 join 가능한지)
-- -----------------------------------------------------------------------------
WITH master_codes AS (
    SELECT DISTINCT dong_code FROM seoul_district_sales WHERE dong_code IS NOT NULL
    UNION SELECT DISTINCT dong_code FROM seoul_district_stores WHERE dong_code IS NOT NULL
    UNION SELECT DISTINCT dong_code FROM seoul_golmok_rent WHERE dong_code IS NOT NULL
    UNION SELECT DISTINCT dong_code FROM seoul_adstrd_change_ix WHERE dong_code IS NOT NULL
    UNION SELECT DISTINCT dong_code FROM seoul_adstrd_flpop WHERE dong_code IS NOT NULL
    UNION SELECT DISTINCT dong_code FROM seoul_adstrd_stor WHERE dong_code IS NOT NULL
    UNION SELECT DISTINCT dong_code FROM seoul_adstrd_fclty WHERE dong_code IS NOT NULL
)
SELECT
    'seoul_population_quarterly' AS tbl,
    COUNT(DISTINCT t.dong_code) AS distinct_codes,
    COUNT(DISTINCT t.dong_code) FILTER (WHERE m.dong_code IS NULL) AS not_in_master
FROM seoul_population_quarterly t
LEFT JOIN master_codes m USING (dong_code)
WHERE t.dong_code IS NOT NULL
UNION ALL
SELECT
    'seoul_training_dataset',
    COUNT(DISTINCT t.dong_code),
    COUNT(DISTINCT t.dong_code) FILTER (WHERE m.dong_code IS NULL)
FROM seoul_training_dataset t
LEFT JOIN master_codes m USING (dong_code)
WHERE t.dong_code IS NOT NULL
UNION ALL
SELECT
    'district_sales_seoul',
    COUNT(DISTINCT t.dong_code),
    COUNT(DISTINCT t.dong_code) FILTER (WHERE m.dong_code IS NULL)
FROM district_sales_seoul t
LEFT JOIN master_codes m USING (dong_code)
WHERE t.dong_code IS NOT NULL
UNION ALL
SELECT
    'dong_subway_access',
    COUNT(DISTINCT t.dong_code),
    COUNT(DISTINCT t.dong_code) FILTER (WHERE m.dong_code IS NULL)
FROM dong_subway_access t
LEFT JOIN master_codes m USING (dong_code)
WHERE t.dong_code IS NOT NULL
UNION ALL
SELECT
    'seoul_resident_pop_quarterly',
    COUNT(DISTINCT t.dong_code),
    COUNT(DISTINCT t.dong_code) FILTER (WHERE m.dong_code IS NULL)
FROM seoul_resident_pop_quarterly t
LEFT JOIN master_codes m USING (dong_code)
WHERE t.dong_code IS NOT NULL;
