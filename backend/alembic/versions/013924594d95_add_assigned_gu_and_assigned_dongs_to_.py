"""add assigned_gu and assigned_dongs to manager_users

Revision ID: 013924594d95
Revises: f6ec0ac9d88c
Create Date: 2026-04-14 10:50:42.717910

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "013924594d95"
down_revision: Union[str, Sequence[str], None] = "f6ec0ac9d88c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "manager_users",
        sa.Column("assigned_gu", sa.String(length=20), nullable=True, comment="담당 구 (예: 마포구)"),
    )
    op.add_column(
        "manager_users",
        sa.Column(
            "assigned_dongs",
            sa.JSON(),
            nullable=True,
            comment='담당 행정동 배열 (예: ["서교동","합정동"])',
        ),
    )


def downgrade() -> None:
    op.drop_column("manager_users", "assigned_dongs")
    op.drop_column("manager_users", "assigned_gu")
