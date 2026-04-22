"""add simulation_history for manager-saved simulation records

Revision ID: a2f3b6d84e9c
Revises: 9c3e7f2a8b14
Create Date: 2026-04-22

- 매니저가 시뮬 결과에 "저장" 액션을 누를 때만 기록되는 히스토리 테이블.
- 자동 로깅 테이블(simulation_result)과 별개. manager_id + client_name 필수.
- JSONB로 scenario/simulation_result 전체 보존.
- pg_trgm 확장 + 고객명 trigram index로 부분 일치 검색 성능 확보.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a2f3b6d84e9c"
down_revision: Union[str, Sequence[str], None] = "9c3e7f2a8b14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "simulation_history",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            comment="히스토리 PK",
        ),
        sa.Column(
            "manager_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            index=True,
            comment="저장한 매니저 ID (manager_users.id 또는 users.id — 스키마 단순화를 위해 FK 안 걸음)",
        ),
        sa.Column(
            "client_name",
            sa.String(length=100),
            nullable=False,
            comment="예비 가맹점주(고객) 성함",
        ),
        sa.Column("district", sa.String(length=50), nullable=False, comment="대상 행정동"),
        sa.Column("brand_name", sa.String(length=100), nullable=False, comment="브랜드명"),
        sa.Column("business_type", sa.String(length=50), nullable=True, comment="업종"),
        sa.Column(
            "scenario",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="시뮬 입력 시나리오 (weather/weekend/rent_shock 등)",
        ),
        sa.Column(
            "simulation_result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="시뮬 결과 전체 (8 agent + ABM)",
        ),
        sa.Column(
            "ai_verdict_summary",
            sa.Text(),
            nullable=True,
            comment="리스트 표시용 요약 (예: 'YELLOW · 카페 포화')",
        ),
        sa.Column(
            "market_entry_signal",
            sa.String(length=10),
            nullable=True,
            comment="green|yellow|red",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=True,
        ),
    )

    op.create_index(
        "idx_simhist_client",
        "simulation_history",
        ["client_name"],
    )
    op.create_index(
        "idx_simhist_created",
        "simulation_history",
        [sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_simhist_manager_created",
        "simulation_history",
        ["manager_id", sa.text("created_at DESC")],
    )
    # client_name 부분 일치 검색 성능 — pg_trgm GIN index
    op.execute(
        "CREATE INDEX idx_simhist_client_trgm "
        "ON simulation_history USING gin (client_name gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_simhist_client_trgm")
    op.drop_index("idx_simhist_manager_created", table_name="simulation_history")
    op.drop_index("idx_simhist_created", table_name="simulation_history")
    op.drop_index("idx_simhist_client", table_name="simulation_history")
    op.drop_table("simulation_history")
    # pg_trgm은 다른 index에서도 쓰일 수 있어 DROP EXTENSION은 안 함
