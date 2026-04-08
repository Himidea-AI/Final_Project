-- =============================================================================
-- V2: golmok_rent 테이블 추가
-- 생성일: 2026-04-08
-- 담당: A1 — 데이터 엔지니어 (찬영)
-- 참조: backend/src/database/models.py — GolmokRent 모델
-- =============================================================================
-- ※ V1 마이그레이션(11개 테이블)에서 누락된 테이블.
--    models.py에는 정의되어 있으나 alembic 마이그레이션 파일에 미포함.


-- =============================================================================
-- 행정동별 환산임대료 (golmok_rent)
-- 출처: 서울 상권분석서비스 (서울신용보증재단 기반)
-- 단위: 원/3.3㎡ (평당)
-- =============================================================================
CREATE TABLE IF NOT EXISTS golmok_rent (
    id          SERIAL          NOT NULL,           -- 자동증가 PK
    year        SMALLINT,                           -- 기준 연도
    quarter     SMALLINT,                           -- 기준 분기 (1~4)
    dong_code   VARCHAR(10),                        -- 행정동 코드
    dong_name   VARCHAR(20),                        -- 행정동명
    gubun       VARCHAR(10),                        -- 구분 (gu=구 단위 / dong=동 단위)
    rent_1f     INTEGER,                            -- 1층 환산임대료 (원/3.3㎡)
    rent_other  INTEGER,                            -- 1층 외 환산임대료 (원/3.3㎡)
    rent_total  INTEGER,                            -- 전체 환산임대료 (원/3.3㎡)
    PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS ix_golmok_rent_year      ON golmok_rent (year);
CREATE INDEX IF NOT EXISTS ix_golmok_rent_dong_code ON golmok_rent (dong_code);
