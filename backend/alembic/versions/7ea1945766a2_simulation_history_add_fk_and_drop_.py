"""simulation_history add FK and drop redundant indexes

변경사항:
  1. simulation_history.manager_id → manager_users(id) FK 추가 (ON DELETE CASCADE)
  2. 중복 인덱스 2개 제거:
     - idx_simhist_client (btree client_name) — idx_simhist_client_trgm 이 정확/부분일치 모두 커버
     - ix_simulation_history_manager_id (btree manager_id) — idx_simhist_manager_created 복합의
       leftmost prefix 로 이미 커버됨

Revision ID: 7ea1945766a2
Revises: 93cecfb0a772
Create Date: 2026-04-22 12:48:38.863211

"""

from typing import Sequence, Union

from alembic import op

revision: str = "7ea1945766a2"
down_revision: Union[str, Sequence[str], None] = "93cecfb0a772"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) FK 추가 (고아 레코드 방지, ON DELETE CASCADE)
    op.create_foreign_key(
        "fk_simhist_manager",
        "simulation_history",
        "manager_users",
        ["manager_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 2) 중복 인덱스 제거
    op.execute("DROP INDEX IF EXISTS idx_simhist_client")
    op.execute("DROP INDEX IF EXISTS ix_simulation_history_manager_id")


def downgrade() -> None:
    # 인덱스 복원
    op.create_index("ix_simulation_history_manager_id", "simulation_history", ["manager_id"])
    op.create_index("idx_simhist_client", "simulation_history", ["client_name"])

    # FK 제거
    op.drop_constraint("fk_simhist_manager", "simulation_history", type_="foreignkey")
