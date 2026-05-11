"""add simulation_abm table

Revision ID: aa13d6029c4f
Revises: a8f3d2e7c1b9
Create Date: 2026-05-09 00:00:00.000000

ABM(Agent-Based Model) 시뮬 영구 저장 테이블 신설.
- /simulate-abm/{job_id}/result 응답을 그대로 result JSONB 에 저장.
- 시나리오 (weather_override / weekend_force / rent_shock_pct / date_override / store_area)
  는 scenario JSONB 에 저장.
- 인덱스: (manager_id, created_at) — 매니저별 최신 정렬 list.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "aa13d6029c4f"
down_revision: Union[str, Sequence[str], None] = "a8f3d2e7c1b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "simulation_abm",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "manager_id",
            UUID(as_uuid=True),
            nullable=False,
            comment="작성자 ID — master면 users.id, manager면 manager_users.id",
        ),
        sa.Column(
            "user_type",
            sa.String(10),
            server_default="manager",
            comment="master | manager",
        ),
        sa.Column(
            "client_name",
            sa.String(100),
            nullable=False,
            comment="예비 가맹점주 이름",
        ),
        sa.Column("brand_name", sa.String(100), nullable=False, comment="브랜드명"),
        sa.Column("business_type", sa.String(50), comment="업종 (cafe/restaurant/...)"),
        sa.Column("target_district", sa.String(50), comment="대상 동"),
        sa.Column("spot_lat", sa.Float, comment="후보 공실 위도"),
        sa.Column("spot_lon", sa.Float, comment="후보 공실 경도"),
        sa.Column("n_agents", sa.Integer, comment="에이전트 수 (default 5000)"),
        sa.Column("days", sa.Integer, comment="시뮬 일수 (default 1)"),
        sa.Column(
            "scenario",
            JSONB,
            comment=(
                "ABM 시나리오 파라미터 — weather_override / weekend_force / rent_shock_pct / date_override / store_area"
            ),
        ),
        sa.Column(
            "result",
            JSONB,
            comment=(
                "/simulate-abm/{job_id}/result 응답 그대로 — dong_totals / "
                "cannibalization / peak_hours / new_store_* / narrator_summary 등"
            ),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        comment="담당: 봉환 | ABM 시뮬 결과 이력 | 5K agent 행동 시뮬",
    )
    op.create_index(
        "idx_abm_manager_created",
        "simulation_abm",
        ["manager_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_abm_manager_created", table_name="simulation_abm")
    op.drop_table("simulation_abm")
