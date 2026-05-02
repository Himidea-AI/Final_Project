"""mapo_schools 테이블 신설 — 학교환경위생정화구역 거리 계산용.

목적:
  - 학교보건법 제6조에 따른 절대정화구역(50m) / 상대정화구역(200m) 룰을
    legal 룰엔진(rule_school_zone)에서 결정적으로 평가
  - 카카오 Local API로 마포 16동 centroid 반경 검색 결과를 적재 (UPSERT)
  - (name, lat, lon) UNIQUE 로 카카오/수동 입력 모두 idempotent

설계:
  - 마포 16동 우선 적재 (district 컬럼 = 행정동명)
  - 추후 서울 전체 425동도 동일 스키마 확장 가능
  - source 추적은 fetched_at + (선택) 추가 컬럼으로 향후 확장

Revision ID: d4f1a2b3c5e6
Revises: cc33dd44ee55
Create Date: 2026-05-02 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "d4f1a2b3c5e6"
down_revision: Union[str, Sequence[str], None] = "cc33dd44ee55"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS mapo_schools (
            id          SERIAL PRIMARY KEY,
            name        VARCHAR(200) NOT NULL,
            school_type VARCHAR(50),
            address     TEXT,
            lat         DOUBLE PRECISION NOT NULL,
            lon         DOUBLE PRECISION NOT NULL,
            district    VARCHAR(50),
            fetched_at  TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_mapo_schools_name_lat_lon UNIQUE (name, lat, lon)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_mapo_schools_district "
        "ON mapo_schools(district)"
    )
    op.execute(
        "COMMENT ON TABLE mapo_schools IS "
        "'담당: A1 | 마포구 학교 위치 (학교환경위생정화구역 거리 계산용) "
        "| 출처: kakao Local API'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_mapo_schools_district")
    op.execute("DROP TABLE IF EXISTS mapo_schools")
