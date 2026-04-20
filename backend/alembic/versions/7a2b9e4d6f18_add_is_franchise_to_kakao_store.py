"""add is_franchise to kakao_store and make brand_name nullable

개인 점포까지 포함 전수 수집을 위해 is_franchise 컬럼 추가.
brand_name은 NORMALIZE_RULES 매칭된 경우만 채우도록 nullable화.

Revision ID: 7a2b9e4d6f18
Revises: b2d4e8f1c7a3
Create Date: 2026-04-20 10:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "7a2b9e4d6f18"
down_revision: Union[str, Sequence[str], None] = "b2d4e8f1c7a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, col: str) -> bool:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(table, schema="public"):
        return False
    cols = sa.inspect(bind).get_columns(table, schema="public")
    return any(c["name"] == col for c in cols)


def upgrade() -> None:
    if not _has_column("kakao_store", "is_franchise"):
        op.add_column(
            "kakao_store",
            sa.Column(
                "is_franchise",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
                comment="프랜차이즈 여부 (NORMALIZE_RULES 매칭 결과)",
            ),
        )
        op.create_index(
            "ix_kakao_store_is_franchise",
            "kakao_store",
            ["is_franchise"],
        )

    op.alter_column(
        "kakao_store",
        "brand_name",
        existing_type=sa.String(100),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "kakao_store",
        "brand_name",
        existing_type=sa.String(100),
        nullable=False,
    )
    op.drop_index("ix_kakao_store_is_franchise", table_name="kakao_store")
    op.drop_column("kakao_store", "is_franchise")
