-- =============================================================================
-- 진단 SQL: 보류 케이스 상세 + 자동 탐지 누락 테이블 정합성 검증
-- 작성: 2026-04-25
-- 담당: A1 (찬영)
--
-- 목적:
--   1. golmok_rent / mapo_resident_pop 의 '11440' 행 상세 확인
--   2. 01 audit에서 빠진 3개 테이블 정합성 보강:
--        - dong_subway_access
--        - seoul_resident_pop_quarterly
--        - living_population_grid  (그룹 C 인데 누락됐었음)
--
-- 실행:
--   python backend/scripts/diagnostics/run_audit.py backend/scripts/diagnostics/03_inspect_special_cases.sql
--
-- 안전성: 100% read-only
-- =============================================================================


-- -----------------------------------------------------------------------------
-- [1] golmok_rent: '11440' 행 상세 (자치구 단위 집계로 추정되는 행)
-- -----------------------------------------------------------------------------
SELECT
    dong_code,
    dong_name,
    gubun,
    year,
    quarter,
    COUNT(*) AS row_count
FROM golmok_rent
WHERE dong_code = '11440'
GROUP BY dong_code, dong_name, gubun, year, quarter
ORDER BY year, quarter;


-- -----------------------------------------------------------------------------
-- [2] mapo_resident_pop: 고아 행 상세
-- -----------------------------------------------------------------------------
SELECT
    dong_code,
    dong_name,
    quarter,
    resident_pop
FROM mapo_resident_pop
WHERE NOT EXISTS (SELECT 1 FROM dong_mapping m WHERE m.dong_code = mapo_resident_pop.dong_code)
ORDER BY quarter
LIMIT 30;


-- -----------------------------------------------------------------------------
-- [3] 01 audit에서 누락된 테이블 정합성
-- -----------------------------------------------------------------------------
WITH stats AS (
    SELECT 'dong_subway_access' AS tbl, COUNT(*) AS rows,
           COUNT(*) FILTER (WHERE t.dong_code IS NULL) AS nulls,
           COUNT(DISTINCT t.dong_code) AS distinct_codes,
           COUNT(*) FILTER (WHERE m.dong_code IS NULL AND t.dong_code IS NOT NULL) AS orphan_rows,
           COUNT(DISTINCT t.dong_code) FILTER (WHERE m.dong_code IS NULL) AS orphan_distinct
    FROM dong_subway_access t LEFT JOIN dong_mapping m USING (dong_code)
    UNION ALL
    SELECT 'seoul_resident_pop_quarterly', COUNT(*),
           COUNT(*) FILTER (WHERE t.dong_code IS NULL),
           COUNT(DISTINCT t.dong_code),
           COUNT(*) FILTER (WHERE m.dong_code IS NULL AND t.dong_code IS NOT NULL),
           COUNT(DISTINCT t.dong_code) FILTER (WHERE m.dong_code IS NULL)
    FROM seoul_resident_pop_quarterly t LEFT JOIN dong_mapping m USING (dong_code)
    UNION ALL
    SELECT 'living_population_grid', COUNT(*),
           COUNT(*) FILTER (WHERE t.dong_code IS NULL),
           COUNT(DISTINCT t.dong_code),
           COUNT(*) FILTER (WHERE m.dong_code IS NULL AND t.dong_code IS NOT NULL),
           COUNT(DISTINCT t.dong_code) FILTER (WHERE m.dong_code IS NULL)
    FROM living_population_grid t LEFT JOIN dong_mapping m ON m.dong_code = t.dong_code
)
SELECT
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
ORDER BY tbl;


-- -----------------------------------------------------------------------------
-- [4] dong_subway_access 의 dong_code 샘플 (마포만 있는지 확인용)
-- -----------------------------------------------------------------------------
SELECT
    dong_code,
    LEFT(dong_code, 5) AS gu_prefix,
    COUNT(*) AS cnt
FROM dong_subway_access
WHERE dong_code IS NOT NULL
GROUP BY dong_code
ORDER BY cnt DESC
LIMIT 20;
