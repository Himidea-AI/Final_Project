-- =============================================================================
-- 진단/정리 SQL: dong_code 고아 행 처리 (그룹 A 우선)
-- 작성: 2026-04-25
-- 담당: A1 (찬영)
--
-- ⚠️ 이 파일은 TEMPLATE입니다.
--    01_audit_dong_code.sql 결과를 보고:
--      • 고아 행이 0건이면 → 이 파일 실행 불필요, 바로 V4 마이그레이션으로
--      • 고아 행이 있으면  → 아래 정책 중 하나 선택 후 주석 해제하여 사용
--
-- 안전 패턴:
--    BEGIN;     ← 모든 변경은 트랜잭션 내부
--    ... DELETE/UPDATE ...
--    -- 결과 확인용 SELECT
--    ROLLBACK;  ← 디폴트 ROLLBACK. 확인 후 COMMIT으로 바꿔서 재실행
--
-- 실행:
--    psql "$POSTGRES_URL" -f backend/scripts/diagnostics/02_cleanup_orphan_dong_codes_TEMPLATE.sql
-- =============================================================================

\timing on
\set ON_ERROR_STOP on

BEGIN;

-- -----------------------------------------------------------------------------
-- 정책 선택지 (택 1)
--
-- [정책 A] 고아 행을 삭제 — 잘못된 dong_code 데이터로 판단되는 경우
-- [정책 B] dong_mapping에 누락된 코드를 추가 — 실제로는 유효한 동인 경우
-- [정책 C] 고아 dong_code를 가까운 마스터 코드로 매핑 — 코드 체계가 살짝 다른 경우
-- -----------------------------------------------------------------------------


-- =============================================================================
-- [정책 A] 고아 행 삭제 — 그룹 A 5개 테이블
-- =============================================================================
-- 사용 시점: 01 진단에서 고아 행이 잘못된 데이터(NULL/빈문자열/형식오류)인 경우
-- 효과:     해당 행이 영구 삭제됨

-- 사전 카운트 (dry-check)
-- SELECT 'living_population' AS tbl, COUNT(*) AS will_delete
--   FROM living_population t
--   WHERE NOT EXISTS (SELECT 1 FROM dong_mapping m WHERE m.dong_code = t.dong_code)
-- UNION ALL
-- SELECT 'district_sales', COUNT(*)
--   FROM district_sales t
--   WHERE NOT EXISTS (SELECT 1 FROM dong_mapping m WHERE m.dong_code = t.dong_code)
-- UNION ALL
-- SELECT 'store_info', COUNT(*)
--   FROM store_info t
--   WHERE NOT EXISTS (SELECT 1 FROM dong_mapping m WHERE m.dong_code = t.dong_code)
-- UNION ALL
-- SELECT 'store_quarterly', COUNT(*)
--   FROM store_quarterly t
--   WHERE NOT EXISTS (SELECT 1 FROM dong_mapping m WHERE m.dong_code = t.dong_code)
-- UNION ALL
-- SELECT 'golmok_rent', COUNT(*)
--   FROM golmok_rent t
--   WHERE NOT EXISTS (SELECT 1 FROM dong_mapping m WHERE m.dong_code = t.dong_code);

-- 실제 삭제 (주석 해제하여 사용)
-- DELETE FROM living_population t
--   WHERE NOT EXISTS (SELECT 1 FROM dong_mapping m WHERE m.dong_code = t.dong_code);
-- DELETE FROM district_sales t
--   WHERE NOT EXISTS (SELECT 1 FROM dong_mapping m WHERE m.dong_code = t.dong_code);
-- DELETE FROM store_info t
--   WHERE NOT EXISTS (SELECT 1 FROM dong_mapping m WHERE m.dong_code = t.dong_code);
-- DELETE FROM store_quarterly t
--   WHERE NOT EXISTS (SELECT 1 FROM dong_mapping m WHERE m.dong_code = t.dong_code);
-- DELETE FROM golmok_rent t
--   WHERE NOT EXISTS (SELECT 1 FROM dong_mapping m WHERE m.dong_code = t.dong_code);


-- =============================================================================
-- [정책 B] dong_mapping에 누락된 코드 추가
-- =============================================================================
-- 사용 시점: 마스터 데이터 자체가 불완전하고 자식 테이블의 코드는 유효한 경우
-- 효과:     dong_mapping에 신규 행 추가 (다른 컬럼은 NULL — 추후 보강)

-- 사전 카운트
-- SELECT COUNT(DISTINCT dong_code) AS will_insert
-- FROM (
--     SELECT dong_code FROM living_population WHERE dong_code IS NOT NULL
--     UNION SELECT dong_code FROM district_sales WHERE dong_code IS NOT NULL
--     UNION SELECT dong_code FROM store_info WHERE dong_code IS NOT NULL
--     UNION SELECT dong_code FROM store_quarterly WHERE dong_code IS NOT NULL
--     UNION SELECT dong_code FROM golmok_rent WHERE dong_code IS NOT NULL
-- ) child
-- WHERE NOT EXISTS (SELECT 1 FROM dong_mapping m WHERE m.dong_code = child.dong_code);

-- 실제 INSERT (주석 해제하여 사용)
-- INSERT INTO dong_mapping (dong_code, dong_name)
-- SELECT DISTINCT child.dong_code, NULL
-- FROM (
--     SELECT dong_code FROM living_population WHERE dong_code IS NOT NULL
--     UNION SELECT dong_code FROM district_sales WHERE dong_code IS NOT NULL
--     UNION SELECT dong_code FROM store_info WHERE dong_code IS NOT NULL
--     UNION SELECT dong_code FROM store_quarterly WHERE dong_code IS NOT NULL
--     UNION SELECT dong_code FROM golmok_rent WHERE dong_code IS NOT NULL
-- ) child
-- WHERE NOT EXISTS (SELECT 1 FROM dong_mapping m WHERE m.dong_code = child.dong_code);


-- =============================================================================
-- [정책 C] 고아 dong_code를 매핑 테이블로 보정
-- =============================================================================
-- 사용 시점: 코드가 살짝 다른 형식(예: 패딩, 자릿수). 별도 매핑 검토 후 작성.
-- 이 경우는 케이스별 SQL이 달라서 템플릿만 제공:
--
-- UPDATE living_population SET dong_code = '<correct>' WHERE dong_code = '<wrong>';
-- (반복)


-- -----------------------------------------------------------------------------
-- 사후 검증: 고아 행이 0이어야 함 (FK 추가 가능)
-- -----------------------------------------------------------------------------
SELECT 'living_population' AS tbl, COUNT(*) AS remaining_orphans
  FROM living_population t LEFT JOIN dong_mapping m USING(dong_code)
  WHERE m.dong_code IS NULL AND t.dong_code IS NOT NULL
UNION ALL
SELECT 'district_sales', COUNT(*)
  FROM district_sales t LEFT JOIN dong_mapping m USING(dong_code)
  WHERE m.dong_code IS NULL AND t.dong_code IS NOT NULL
UNION ALL
SELECT 'store_info', COUNT(*)
  FROM store_info t LEFT JOIN dong_mapping m USING(dong_code)
  WHERE m.dong_code IS NULL AND t.dong_code IS NOT NULL
UNION ALL
SELECT 'store_quarterly', COUNT(*)
  FROM store_quarterly t LEFT JOIN dong_mapping m USING(dong_code)
  WHERE m.dong_code IS NULL AND t.dong_code IS NOT NULL
UNION ALL
SELECT 'golmok_rent', COUNT(*)
  FROM golmok_rent t LEFT JOIN dong_mapping m USING(dong_code)
  WHERE m.dong_code IS NULL AND t.dong_code IS NOT NULL;


-- ⚠️ 디폴트는 ROLLBACK. 결과 확인 후 COMMIT으로 바꿔 재실행
ROLLBACK;
-- COMMIT;
