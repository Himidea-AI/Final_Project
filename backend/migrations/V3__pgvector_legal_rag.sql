-- =============================================================================
-- V3: pgvector RAG 테이블 — 법률 문서 벡터 검색 (langchain_postgres)
-- 생성일: 2026-04-08
-- 담당: A2 — RAG 엔지니어 (봉봉)
-- 참조: backend/src/database/vector_db.py — LegalVectorDB
-- =============================================================================
-- ※ 이 테이블들은 langchain_postgres 라이브러리가 자동 생성합니다.
--    (PGVector.from_documents() 또는 PGVector(connection=...) 최초 호출 시)
--    직접 실행하지 않아도 되며, 스키마 참조 및 수동 초기화용으로 제공합니다.
--
-- 컬렉션명: "legal_documents"
-- 임베딩 모델: paraphrase-multilingual-MiniLM-L12-v2 (384차원)
-- =============================================================================

-- pgvector 확장 활성화 (V1에서 이미 실행됨 — 중복 실행 무해)
CREATE EXTENSION IF NOT EXISTS vector;


-- =============================================================================
-- langchain_pg_collection — 컬렉션 메타데이터
-- langchain_postgres 내부 스키마 (수정 금지)
-- =============================================================================
CREATE TABLE IF NOT EXISTS langchain_pg_collection (
    uuid        UUID            NOT NULL DEFAULT gen_random_uuid(),
    name        VARCHAR         NOT NULL,           -- 컬렉션명 (예: "legal_documents")
    cmetadata   JSONB,                              -- 컬렉션 메타데이터
    PRIMARY KEY (uuid),
    UNIQUE (name)
);


-- =============================================================================
-- langchain_pg_embedding — 임베딩 벡터 + 문서 본문 + 메타데이터
-- langchain_postgres 내부 스키마 (수정 금지)
-- 384차원: paraphrase-multilingual-MiniLM-L12-v2 기준
-- =============================================================================
CREATE TABLE IF NOT EXISTS langchain_pg_embedding (
    id              UUID            NOT NULL DEFAULT gen_random_uuid(),
    collection_id   UUID            REFERENCES langchain_pg_collection (uuid) ON DELETE CASCADE,
    embedding       vector(384),                    -- 벡터 (384차원)
    document        VARCHAR,                        -- 청크 본문 텍스트
    cmetadata       JSONB,                          -- 문서 메타데이터 (source, page, law_name 등)
    PRIMARY KEY (id)
);

-- 벡터 유사도 검색 인덱스 (IVFFLAT — 근사 최근접 이웃 검색)
-- 데이터 로드 완료 후 실행 권장 (빈 테이블에서 생성 시 효과 없음)
-- lists 값 기준: sqrt(청크수) 권장 — 3,775청크 기준 약 61
CREATE INDEX IF NOT EXISTS ix_langchain_pg_embedding_vector
    ON langchain_pg_embedding
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 64);

-- 컬렉션 ID 기준 일반 인덱스
CREATE INDEX IF NOT EXISTS ix_langchain_pg_embedding_collection_id
    ON langchain_pg_embedding (collection_id);

-- cmetadata 기준 GIN 인덱스 (메타데이터 필터링용)
CREATE INDEX IF NOT EXISTS ix_langchain_pg_embedding_cmetadata
    ON langchain_pg_embedding USING gin (cmetadata);
