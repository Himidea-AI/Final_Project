"""merge ftc_unique + emerging_trend

Revision ID: 18bfead869d5
Revises: b9c1e3f5d7a2, b9c5d7e1f2a3
Create Date: 2026-04-29 15:19:03.203113

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '18bfead869d5'
down_revision: Union[str, Sequence[str], None] = ('b9c1e3f5d7a2', 'b9c5d7e1f2a3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
