"""legal chunk_id constraint + cmetadata GIN index

Revision ID: aa11bb22cc33
Revises: f1a2b3c4d5e6
Create Date: 2026-04-30

법률 RAG 데이터 정합성 회복 (SP1) — langchain_pg_embedding 테이블에
chunk_id 부분 UNIQUE 인덱스 + cmetadata GIN 인덱스 추가.

테이블 구조 자체는 LangChain PGVector가 관리하므로 수정하지 않고
인덱스만 추가하여 LangChain 호환성 유지.

전제: phantom revision 18bfead869d5 정리 후 적용 가능
(IM3-alembic-user-lifecycle-catchup 브랜치 후속 작업).
"""

from alembic import op


revision = "aa11bb22cc33"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # chunk_id 부분 UNIQUE 인덱스
    # WHERE 절: cmetadata에 chunk_id가 있는 행만 UNIQUE 강제
    # → 옛 데이터(chunk_id 없음)와 공존 가능, cleanup 전에도 안전
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_legal_chunk_id
        ON langchain_pg_embedding ((cmetadata->>'chunk_id'))
        WHERE cmetadata ? 'chunk_id'
        """
    )

    # cmetadata 일반 검색 가속 (source/category/article 필터 빈번)
    # jsonb_path_ops: @> 연산자 최적화, 가장 가벼운 GIN 변종
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_legal_cmetadata_gin
        ON langchain_pg_embedding USING GIN (cmetadata jsonb_path_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_legal_cmetadata_gin")
    op.execute("DROP INDEX IF EXISTS uq_legal_chunk_id")
