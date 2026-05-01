"""law_legislations + law_precedents body_text columns

Revision ID: bb22cc33dd44
Revises: aa11bb22cc33
Create Date: 2026-05-01

SP2 — 법령/판례 본문 사전 임베딩.
law.go.kr DRF API로 수집한 본문을 DB에 캐시 저장.
이후 chunks.json에 합쳐 BGE-m3 임베딩 → langchain_pg_embedding 적재.

컬럼:
- body_text: HTML 태그 제거된 평문 본문 (조문 또는 판시사항+판결요지+참조조문)
- body_fetched_at: 본문 수집 시각 (NULL = 미수집)
"""

import sqlalchemy as sa
from alembic import op


revision = "bb22cc33dd44"
down_revision = "aa11bb22cc33"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("law_legislations", sa.Column("body_text", sa.Text(), nullable=True))
    op.add_column(
        "law_legislations",
        sa.Column("body_fetched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("law_precedents", sa.Column("body_text", sa.Text(), nullable=True))
    op.add_column(
        "law_precedents",
        sa.Column("body_fetched_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("law_precedents", "body_fetched_at")
    op.drop_column("law_precedents", "body_text")
    op.drop_column("law_legislations", "body_fetched_at")
    op.drop_column("law_legislations", "body_text")
