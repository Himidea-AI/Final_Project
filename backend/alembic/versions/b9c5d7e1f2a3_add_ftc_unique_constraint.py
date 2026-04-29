"""ftc_brand_franchise 테이블에 UNIQUE 제약 추가.

동일 (yr, corpNm, brandNm) 중복 INSERT 방지.
NULLS NOT DISTINCT로 NULL 값 중복도 차단 (PostgreSQL 15+).

Revision ID: b9c5d7e1f2a3
Revises: a8b2c4d6e8f0
Create Date: 2026-04-29 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "b9c5d7e1f2a3"
down_revision: Union[str, Sequence[str], None] = "a8b2c4d6e8f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE ftc_brand_franchise "
        "ADD CONSTRAINT uq_ftc_yr_corp_brand "
        'UNIQUE NULLS NOT DISTINCT (yr, "corpNm", "brandNm")'
    )


def downgrade() -> None:
    op.drop_constraint("uq_ftc_yr_corp_brand", "ftc_brand_franchise", type_="unique")
