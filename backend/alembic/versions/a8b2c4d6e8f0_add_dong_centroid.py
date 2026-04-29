"""dong_centroid 테이블 신설 + 마포 16동 좌표 적재.

목적:
  - commercial_intelligence.get_dong_centroid 가 매번 store_info 평균 query
    하지 않도록 dedicated 테이블 분리 (lru_cache 의 영구 storage 화)
  - 추후 Kakao Geocoding API 호출 시 같은 테이블 update 가능

설계:
  - 마포 16동만 우선 적재 (store_info 평균 lat/lon)
  - source 컬럼으로 출처 추적 (현재: store_info_avg, 향후: kakao_api)
  - extension 가능 — 서울 전체 425동도 같은 방식

Revision ID: a8b2c4d6e8f0
Revises: f6ec0ac9d88c
Create Date: 2026-04-27 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "a8b2c4d6e8f0"
# 2026-04-29: down_revision을 FK 작업 chain head(f3c4d5e6a7b8 = B-3.3)로 정정.
# 원래 값 "f6ec0ac9d88c"는 FK 작업 시작 전 지점이라 multiple heads 충돌 발생.
down_revision: Union[str, Sequence[str], None] = "f3c4d5e6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS dong_centroid (
            dong_code  VARCHAR(8) PRIMARY KEY,
            dong_name  TEXT,
            lat        DOUBLE PRECISION NOT NULL,
            lon        DOUBLE PRECISION NOT NULL,
            source     VARCHAR(32) NOT NULL DEFAULT 'store_info_avg',
            n_stores   INTEGER,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """
    )

    # 마포 16동 적재 — store_info 평균 좌표
    op.execute(
        """
        INSERT INTO dong_centroid (dong_code, dong_name, lat, lon, source, n_stores)
        SELECT
            si.dong_code,
            COALESCE(sdm.dong_name, si.dong_name) AS dong_name,
            AVG(si.lat)::DOUBLE PRECISION,
            AVG(si.lon)::DOUBLE PRECISION,
            'store_info_avg',
            COUNT(*)::INTEGER
        FROM store_info si
        LEFT JOIN seoul_dong_master sdm ON sdm.dong_code = si.dong_code
        WHERE si.dong_code LIKE '11440%'
          AND si.lat IS NOT NULL
          AND si.lon IS NOT NULL
        GROUP BY si.dong_code, COALESCE(sdm.dong_name, si.dong_name)
        ON CONFLICT (dong_code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS dong_centroid")
