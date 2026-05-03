"""add scenario column to simulation_foresee and simulation_ai

Revision ID: a04d71f50d19
Revises: df1beccf084e
Create Date: 2026-05-03 17:54:36.460389

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a04d71f50d19'
down_revision: Union[str, Sequence[str], None] = 'df1beccf084e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("simulation_foresee", sa.Column("scenario", postgresql.JSONB(), nullable=True, comment="시뮬 시나리오 파라미터 (재실행용)"))
    op.add_column("simulation_ai", sa.Column("scenario", postgresql.JSONB(), nullable=True, comment="시뮬 시나리오 파라미터 (재실행용)"))


def downgrade() -> None:
    op.drop_column("simulation_ai", "scenario")
    op.drop_column("simulation_foresee", "scenario")
