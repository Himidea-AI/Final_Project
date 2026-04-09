-- backend/scripts/setup_pgvector_index.sql
-- pgvector 공간 연산 최적화를 위한 HNSW 인덱싱 설정

-- 1. pgvector 확장 활성화 확인
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. store_info 테이블에 위치 벡터 컬럼 추가 (위도, 경도 2차원)
-- 이미 존재한다면 스킵
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='store_info' AND column_name='location_vector') THEN
        ALTER TABLE store_info ADD COLUMN location_vector vector(2);
    END IF;
END $$;

-- 3. 기존 lat, lon 데이터를 location_vector로 마이그레이션
UPDATE store_info 
SET location_vector = ARRAY[lat, lon]::vector(2)
WHERE location_vector IS NULL AND lat IS NOT NULL AND lon IS NOT NULL;

-- 4. HNSW 인덱스 생성 (L2 거리 연산 최적화)
-- m: 최대 연결 수, ef_construction: 인덱스 생성 시 탐색 범위
CREATE INDEX IF NOT EXISTS idx_store_info_location_hnsw 
ON store_info USING hnsw (location_vector vector_l2_ops) 
WITH (m = 16, ef_construction = 64);

-- 5. 인덱스 통계 업데이트
ANALYZE store_info;
