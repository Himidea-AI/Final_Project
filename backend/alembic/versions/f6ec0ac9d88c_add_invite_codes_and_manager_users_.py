"""add invite_codes and manager_users tables

Revision ID: f6ec0ac9d88c
Revises: e5f6a7b8c9d0
Create Date: 2026-04-14 06:29:08.290769

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f6ec0ac9d88c"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "invite_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="자동증가 PK"),
        sa.Column("code", sa.String(length=20), nullable=False, comment="초대코드 (8자리)"),
        sa.Column("owner_id", sa.UUID(), nullable=False, comment="발급한 팀장 ID"),
        sa.Column("max_uses", sa.Integer(), nullable=True, comment="최대 사용 가능 횟수"),
        sa.Column("used_count", sa.Integer(), nullable=True, comment="현재 사용된 횟수"),
        sa.Column("is_active", sa.Boolean(), nullable=True, comment="활성 여부"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True, comment="발급 일시"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True, comment="만료 일시 (NULL이면 무제한)"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_invite_codes_code"), "invite_codes", ["code"], unique=True)

    op.create_table(
        "manager_users",
        sa.Column("id", sa.UUID(), nullable=False, comment="매니저 고유 ID (UUID v4)"),
        sa.Column("owner_id", sa.UUID(), nullable=False, comment="소속 팀장 ID"),
        sa.Column("invite_code_id", sa.Integer(), nullable=True, comment="사용한 초대코드 ID"),
        sa.Column("contact_name", sa.String(length=50), nullable=False, comment="매니저 이름"),
        sa.Column("position", sa.String(length=50), nullable=True, comment="직책"),
        sa.Column("email", sa.String(length=100), nullable=False, comment="이메일"),
        sa.Column("phone", sa.String(length=20), nullable=False, comment="연락처"),
        sa.Column("password_hash", sa.String(length=255), nullable=False, comment="비밀번호 해시"),
        sa.Column("is_active", sa.Boolean(), nullable=True, comment="활성 여부"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True, comment="가입 일시"),
        sa.ForeignKeyConstraint(["invite_code_id"], ["invite_codes.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_manager_users_email"), "manager_users", ["email"], unique=False)
    op.create_index(op.f("ix_manager_users_owner_id"), "manager_users", ["owner_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_manager_users_owner_id"), table_name="manager_users")
    op.drop_index(op.f("ix_manager_users_email"), table_name="manager_users")
    op.drop_table("manager_users")
    op.drop_index(op.f("ix_invite_codes_code"), table_name="invite_codes")
    op.drop_table("invite_codes")
