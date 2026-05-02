"""merge ftc_emerging + legal_hnsw

Revision ID: bfd610a9aa07
Revises: 18bfead869d5, cc33dd44ee55
Create Date: 2026-05-01 13:08:48.950751

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bfd610a9aa07'
down_revision: Union[str, Sequence[str], None] = ('18bfead869d5', 'cc33dd44ee55')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
