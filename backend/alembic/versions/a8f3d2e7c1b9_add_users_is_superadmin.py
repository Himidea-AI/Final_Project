"""add is_superadmin column to users

Revision ID: a8f3d2e7c1b9
Revises: 91b66e68ec18
Create Date: 2026-05-05 13:00:00.000000

users 테이블에 is_superadmin 플래그 추가.
- True: 모든 가맹본부의 simulation 이력(industry/brand 무관) 조회/삭제 가능
- False (기본): 본인 + 소속 매니저 데이터만 (기존 master 권한)

자동 시드는 절대 금지. 운영자가 직접 UPDATE 또는 scripts/seed_superadmin.py 사용.
"""

from typing import Union, Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a8f3d2e7c1b9"
down_revision: Union[str, Sequence[str], None] = "91b66e68ec18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_superadmin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="전체 가맹본부 simulation 데이터 조회 권한 (기본 false)",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "is_superadmin")
