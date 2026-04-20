"""add kakao_store_menu table

panel3 응답의 menu.menus.items[] 를 저장. 점포당 여러 메뉴 → 1:N 관계.

Revision ID: 9c3e7f2a8b14
Revises: 7a2b9e4d6f18
Create Date: 2026-04-20 15:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "9c3e7f2a8b14"
down_revision: Union[str, Sequence[str], None] = "7a2b9e4d6f18"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("kakao_store_menu", schema="public"):
        op.create_table(
            "kakao_store_menu",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "kakao_id",
                sa.String(20),
                sa.ForeignKey("kakao_store.kakao_id", ondelete="CASCADE"),
                nullable=False,
                comment="점포 FK",
            ),
            sa.Column("product_id", sa.Integer(), comment="카카오 내부 메뉴 ID"),
            sa.Column("menu_name", sa.Text(), nullable=False, comment="메뉴명"),
            sa.Column("price", sa.Integer(), comment="가격(원)"),
            sa.Column("description", sa.Text(), comment="메뉴 설명"),
            sa.Column("photo_url", sa.Text(), comment="사진 URL"),
            sa.Column("mod_at", sa.DateTime(), comment="카카오 측 최종 수정일"),
            sa.Column(
                "collected_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                comment="수집 일시",
            ),
            sa.UniqueConstraint("kakao_id", "product_id", name="uq_kakao_menu_store_product"),
        )
        op.create_index("ix_kakao_menu_kakao_id", "kakao_store_menu", ["kakao_id"])
        op.create_index("ix_kakao_menu_price", "kakao_store_menu", ["price"])


def downgrade() -> None:
    op.drop_index("ix_kakao_menu_price", table_name="kakao_store_menu")
    op.drop_index("ix_kakao_menu_kakao_id", table_name="kakao_store_menu")
    op.drop_table("kakao_store_menu")
