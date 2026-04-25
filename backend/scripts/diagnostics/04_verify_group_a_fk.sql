-- =============================================================================
-- 검증 SQL: 그룹 A FK 마이그레이션 적용 후 확인용
-- 작성: 2026-04-25
-- 담당: A1 (찬영)
--
-- 실행:
--   python backend/scripts/diagnostics/run_audit.py backend/scripts/diagnostics/04_verify_group_a_fk.sql
--
-- 안전성: 100% read-only
-- =============================================================================


-- -----------------------------------------------------------------------------
-- [1] 추가된 FK 4개 확인
-- -----------------------------------------------------------------------------
SELECT
    conname                                AS constraint_name,
    conrelid::regclass                     AS child_table,
    pg_get_constraintdef(oid)              AS definition,
    convalidated                           AS validated
FROM pg_constraint
WHERE contype = 'f'
  AND conname LIKE 'fk_%_dong'
ORDER BY conrelid::regclass::text;


-- -----------------------------------------------------------------------------
-- [2] alembic 적용 상태
-- -----------------------------------------------------------------------------
SELECT version_num
FROM alembic_version;


-- -----------------------------------------------------------------------------
-- [3] FK 동작 sanity check — 존재하지 않는 dong_code 입력 시 거부되는지
--     ※ ROLLBACK으로 끝나서 실제 데이터는 변하지 않음
-- -----------------------------------------------------------------------------
-- 의도적으로 잘못된 dong_code 삽입 시도 (ROLLBACK으로 마무리)
-- 정상이라면: ERROR  insert or update on table ... violates foreign key constraint
-- 비정상이라면: 행이 INSERT 되어버림 (이 경우 FK 미적용)
DO $$
BEGIN
    BEGIN
        INSERT INTO district_sales (quarter, dong_code, industry_code, monthly_sales)
        VALUES (99999, 'XXXXXXXX', 'TEST', 0);
        RAISE NOTICE '⚠️ FK 미작동: 잘못된 dong_code가 삽입됨';
    EXCEPTION WHEN foreign_key_violation THEN
        RAISE NOTICE '✅ FK 정상 동작: foreign_key_violation 발생';
    END;
    -- 무조건 롤백 (테스트 행 흔적 제거)
    RAISE EXCEPTION 'rollback test transaction';
EXCEPTION WHEN OTHERS THEN
    NULL;  -- 위 RAISE EXCEPTION 흡수
END $$;
