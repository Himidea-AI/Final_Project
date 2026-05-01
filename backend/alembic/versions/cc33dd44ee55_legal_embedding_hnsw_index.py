"""legal embedding HNSW ANN index

Revision ID: cc33dd44ee55
Revises: bb22cc33dd44
Create Date: 2026-05-01

SP3 — pgvector HNSW (Hierarchical Navigable Small World) ANN 인덱스 추가.
9,484 청크 규모에서 풀스캔 → ANN 전환으로 검색 시간 단축.

파라미터:
- m=16:               각 노드의 최대 연결 수 (default)
- ef_construction=64: 인덱스 빌드 시 정확도/속도 trade-off (default)
- vector_cosine_ops:  cosine 거리 연산자 (BGE-m3 임베딩이 normalize되어 있어 cosine ≈ dot)

전제: SP2 reingest 완료 후 적용 권장 (인덱스 빌드는 INSERT 부하와 충돌 가능).
"""

from alembic import op


revision = "cc33dd44ee55"
down_revision = "bb22cc33dd44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_legal_embedding_hnsw
        ON langchain_pg_embedding
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_legal_embedding_hnsw")
