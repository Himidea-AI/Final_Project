"""merge heads: user_lifecycle + emerging_trend_b1

두 평행 head 를 단일 head 로 통합:
    c5e9a1f3d7b2 (users/manager_users 라이프사이클 컬럼 4종)
    b9c1e3f5d7a2 (emerging-trend B1 5 테이블)

두 마이그레이션은 서로 다른 객체를 다루므로 충돌 없음 — 순수 chain 통합용
no-op merge.

Revision ID: f1a2b3c4d5e6
Revises: c5e9a1f3d7b2, b9c1e3f5d7a2
Create Date: 2026-04-30 00:00:00.000000

"""

from typing import Sequence, Union


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = ("c5e9a1f3d7b2", "b9c1e3f5d7a2")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
