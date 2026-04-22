"""add seoul_resident_pop_quarterly table

B2 요청 — 기존 mapo_resident_pop (마포 17 region × 24분기) 을 서울 전체 424
행정동 × 분기로 확장. 행안부 주민등록 월간 CSV 를 분기별로 변환 적재.

Revision ID: c5d8a7b1e4f2
Revises: a4f1e8d3c2b5
Create Date: 2026-04-20 17:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "c5d8a7b1e4f2"
down_revision: Union[str, Sequence[str], None] = "a4f1e8d3c2b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("seoul_resident_pop_quarterly", schema="public"):
        op.create_table(
            "seoul_resident_pop_quarterly",
            sa.Column("quarter", sa.Integer(), primary_key=True, comment="YYYYQ 분기"),
            sa.Column("dong_code", sa.String(10), primary_key=True, comment="행정동코드 8자리"),
            sa.Column("dong_name", sa.String(50), nullable=False, comment="행정동명"),
            sa.Column("resident_pop", sa.Integer(), comment="주민등록 인구 (분기 마지막 월 값)"),
        )
        op.create_index(
            "ix_seoul_resident_pop_q_dong",
            "seoul_resident_pop_quarterly",
            ["dong_code"],
        )


def downgrade() -> None:
    op.drop_index("ix_seoul_resident_pop_q_dong", table_name="seoul_resident_pop_quarterly")
    op.drop_table("seoul_resident_pop_quarterly")
