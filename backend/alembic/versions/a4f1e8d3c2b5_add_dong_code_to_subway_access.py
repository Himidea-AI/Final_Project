"""add dong_code column to dong_subway_access

서울 전체 확장을 위해 dong_code 추가. PK 는 기존 dong_name 유지 (B2/백엔드
호환). 마포 16건 → 서울 424건 재적재 예정.

Revision ID: a4f1e8d3c2b5
Revises: 9c3e7f2a8b14
Create Date: 2026-04-20 16:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a4f1e8d3c2b5"
down_revision: Union[str, Sequence[str], None] = "9c3e7f2a8b14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, col: str) -> bool:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(table, schema="public"):
        return False
    return any(c["name"] == col for c in sa.inspect(bind).get_columns(table, schema="public"))


def upgrade() -> None:
    if not _has_column("dong_subway_access", "dong_code"):
        op.add_column(
            "dong_subway_access",
            sa.Column("dong_code", sa.String(10), comment="행정동 코드 (seoul_district_sales 기준 8자리)"),
        )
        op.create_index("ix_dong_subway_access_dong_code", "dong_subway_access", ["dong_code"])


def downgrade() -> None:
    op.drop_index("ix_dong_subway_access_dong_code", table_name="dong_subway_access")
    op.drop_column("dong_subway_access", "dong_code")
