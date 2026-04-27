"""B-3.3: jeonse_dong_master 신설 (법정동 10자리) + jeonse_monthly_rent FK

배경:
  - jeonse_monthly_rent는 국토부 전월세 신고 원본 데이터로 **법정동 10자리** 코드 사용
  - 다른 모든 테이블의 행정동 8자리와 별개 체계 (5번째 자리부터 다름)
  - LEFT(8) 변환 시 잘못된 코드 생성 → 별도 master 필요

설계:
  - jeonse_dong_master: dong_code VARCHAR(10) PK, dong_name, gu_code, gu_name
  - 데이터 source: jeonse_monthly_rent 자체 distinct (자체 union)
  - dong_name 정규화 ('?' → '·') — 다른 master와 동일 정책

Revision ID: f3c4d5e6a7b8
Revises: e2b3c4d5f6a7
Create Date: 2026-04-25 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "f3c4d5e6a7b8"
down_revision: Union[str, Sequence[str], None] = "e2b3c4d5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1단계: 법정동 마스터 테이블 신설
    op.execute("""
        CREATE TABLE IF NOT EXISTS jeonse_dong_master (
            dong_code  VARCHAR(10) PRIMARY KEY,
            dong_name  TEXT,
            gu_code    VARCHAR(5),
            gu_name    TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_jeonse_dong_master_gu
        ON jeonse_dong_master (gu_code)
    """)

    # 2단계: jeonse_monthly_rent의 distinct dong_code 적재 (정규화 포함)
    op.execute("""
        INSERT INTO jeonse_dong_master (dong_code, dong_name, gu_code, gu_name)
        SELECT
            dong_code,
            MAX(REPLACE(dong_name, '?', '·')) AS dong_name,
            MAX(gu_code) AS gu_code,
            MAX(gu_name) AS gu_name
        FROM jeonse_monthly_rent
        WHERE dong_code IS NOT NULL
        GROUP BY dong_code
        ON CONFLICT (dong_code) DO NOTHING
    """)

    # 3단계: FK 추가
    op.execute("""
        ALTER TABLE jeonse_monthly_rent
        ADD CONSTRAINT fk_jeonse_monthly_rent_dong
        FOREIGN KEY (dong_code) REFERENCES jeonse_dong_master (dong_code)
        ON UPDATE CASCADE
        ON DELETE NO ACTION
        NOT VALID
    """)
    op.execute("ALTER TABLE jeonse_monthly_rent VALIDATE CONSTRAINT fk_jeonse_monthly_rent_dong")


def downgrade() -> None:
    op.execute("ALTER TABLE jeonse_monthly_rent DROP CONSTRAINT IF EXISTS fk_jeonse_monthly_rent_dong")
    op.execute("DROP INDEX IF EXISTS idx_jeonse_dong_master_gu")
    op.execute("DROP TABLE IF EXISTS jeonse_dong_master")
