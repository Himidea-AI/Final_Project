"""add csv seed tables and is_approved column

13개 CSV 시드 테이블 추가 + manager_users.is_approved 컬럼 추가:
- golmok_rent, kakao_store, naver_vacancy (모델에 있었으나 migration 누락)
- brand_logo, cpi_dining_quarterly, golmok_sales, golmok_stores,
  mapo_resident_pop, seoul_district_sales, seoul_district_stores,
  seoul_golmok_rent, seoul_population_quarterly, seoul_training_dataset

Revision ID: b2d4e8f1c7a3
Revises: 013924594d95
Create Date: 2026-04-17 15:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2d4e8f1c7a3"
down_revision: Union[str, Sequence[str], None] = "013924594d95"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 기존 DB에 ad-hoc DDL로 일부 테이블/컬럼이 먼저 만들어져 있을 수 있으므로
# idempotent 하게 처리 (팀원별 DB 상태 차이 흡수)
def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return sa.inspect(bind).has_table(name, schema="public")


def _has_column(table: str, col: str) -> bool:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(table, schema="public"):
        return False
    cols = sa.inspect(bind).get_columns(table, schema="public")
    return any(c["name"] == col for c in cols)


def _maybe_create_table(name: str, *columns) -> None:
    """테이블이 이미 있으면 스킵 (ad-hoc DDL로 먼저 만들어진 경우 대응)."""
    if _has_table(name):
        print(f"[alembic] skip create_table (already exists): {name}")
        return
    op.create_table(name, *columns)


def _maybe_create_index(name: str, table: str, cols: list[str], unique: bool = False) -> None:
    """테이블 없거나 인덱스 이미 있으면 스킵."""
    bind = op.get_bind()
    if not _has_table(table):
        return
    existing = sa.inspect(bind).get_indexes(table, schema="public")
    if any(ix["name"] == name for ix in existing):
        return
    op.create_index(name, table, cols, unique=unique)


# 매출 테이블 공통 컬럼 (요일/시간대/성별/연령대) ----------------------------
def _sales_time_gender_age(int_type):
    """golmok_sales, seoul_district_sales 등 공통 매출 컬럼 생성."""
    return [
        sa.Column("weekday_sales", int_type, nullable=True),
        sa.Column("weekend_sales", int_type, nullable=True),
        sa.Column("mon_sales", int_type, nullable=True),
        sa.Column("tue_sales", int_type, nullable=True),
        sa.Column("wed_sales", int_type, nullable=True),
        sa.Column("thu_sales", int_type, nullable=True),
        sa.Column("fri_sales", int_type, nullable=True),
        sa.Column("sat_sales", int_type, nullable=True),
        sa.Column("sun_sales", int_type, nullable=True),
        sa.Column("time_00_06_sales", int_type, nullable=True),
        sa.Column("time_06_11_sales", int_type, nullable=True),
        sa.Column("time_11_14_sales", int_type, nullable=True),
        sa.Column("time_14_17_sales", int_type, nullable=True),
        sa.Column("time_17_21_sales", int_type, nullable=True),
        sa.Column("time_21_24_sales", int_type, nullable=True),
        sa.Column("male_sales", int_type, nullable=True),
        sa.Column("female_sales", int_type, nullable=True),
        sa.Column("age_10_sales", int_type, nullable=True),
        sa.Column("age_20_sales", int_type, nullable=True),
        sa.Column("age_30_sales", int_type, nullable=True),
        sa.Column("age_40_sales", int_type, nullable=True),
        sa.Column("age_50_sales", int_type, nullable=True),
        sa.Column("age_60_above_sales", int_type, nullable=True),
        sa.Column("weekday_count", int_type, nullable=True),
        sa.Column("weekend_count", int_type, nullable=True),
        sa.Column("mon_count", int_type, nullable=True),
        sa.Column("tue_count", int_type, nullable=True),
        sa.Column("wed_count", int_type, nullable=True),
        sa.Column("thu_count", int_type, nullable=True),
        sa.Column("fri_count", int_type, nullable=True),
        sa.Column("sat_count", int_type, nullable=True),
        sa.Column("sun_count", int_type, nullable=True),
        sa.Column("time_00_06_count", int_type, nullable=True),
        sa.Column("time_06_11_count", int_type, nullable=True),
        sa.Column("time_11_14_count", int_type, nullable=True),
        sa.Column("time_14_17_count", int_type, nullable=True),
        sa.Column("time_17_21_count", int_type, nullable=True),
        sa.Column("time_21_24_count", int_type, nullable=True),
        sa.Column("male_count", int_type, nullable=True),
        sa.Column("female_count", int_type, nullable=True),
        sa.Column("age_10_count", int_type, nullable=True),
        sa.Column("age_20_count", int_type, nullable=True),
        sa.Column("age_30_count", int_type, nullable=True),
        sa.Column("age_40_count", int_type, nullable=True),
        sa.Column("age_50_count", int_type, nullable=True),
        sa.Column("age_60_above_count", int_type, nullable=True),
    ]


def upgrade() -> None:
    # ---- manager_users.is_approved ----
    if not _has_column("manager_users", "is_approved"):
        op.add_column(
            "manager_users",
            sa.Column(
                "is_approved",
                sa.Boolean(),
                nullable=True,
                server_default=sa.text("false"),
                comment="팀장 승인 여부",
            ),
        )

    # ---- simulation_result.workspace_id ----
    if not _has_column("simulation_result", "workspace_id"):
        op.add_column(
            "simulation_result",
            sa.Column(
                "workspace_id",
                sa.String(length=100),
                nullable=True,
                comment="워크스페이스 ID (멀티테넌시)",
            ),
        )
        _maybe_create_index(
            "ix_simulation_result_workspace",
            "simulation_result",
            ["workspace_id"],
            unique=False,
        )

    # ---- golmok_rent ----
    _maybe_create_table(
        "golmok_rent",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="자동증가 PK"),
        sa.Column("year", sa.SmallInteger(), nullable=True, comment="기준 연도"),
        sa.Column("quarter", sa.SmallInteger(), nullable=True, comment="기준 분기"),
        sa.Column("dong_code", sa.String(length=10), nullable=True, comment="행정동코드"),
        sa.Column("dong_name", sa.String(length=20), nullable=True, comment="행정동명"),
        sa.Column("gubun", sa.String(length=10), nullable=True, comment="구분 (gu/dong)"),
        sa.Column("rent_1f", sa.Integer(), nullable=True, comment="1층 환산임대료 (원/3.3㎡)"),
        sa.Column("rent_other", sa.Integer(), nullable=True, comment="1층 외 환산임대료"),
        sa.Column("rent_total", sa.Integer(), nullable=True, comment="전체 환산임대료"),
        sa.PrimaryKeyConstraint("id"),
    )
    _maybe_create_index("ix_golmok_rent_year", "golmok_rent", ["year"], unique=False)
    _maybe_create_index("ix_golmok_rent_dong_code", "golmok_rent", ["dong_code"], unique=False)

    # ---- kakao_store ----
    _maybe_create_table(
        "kakao_store",
        sa.Column("kakao_id", sa.String(length=20), nullable=False, comment="카카오 장소 ID"),
        sa.Column("place_name", sa.String(length=200), nullable=True),
        sa.Column("brand_name", sa.String(length=100), nullable=True),
        sa.Column("category", sa.String(length=30), nullable=True),
        sa.Column("category_detail", sa.String(length=200), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("road_address", sa.Text(), nullable=True),
        sa.Column("dong_name", sa.String(length=20), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("place_url", sa.Text(), nullable=True),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("kakao_id"),
    )
    _maybe_create_index("ix_kakao_store_brand_name", "kakao_store", ["brand_name"], unique=False)
    _maybe_create_index("ix_kakao_store_category", "kakao_store", ["category"], unique=False)
    _maybe_create_index("ix_kakao_store_dong_name", "kakao_store", ["dong_name"], unique=False)

    # ---- naver_vacancy ----
    _maybe_create_table(
        "naver_vacancy",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("trade_type", sa.String(length=10), nullable=True),
        sa.Column("trade_code", sa.String(length=5), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column("listing_count", sa.Integer(), nullable=True),
        sa.Column("dong_name", sa.String(length=20), nullable=True),
        sa.Column("lgeo", sa.String(length=30), nullable=True),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    _maybe_create_index("ix_naver_vacancy_dong", "naver_vacancy", ["dong_name"], unique=False)
    _maybe_create_index("ix_naver_vacancy_trade", "naver_vacancy", ["trade_type"], unique=False)

    # ---- brand_logo ----
    _maybe_create_table(
        "brand_logo",
        sa.Column("brand_name", sa.String(length=100), nullable=False, comment="브랜드명"),
        sa.Column("domain", sa.String(length=100), nullable=True),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("logo_source", sa.String(length=30), nullable=True),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("brand_name"),
    )

    # ---- cpi_dining_quarterly ----
    _maybe_create_table(
        "cpi_dining_quarterly",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("quarter", sa.BigInteger(), nullable=True),
        sa.Column("cpi_index", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # ---- golmok_sales ----
    _maybe_create_table(
        "golmok_sales",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("quarter", sa.BigInteger(), nullable=True),
        sa.Column("trdar_code", sa.Text(), nullable=True),
        sa.Column("industry_code", sa.Text(), nullable=True),
        sa.Column("monthly_sales", sa.BigInteger(), nullable=True),
        sa.Column("monthly_count", sa.BigInteger(), nullable=True),
        *_sales_time_gender_age(sa.BigInteger()),
        sa.PrimaryKeyConstraint("id"),
    )
    _maybe_create_index("ix_golmok_sales_quarter", "golmok_sales", ["quarter"], unique=False)
    _maybe_create_index("ix_golmok_sales_trdar_code", "golmok_sales", ["trdar_code"], unique=False)

    # ---- golmok_stores ----
    _maybe_create_table(
        "golmok_stores",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("quarter", sa.BigInteger(), nullable=True),
        sa.Column("trdar_code", sa.Text(), nullable=True),
        sa.Column("industry_code", sa.Text(), nullable=True),
        sa.Column("store_count", sa.BigInteger(), nullable=True),
        sa.Column("similar_store_count", sa.BigInteger(), nullable=True),
        sa.Column("open_rate", sa.BigInteger(), nullable=True),
        sa.Column("open_count", sa.BigInteger(), nullable=True),
        sa.Column("close_rate", sa.BigInteger(), nullable=True),
        sa.Column("close_count", sa.BigInteger(), nullable=True),
        sa.Column("franchise_count", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    _maybe_create_index("ix_golmok_stores_quarter", "golmok_stores", ["quarter"], unique=False)
    _maybe_create_index("ix_golmok_stores_trdar_code", "golmok_stores", ["trdar_code"], unique=False)

    # ---- mapo_resident_pop ----
    _maybe_create_table(
        "mapo_resident_pop",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("quarter", sa.BigInteger(), nullable=True),
        sa.Column("dong_code", sa.Text(), nullable=True),
        sa.Column("dong_name", sa.Text(), nullable=True),
        sa.Column("resident_pop", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    _maybe_create_index("ix_mapo_resident_pop_quarter", "mapo_resident_pop", ["quarter"], unique=False)
    _maybe_create_index("ix_mapo_resident_pop_dong_code", "mapo_resident_pop", ["dong_code"], unique=False)

    # ---- seoul_district_sales ----
    _maybe_create_table(
        "seoul_district_sales",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("quarter", sa.BigInteger(), nullable=True),
        sa.Column("dong_code", sa.Text(), nullable=True),
        sa.Column("dong_name", sa.Text(), nullable=True),
        sa.Column("industry_code", sa.Text(), nullable=True),
        sa.Column("industry_name", sa.Text(), nullable=True),
        sa.Column("monthly_sales", sa.BigInteger(), nullable=True),
        sa.Column("monthly_count", sa.BigInteger(), nullable=True),
        *_sales_time_gender_age(sa.BigInteger()),
        sa.PrimaryKeyConstraint("id"),
    )
    _maybe_create_index("ix_seoul_district_sales_quarter", "seoul_district_sales", ["quarter"], unique=False)
    _maybe_create_index("ix_seoul_district_sales_dong_code", "seoul_district_sales", ["dong_code"], unique=False)

    # ---- seoul_district_stores ----
    _maybe_create_table(
        "seoul_district_stores",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("quarter", sa.BigInteger(), nullable=True),
        sa.Column("dong_code", sa.Text(), nullable=True),
        sa.Column("dong_name", sa.Text(), nullable=True),
        sa.Column("industry_code", sa.Text(), nullable=True),
        sa.Column("industry_name", sa.Text(), nullable=True),
        sa.Column("store_count", sa.BigInteger(), nullable=True),
        sa.Column("similar_store_count", sa.BigInteger(), nullable=True),
        sa.Column("open_count", sa.BigInteger(), nullable=True),
        sa.Column("close_count", sa.BigInteger(), nullable=True),
        sa.Column("franchise_count", sa.BigInteger(), nullable=True),
        sa.Column("closure_rate", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    _maybe_create_index("ix_seoul_district_stores_quarter", "seoul_district_stores", ["quarter"], unique=False)
    _maybe_create_index("ix_seoul_district_stores_dong_code", "seoul_district_stores", ["dong_code"], unique=False)

    # ---- seoul_golmok_rent ----
    _maybe_create_table(
        "seoul_golmok_rent",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("year", sa.BigInteger(), nullable=True),
        sa.Column("quarter", sa.BigInteger(), nullable=True),
        sa.Column("dong_code", sa.Text(), nullable=True),
        sa.Column("dong_name", sa.Text(), nullable=True),
        sa.Column("gubun", sa.Text(), nullable=True),
        sa.Column("rent_1f", sa.Float(), nullable=True),
        sa.Column("rent_other", sa.Float(), nullable=True),
        sa.Column("rent_total", sa.Float(), nullable=True),
        sa.Column("quarter_code", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    _maybe_create_index("ix_seoul_golmok_rent_year", "seoul_golmok_rent", ["year"], unique=False)
    _maybe_create_index("ix_seoul_golmok_rent_dong_code", "seoul_golmok_rent", ["dong_code"], unique=False)

    # ---- seoul_population_quarterly ----
    _maybe_create_table(
        "seoul_population_quarterly",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("quarter", sa.BigInteger(), nullable=True),
        sa.Column("dong_code", sa.Text(), nullable=True),
        sa.Column("total_pop", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    _maybe_create_index(
        "ix_seoul_population_quarterly_quarter",
        "seoul_population_quarterly",
        ["quarter"],
        unique=False,
    )
    _maybe_create_index(
        "ix_seoul_population_quarterly_dong_code",
        "seoul_population_quarterly",
        ["dong_code"],
        unique=False,
    )

    # ---- seoul_training_dataset ----
    _maybe_create_table(
        "seoul_training_dataset",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("quarter", sa.BigInteger(), nullable=True),
        sa.Column("dong_code", sa.Text(), nullable=True),
        sa.Column("dong_name", sa.Text(), nullable=True),
        sa.Column("industry_code", sa.Text(), nullable=True),
        sa.Column("industry_name", sa.Text(), nullable=True),
        sa.Column("monthly_sales", sa.BigInteger(), nullable=True),
        sa.Column("monthly_count", sa.BigInteger(), nullable=True),
        sa.Column("store_count", sa.BigInteger(), nullable=True),
        sa.Column("open_count", sa.BigInteger(), nullable=True),
        sa.Column("close_count", sa.BigInteger(), nullable=True),
        sa.Column("total_pop", sa.Float(), nullable=True),
        sa.Column("cpi_index", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    _maybe_create_index(
        "ix_seoul_training_dataset_quarter",
        "seoul_training_dataset",
        ["quarter"],
        unique=False,
    )
    _maybe_create_index(
        "ix_seoul_training_dataset_dong_code",
        "seoul_training_dataset",
        ["dong_code"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("seoul_training_dataset")
    op.drop_table("seoul_population_quarterly")
    op.drop_table("seoul_golmok_rent")
    op.drop_table("seoul_district_stores")
    op.drop_table("seoul_district_sales")
    op.drop_table("mapo_resident_pop")
    op.drop_table("golmok_stores")
    op.drop_table("golmok_sales")
    op.drop_table("cpi_dining_quarterly")
    op.drop_table("brand_logo")
    op.drop_table("naver_vacancy")
    op.drop_table("kakao_store")
    op.drop_table("golmok_rent")
    op.drop_index("ix_simulation_result_workspace", table_name="simulation_result")
    op.drop_column("simulation_result", "workspace_id")
    op.drop_column("manager_users", "is_approved")


# lint: postgresql 모듈은 향후 FK/UUID 추가 대비용으로 import 유지
_ = postgresql
