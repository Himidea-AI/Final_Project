"""fix simulation_history FK: drop manager_users FK, add user_type column

변경사항:
  1. simulation_history.manager_id → manager_users(id) FK 제거
     (팀장은 users 테이블에 있어 FK 위반 발생하던 문제 해결)
  2. user_type 컬럼 추가 (기본값 'manager') — 팀장/매니저 구분용
  3. 기존 레코드 호환: 기존 데이터는 모두 manager_users 소속이므로 'manager'로 채움

Revision ID: a3b4c5d6e7f8
Revises: 7ea1945766a2
Create Date: 2026-04-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "7ea1945766a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) manager_users FK 제약 제거 — 팀장(users 테이블) ID 허용
    op.drop_constraint("fk_simhist_manager", "simulation_history", type_="foreignkey")

    # 2) user_type 컬럼 추가 ('master' | 'manager'), 기존 레코드는 'manager'
    op.add_column(
        "simulation_history",
        sa.Column(
            "user_type",
            sa.String(10),
            nullable=False,
            server_default="manager",
            comment="사용자 유형 (master=팀장/users, manager=매니저/manager_users)",
        ),
    )


def downgrade() -> None:
    # user_type 컬럼 제거
    op.drop_column("simulation_history", "user_type")

    # FK 복원 (팀장 이력이 있다면 downgrade 시 FK 오류 가능 — 주의)
    op.create_foreign_key(
        "fk_simhist_manager",
        "simulation_history",
        "manager_users",
        ["manager_id"],
        ["id"],
        ondelete="CASCADE",
    )
