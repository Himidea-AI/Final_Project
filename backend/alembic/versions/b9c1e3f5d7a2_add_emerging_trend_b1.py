"""add emerging-trend B1 tables (subway/migration/ttareungi)

5 tables:
  - master_subway_station
  - master_ttareungi_station
  - seoul_subway_passenger_daily
  - seoul_dong_migration_monthly
  - seoul_ttareungi_usage_daily

spec: docs/superpowers/specs/2026-04-29-emerging-trend-data-b1-design.md

Revision ID: b9c1e3f5d7a2
Revises: a8b2c4d6e8f0
Create Date: 2026-04-29 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b9c1e3f5d7a2"
down_revision: Union[str, Sequence[str], None] = "a8b2c4d6e8f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "master_subway_station",
        sa.Column("station_code", sa.String(10), primary_key=True, comment="역코드 (운영사별 통합)"),
        sa.Column("station_name", sa.String(50), nullable=False, comment="역명"),
        sa.Column("line_name", sa.String(20), comment="호선/노선"),
        sa.Column("sigungu_code", sa.String(5), comment="자치구 코드 (마포=11440)"),
        sa.Column("lat", sa.Float, comment="위도"),
        sa.Column("lon", sa.Float, comment="경도"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        comment="담당: 찬영 | 서울 전체 지하철역 마스터 | 출처: 서울교통공사 + 국토부 좌표",
    )
    op.create_index("ix_master_subway_sigungu", "master_subway_station", ["sigungu_code"])

    op.create_table(
        "master_ttareungi_station",
        sa.Column("station_id", sa.String(20), primary_key=True, comment="대여소 ID"),
        sa.Column("station_name", sa.String(100), nullable=False, comment="대여소명"),
        sa.Column("sigungu_code", sa.String(5), comment="자치구 코드"),
        sa.Column(
            "dong_code",
            sa.String(8),
            sa.ForeignKey("seoul_dong_master.dong_code"),
            comment="행정동 코드 (8자리 FK)",
        ),
        sa.Column("lat", sa.Float, comment="위도"),
        sa.Column("lon", sa.Float, comment="경도"),
        sa.Column("opened_at", sa.Date, comment="개소일"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        comment="담당: 찬영 | 서울 전체 따릉이 대여소 마스터 | 출처: 서울 열린데이터광장",
    )
    op.create_index("ix_master_ttareungi_sigungu", "master_ttareungi_station", ["sigungu_code"])
    op.create_index("ix_master_ttareungi_dong", "master_ttareungi_station", ["dong_code"])

    op.create_table(
        "seoul_subway_passenger_daily",
        sa.Column("date", sa.Date, primary_key=True, comment="영업일"),
        sa.Column(
            "station_code",
            sa.String(10),
            sa.ForeignKey("master_subway_station.station_code"),
            primary_key=True,
            comment="역코드",
        ),
        sa.Column("boarding_cnt", sa.Integer, comment="승차 인원"),
        sa.Column("alighting_cnt", sa.Integer, comment="하차 인원"),
        comment="담당: 찬영 | 서울 전체 지하철 일별 승하차 | 출처: 서울교통공사",
    )
    op.create_index("ix_subway_passenger_station", "seoul_subway_passenger_daily", ["station_code"])

    op.create_table(
        "seoul_dong_migration_monthly",
        sa.Column("ym", sa.Integer, primary_key=True, comment="YYYYMM"),
        sa.Column(
            "dong_code",
            sa.String(8),
            sa.ForeignKey("seoul_dong_master.dong_code"),
            primary_key=True,
            comment="행정동 코드",
        ),
        sa.Column("move_in_cnt", sa.Integer, comment="전입 총수"),
        sa.Column("move_out_cnt", sa.Integer, comment="전출 총수"),
        sa.Column("net_move", sa.Integer, comment="순이동 (전입 - 전출)"),
        sa.Column("move_in_2030", sa.Integer, comment="20-30대 전입자 수"),
        sa.Column("move_out_2030", sa.Integer, comment="20-30대 전출자 수"),
        comment="담당: 찬영 | 서울 전체 동별 월간 전입/전출 | 출처: 행정안전부 주민등록 이동통계",
    )

    op.create_table(
        "seoul_ttareungi_usage_daily",
        sa.Column("date", sa.Date, primary_key=True, comment="이용일"),
        sa.Column(
            "station_id",
            sa.String(20),
            sa.ForeignKey("master_ttareungi_station.station_id"),
            primary_key=True,
            comment="대여소 ID",
        ),
        sa.Column("rent_cnt", sa.Integer, comment="대여 건수"),
        sa.Column("return_cnt", sa.Integer, comment="반납 건수"),
        comment="담당: 찬영 | 서울 전체 따릉이 일×대여소 집계 | 출처: 서울 열린데이터광장",
    )
    op.create_index("ix_ttareungi_usage_station", "seoul_ttareungi_usage_daily", ["station_id"])


def downgrade() -> None:
    op.drop_index("ix_ttareungi_usage_station", table_name="seoul_ttareungi_usage_daily")
    op.drop_table("seoul_ttareungi_usage_daily")

    op.drop_table("seoul_dong_migration_monthly")

    op.drop_index("ix_subway_passenger_station", table_name="seoul_subway_passenger_daily")
    op.drop_table("seoul_subway_passenger_daily")

    op.drop_index("ix_master_ttareungi_dong", table_name="master_ttareungi_station")
    op.drop_index("ix_master_ttareungi_sigungu", table_name="master_ttareungi_station")
    op.drop_table("master_ttareungi_station")

    op.drop_index("ix_master_subway_sigungu", table_name="master_subway_station")
    op.drop_table("master_subway_station")
