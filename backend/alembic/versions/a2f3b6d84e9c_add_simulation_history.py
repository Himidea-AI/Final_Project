"""add simulation_history table

매니저가 시뮬 실행 후 [저장] 버튼 누르면 [매니저 × 고객 × 날짜] 로 이력 저장.
나중에 필터로 재열람.

- simulation_history 테이블 (manager_id × client_name × 시뮬 입력/결과 JSONB)
- pg_trgm extension (client_name 한글 부분 일치용)
- 인덱스 4개: 매니저, 고객명 trigram, 날짜 DESC, 매니저×날짜 복합
- 추가 인덱스: client_name btree (정확 일치 검색용), manager_id 단일 (ORM index=True)

Revision ID: a2f3b6d84e9c
Revises: 9c3e7f2a8b14
Create Date: 2026-04-22 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a2f3b6d84e9c"
down_revision: Union[str, Sequence[str], None] = "9c3e7f2a8b14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # pg_trgm extension (client_name 한글 부분일치 GIN 인덱스용)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    if sa.inspect(bind).has_table("simulation_history", schema="public"):
        return

    op.create_table(
        "simulation_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("manager_id", postgresql.UUID(as_uuid=True), nullable=False, comment="매니저 ID"),
        sa.Column("client_name", sa.String(100), nullable=False, comment="예비 가맹점주 이름"),
        sa.Column("district", sa.String(50), nullable=False, comment="출점 후보 행정동"),
        sa.Column("brand_name", sa.String(100), nullable=False, comment="브랜드명"),
        sa.Column("business_type", sa.String(50), nullable=True, comment="업종 (cafe/restaurant/convenience)"),
        sa.Column("scenario", postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment="시뮬 시나리오 파라미터"),
        sa.Column(
            "simulation_result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="시뮬 결과 전체 (8 agent + ABM + B2 ML 9개)",
        ),
        sa.Column("ai_verdict_summary", sa.Text(), nullable=True, comment="리스트 표시용 요약"),
        sa.Column("market_entry_signal", sa.String(10), nullable=True, comment="green|yellow|red"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # ORM Column(index=True) 자동 명명 규칙
    op.create_index("ix_simulation_history_manager_id", "simulation_history", ["manager_id"])

    # 명시 인덱스 4개 (강민 초안)
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


def downgrade() -> None:
    op.drop_index("idx_simhist_manager_created", table_name="simulation_history")
    op.drop_index("idx_simhist_created", table_name="simulation_history")
    op.drop_index("idx_simhist_client_trgm", table_name="simulation_history")
    op.drop_index("idx_simhist_client", table_name="simulation_history")
    op.drop_index("ix_simulation_history_manager_id", table_name="simulation_history")
    op.drop_table("simulation_history")
    # pg_trgm extension은 다른 테이블(customers future 등)이 쓸 수 있으므로 유지
