"""merge simulation_history and orphan branches

Revision ID: 93cecfb0a772
Revises: a2f3b6d84e9c, c5d8a7b1e4f2
Create Date: 2026-04-22 12:46:10.423028

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "93cecfb0a772"
down_revision: Union[str, Sequence[str], None] = ("a2f3b6d84e9c", "c5d8a7b1e4f2")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
