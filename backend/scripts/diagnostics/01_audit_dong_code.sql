-- =============================================================================
-- 진단 SQL: dong_code FK 추가 전 정합성 검증
-- 작성: 2026-04-25
-- 담당: A1 (찬영)
--
-- 실행:
--   psql "$POSTGRES_URL" -f backend/scripts/diagnostics/01_audit_dong_code.sql
--
-- 안전성: 100% read-only (SELECT만, DDL/DML 없음)
--
-- 출력:
--   섹션 1 — dong_code 컬럼이 있는 모든 테이블 (자동 탐지)
--   섹션 2 — dong_mapping 마스터 상태
--   섹션 3 — 자식 테이블별 NULL/길이 분포/orphan 카운트
--   섹션 4 — 마스터에 없는 dong_code 샘플 (상위 20개)
-- =============================================================================

\timing on
\pset border 2
\pset linestyle unicode

-- -----------------------------------------------------------------------------
-- 섹션 1: dong_code 컬럼이 있는 모든 테이블 자동 탐지
-- -----------------------------------------------------------------------------
\echo '\n=== [1] dong_code 컬럼 보유 테이블 (information_schema) ==='

SELECT
    table_name,
    data_type,
    character_maximum_length AS max_len,
    is_nullable
FROM information_schema.columns
WHERE column_name = 'dong_code'
  AND table_schema = 'public'
ORDER BY data_type, character_maximum_length, table_name;


-- -----------------------------------------------------------------------------
-- 섹션 2: dong_mapping 마스터 상태
-- -----------------------------------------------------------------------------
\echo '\n=== [2] dong_mapping 마스터 상태 ==='

SELECT
    COUNT(*)                                         AS total_rows,
    COUNT(DISTINCT dong_code)                        AS distinct_codes,
    COUNT(*) FILTER (WHERE dong_code IS NULL)        AS null_codes,
    MIN(LENGTH(dong_code))                           AS min_len,
    MAX(LENGTH(dong_code))                           AS max_len,
    -- 마포구 코드는 1144로 시작 (행정동 표준코드 기준)
    COUNT(*) FILTER (WHERE dong_code LIKE '1144%')   AS mapo_count,
    COUNT(*) FILTER (WHERE dong_code NOT LIKE '1144%') AS non_mapo_count
FROM dong_mapping;

\echo '\n--- dong_mapping 상위 10개 sample ---'
SELECT dong_code, dong_name, LENGTH(dong_code) AS code_len
FROM dong_mapping
ORDER BY dong_code
LIMIT 10;


-- -----------------------------------------------------------------------------
-- 섹션 3: 자식 테이블별 정합성 통계
-- -----------------------------------------------------------------------------
\echo '\n=== [3] 자식 테이블별 정합성 (NULL / 길이분포 / orphan) ==='
\echo '※ orphan = dong_mapping에 없는 dong_code 보유 행 수'
\echo '※ 그룹 A(VARCHAR(10)) / 그룹 B(TEXT) / 그룹 C(VARCHAR(15))'

WITH stats AS (
    -- 그룹 A: VARCHAR(10) — 마포 운영 핵심
    SELECT 'A' AS grp, 'living_population' AS tbl, COUNT(*) AS rows,
           COUNT(*) FILTER (WHERE t.dong_code IS NULL) AS nulls,
           COUNT(DISTINCT t.dong_code) AS distinct_codes,
           COUNT(*) FILTER (WHERE m.dong_code IS NULL AND t.dong_code IS NOT NULL) AS orphan_rows,
           COUNT(DISTINCT t.dong_code) FILTER (WHERE m.dong_code IS NULL) AS orphan_distinct
    FROM living_population t LEFT JOIN dong_mapping m USING (dong_code)
    UNION ALL
    SELECT 'A','district_sales',COUNT(*),
           COUNT(*) FILTER (WHERE t.dong_code IS NULL),
           COUNT(DISTINCT t.dong_code),
           COUNT(*) FILTER (WHERE m.dong_code IS NULL AND t.dong_code IS NOT NULL),
           COUNT(DISTINCT t.dong_code) FILTER (WHERE m.dong_code IS NULL)
    FROM district_sales t LEFT JOIN dong_mapping m USING (dong_code)
    UNION ALL
    SELECT 'A','store_info',COUNT(*),
           COUNT(*) FILTER (WHERE t.dong_code IS NULL),
           COUNT(DISTINCT t.dong_code),
           COUNT(*) FILTER (WHERE m.dong_code IS NULL AND t.dong_code IS NOT NULL),
           COUNT(DISTINCT t.dong_code) FILTER (WHERE m.dong_code IS NULL)
    FROM store_info t LEFT JOIN dong_mapping m USING (dong_code)
    UNION ALL
    SELECT 'A','store_quarterly',COUNT(*),
           COUNT(*) FILTER (WHERE t.dong_code IS NULL),
           COUNT(DISTINCT t.dong_code),
           COUNT(*) FILTER (WHERE m.dong_code IS NULL AND t.dong_code IS NOT NULL),
           COUNT(DISTINCT t.dong_code) FILTER (WHERE m.dong_code IS NULL)
    FROM store_quarterly t LEFT JOIN dong_mapping m USING (dong_code)
    UNION ALL
    SELECT 'A','golmok_rent',COUNT(*),
           COUNT(*) FILTER (WHERE t.dong_code IS NULL),
           COUNT(DISTINCT t.dong_code),
           COUNT(*) FILTER (WHERE m.dong_code IS NULL AND t.dong_code IS NOT NULL),
           COUNT(DISTINCT t.dong_code) FILTER (WHERE m.dong_code IS NULL)
    FROM golmok_rent t LEFT JOIN dong_mapping m USING (dong_code)
    UNION ALL

    -- 그룹 B: TEXT — 서울 ML 학습용
    SELECT 'B','mapo_resident_pop',COUNT(*),
           COUNT(*) FILTER (WHERE t.dong_code IS NULL),
           COUNT(DISTINCT t.dong_code),
           COUNT(*) FILTER (WHERE m.dong_code IS NULL AND t.dong_code IS NOT NULL),
           COUNT(DISTINCT t.dong_code) FILTER (WHERE m.dong_code IS NULL)
    FROM mapo_resident_pop t LEFT JOIN dong_mapping m ON m.dong_code = t.dong_code
    UNION ALL
    SELECT 'B','seoul_district_sales',COUNT(*),
           COUNT(*) FILTER (WHERE t.dong_code IS NULL),
           COUNT(DISTINCT t.dong_code),
           COUNT(*) FILTER (WHERE m.dong_code IS NULL AND t.dong_code IS NOT NULL),
           COUNT(DISTINCT t.dong_code) FILTER (WHERE m.dong_code IS NULL)
    FROM seoul_district_sales t LEFT JOIN dong_mapping m ON m.dong_code = t.dong_code
    UNION ALL
    SELECT 'B','seoul_district_stores',COUNT(*),
           COUNT(*) FILTER (WHERE t.dong_code IS NULL),
           COUNT(DISTINCT t.dong_code),
           COUNT(*) FILTER (WHERE m.dong_code IS NULL AND t.dong_code IS NOT NULL),
           COUNT(DISTINCT t.dong_code) FILTER (WHERE m.dong_code IS NULL)
    FROM seoul_district_stores t LEFT JOIN dong_mapping m ON m.dong_code = t.dong_code
    UNION ALL
    SELECT 'B','seoul_golmok_rent',COUNT(*),
           COUNT(*) FILTER (WHERE t.dong_code IS NULL),
           COUNT(DISTINCT t.dong_code),
           COUNT(*) FILTER (WHERE m.dong_code IS NULL AND t.dong_code IS NOT NULL),
           COUNT(DISTINCT t.dong_code) FILTER (WHERE m.dong_code IS NULL)
    FROM seoul_golmok_rent t LEFT JOIN dong_mapping m ON m.dong_code = t.dong_code
    UNION ALL
    SELECT 'B','seoul_population_quarterly',COUNT(*),
           COUNT(*) FILTER (WHERE t.dong_code IS NULL),
           COUNT(DISTINCT t.dong_code),
           COUNT(*) FILTER (WHERE m.dong_code IS NULL AND t.dong_code IS NOT NULL),
           COUNT(DISTINCT t.dong_code) FILTER (WHERE m.dong_code IS NULL)
    FROM seoul_population_quarterly t LEFT JOIN dong_mapping m ON m.dong_code = t.dong_code
    UNION ALL
    SELECT 'B','seoul_training_dataset',COUNT(*),
           COUNT(*) FILTER (WHERE t.dong_code IS NULL),
           COUNT(DISTINCT t.dong_code),
           COUNT(*) FILTER (WHERE m.dong_code IS NULL AND t.dong_code IS NOT NULL),
           COUNT(DISTINCT t.dong_code) FILTER (WHERE m.dong_code IS NULL)
    FROM seoul_training_dataset t LEFT JOIN dong_mapping m ON m.dong_code = t.dong_code
    UNION ALL

    -- 그룹 C: VARCHAR(15) — 서울 통계 reflect
    SELECT 'C','district_sales_seoul',COUNT(*),
           COUNT(*) FILTER (WHERE t.dong_code IS NULL),
           COUNT(DISTINCT t.dong_code),
           COUNT(*) FILTER (WHERE m.dong_code IS NULL AND t.dong_code IS NOT NULL),
           COUNT(DISTINCT t.dong_code) FILTER (WHERE m.dong_code IS NULL)
    FROM district_sales_seoul t LEFT JOIN dong_mapping m ON m.dong_code = t.dong_code
    UNION ALL
    SELECT 'C','jeonse_monthly_rent',COUNT(*),
           COUNT(*) FILTER (WHERE t.dong_code IS NULL),
           COUNT(DISTINCT t.dong_code),
           COUNT(*) FILTER (WHERE m.dong_code IS NULL AND t.dong_code IS NOT NULL),
           COUNT(DISTINCT t.dong_code) FILTER (WHERE m.dong_code IS NULL)
    FROM jeonse_monthly_rent t LEFT JOIN dong_mapping m ON m.dong_code = t.dong_code
    UNION ALL
    SELECT 'C','seoul_adstrd_change_ix',COUNT(*),
           COUNT(*) FILTER (WHERE t.dong_code IS NULL),
           COUNT(DISTINCT t.dong_code),
           COUNT(*) FILTER (WHERE m.dong_code IS NULL AND t.dong_code IS NOT NULL),
           COUNT(DISTINCT t.dong_code) FILTER (WHERE m.dong_code IS NULL)
    FROM seoul_adstrd_change_ix t LEFT JOIN dong_mapping m ON m.dong_code = t.dong_code
    UNION ALL
    SELECT 'C','seoul_adstrd_fclty',COUNT(*),
           COUNT(*) FILTER (WHERE t.dong_code IS NULL),
           COUNT(DISTINCT t.dong_code),
           COUNT(*) FILTER (WHERE m.dong_code IS NULL AND t.dong_code IS NOT NULL),
           COUNT(DISTINCT t.dong_code) FILTER (WHERE m.dong_code IS NULL)
    FROM seoul_adstrd_fclty t LEFT JOIN dong_mapping m ON m.dong_code = t.dong_code
    UNION ALL
    SELECT 'C','seoul_adstrd_flpop',COUNT(*),
           COUNT(*) FILTER (WHERE t.dong_code IS NULL),
           COUNT(DISTINCT t.dong_code),
           COUNT(*) FILTER (WHERE m.dong_code IS NULL AND t.dong_code IS NOT NULL),
           COUNT(DISTINCT t.dong_code) FILTER (WHERE m.dong_code IS NULL)
    FROM seoul_adstrd_flpop t LEFT JOIN dong_mapping m ON m.dong_code = t.dong_code
    UNION ALL
    SELECT 'C','seoul_adstrd_stor',COUNT(*),
           COUNT(*) FILTER (WHERE t.dong_code IS NULL),
           COUNT(DISTINCT t.dong_code),
           COUNT(*) FILTER (WHERE m.dong_code IS NULL AND t.dong_code IS NOT NULL),
           COUNT(DISTINCT t.dong_code) FILTER (WHERE m.dong_code IS NULL)
    FROM seoul_adstrd_stor t LEFT JOIN dong_mapping m ON m.dong_code = t.dong_code
)
SELECT
    grp                                        AS "그룹",
    tbl                                        AS "테이블",
    rows                                       AS "총행수",
    nulls                                      AS "NULL",
    distinct_codes                             AS "고유코드",
    orphan_rows                                AS "고아행수",
    orphan_distinct                            AS "고아고유",
    CASE WHEN rows = 0 THEN 0
         ELSE ROUND(100.0 * orphan_rows / rows, 1)
    END                                        AS "고아%"
FROM stats
ORDER BY grp, tbl;


-- -----------------------------------------------------------------------------
-- 섹션 4: 마스터에 없는 dong_code 샘플 (그룹 A 우선)
-- -----------------------------------------------------------------------------
\echo '\n=== [4] 마스터에 없는 dong_code 샘플 (그룹 A — 마포 핵심) ==='

(SELECT 'living_population' AS src, dong_code, COUNT(*) AS cnt
 FROM living_population t
 WHERE NOT EXISTS (SELECT 1 FROM dong_mapping m WHERE m.dong_code = t.dong_code)
   AND t.dong_code IS NOT NULL
 GROUP BY dong_code ORDER BY cnt DESC LIMIT 5)
UNION ALL
(SELECT 'district_sales', dong_code, COUNT(*)
 FROM district_sales t
 WHERE NOT EXISTS (SELECT 1 FROM dong_mapping m WHERE m.dong_code = t.dong_code)
   AND t.dong_code IS NOT NULL
 GROUP BY dong_code ORDER BY 3 DESC LIMIT 5)
UNION ALL
(SELECT 'store_info', dong_code, COUNT(*)
 FROM store_info t
 WHERE NOT EXISTS (SELECT 1 FROM dong_mapping m WHERE m.dong_code = t.dong_code)
   AND t.dong_code IS NOT NULL
 GROUP BY dong_code ORDER BY 3 DESC LIMIT 5)
UNION ALL
(SELECT 'golmok_rent', dong_code, COUNT(*)
 FROM golmok_rent t
 WHERE NOT EXISTS (SELECT 1 FROM dong_mapping m WHERE m.dong_code = t.dong_code)
   AND t.dong_code IS NOT NULL
 GROUP BY dong_code ORDER BY 3 DESC LIMIT 5);


\echo '\n=== 진단 완료 ==='
\echo '다음 단계 결정 가이드:'
\echo '  • 그룹 A 고아% < 1%   → 바로 cleanup + FK 가능'
\echo '  • 그룹 A 고아% > 5%   → 마스터 데이터 보정 먼저'
\echo '  • 그룹 B/C 고아% 높음 → dong_mapping 서울 전체 확장 OR 별도 마스터 필요'
