"""merge foresee_ai + dev

Revision ID: df1beccf084e
Revises: 1ea09aac2adb, d4f1a2b3c5e6
Create Date: 2026-05-03 17:54:02.713460

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'df1beccf084e'
down_revision: Union[str, Sequence[str], None] = ('1ea09aac2adb', 'd4f1a2b3c5e6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
