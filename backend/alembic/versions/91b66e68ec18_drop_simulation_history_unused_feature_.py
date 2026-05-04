"""drop simulation_history (unused feature cleanup)

simulation_history 는 ORM/Pydantic schema/test 만 작성되고 service 레이어
(`simulation_history_service.py`) 와 router 가 미구현 상태로 방치됨.
이력 저장 기능은 `simulation_ai`/`simulation_foresee` 로 대체됨.

추후 필요 시 새 마이그레이션으로 재생성. 현재 phantom DDL 정리 차원.

Revision ID: 91b66e68ec18
Revises: a04d71f50d19
Create Date: 2026-05-04 20:58:54.627693
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "91b66e68ec18"
down_revision: Union[str, Sequence[str], None] = "a04d71f50d19"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop simulation_history 테이블 + 인덱스 5개. pg_trgm extension 은 유지 (다른 테이블 잠재 사용)."""
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("simulation_history", schema="public"):
        return

    op.drop_index("idx_simhist_manager_created", table_name="simulation_history")
    op.drop_index("idx_simhist_created", table_name="simulation_history")
    op.drop_index("idx_simhist_client_trgm", table_name="simulation_history")
    op.drop_index("idx_simhist_client", table_name="simulation_history")
    op.drop_index("ix_simulation_history_manager_id", table_name="simulation_history")
    op.drop_table("simulation_history")


def downgrade() -> None:
    """재생성 — a2f3b6d84e9c 마이그레이션 정의와 동일 스키마."""
    bind = op.get_bind()
    if sa.inspect(bind).has_table("simulation_history", schema="public"):
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table(
        "simulation_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("manager_id", postgresql.UUID(as_uuid=True), nullable=False, comment="매니저 ID"),
        sa.Column("client_name", sa.String(100), nullable=False, comment="예비 가맹점주 이름"),
        sa.Column("district", sa.String(50), nullable=False, comment="출점 후보 행정동"),
        sa.Column("brand_name", sa.String(100), nullable=False, comment="브랜드명"),
        sa.Column("business_type", sa.String(50), nullable=True, comment="업종 (cafe/restaurant/convenience)"),
        sa.Column("scenario", postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment="시뮬 시나리오"),
        sa.Column(
            "simulation_result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="시뮬 결과 전체",
        ),
        sa.Column("ai_verdict_summary", sa.Text(), nullable=True, comment="AI 판정 요약"),
        sa.Column("market_entry_signal", sa.String(10), nullable=True, comment="green|yellow|red"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_simulation_history_manager_id", "simulation_history", ["manager_id"])
    op.create_index("idx_simhist_client", "simulation_history", ["client_name"])
    op.create_index(
        "idx_simhist_client_trgm",
        "simulation_history",
        ["client_name"],
        postgresql_using="gin",
        postgresql_ops={"client_name": "gin_trgm_ops"},
    )
    op.create_index("idx_simhist_created", "simulation_history", [sa.text("created_at DESC")])
    op.create_index(
        "idx_simhist_manager_created",
        "simulation_history",
        ["manager_id", sa.text("created_at DESC")],
    )
