"""add ftc_brand_franchise table

Revision ID: d4e5f6a7b8c9
Revises: c3c01b64fb39
Create Date: 2026-04-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3c01b64fb39"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ftc_brand_franchise",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="자동증가 PK"),
        sa.Column("yr", sa.SmallInteger(), nullable=True, comment="기준 연도"),
        sa.Column("corpNm", sa.String(length=200), nullable=True, comment="법인명 (기업명)"),
        sa.Column("brandNm", sa.String(length=200), nullable=True, comment="브랜드명"),
        sa.Column("indutyLclasNm", sa.String(length=50), nullable=True, comment="업종 대분류명"),
        sa.Column("indutyMlsfcNm", sa.String(length=50), nullable=True, comment="업종 중분류명"),
        sa.Column("frcsCnt", sa.Integer(), nullable=True, comment="가맹점 수"),
        sa.Column("newFrcsRgsCnt", sa.Integer(), nullable=True, comment="신규 가맹점 등록 수"),
        sa.Column("ctrtEndCnt", sa.Integer(), nullable=True, comment="계약 종료 수"),
        sa.Column("ctrtCncltnCnt", sa.Integer(), nullable=True, comment="계약 해지 수"),
        sa.Column("nmChgCnt", sa.Integer(), nullable=True, comment="명칭 변경 수"),
        sa.Column("avrgSlsAmt", sa.BigInteger(), nullable=True, comment="평균 매출액 (천원)"),
        sa.Column("arUnitAvrgSlsAmt", sa.BigInteger(), nullable=True, comment="면적당 평균 매출액"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ftc_brand_franchise_yr"), "ftc_brand_franchise", ["yr"], unique=False)
    op.create_index(op.f("ix_ftc_brand_franchise_brandNm"), "ftc_brand_franchise", ["brandNm"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ftc_brand_franchise_brandNm"), table_name="ftc_brand_franchise")
    op.drop_index(op.f("ix_ftc_brand_franchise_yr"), table_name="ftc_brand_franchise")
    op.drop_table("ftc_brand_franchise")
