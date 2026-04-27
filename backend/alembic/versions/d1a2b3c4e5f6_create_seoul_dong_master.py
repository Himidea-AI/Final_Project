"""B-3.1: seoul_dong_master 신설 + union 적재 + dong_name 정규화

목적:
  - 서울 전체 ~425개 행정동의 마스터 테이블 신설 (8자리 코드)
  - 자식 테이블 distinct (dong_code, dong_name) union 적재
  - dong_name 인코딩 깨진 '?' → '·' (가운뎃점) 정규화

설계 결정:
  - dong_mapping (마포 16개, 운영용)은 보존
  - seoul_dong_master는 ML/학습 분석용 서울 전체 마스터
  - dong_mapping ⊂ seoul_dong_master (마포 코드는 양쪽 존재, 중복 OK)

데이터 source:
  - dong_mapping (16) + 자식 테이블 union (425)
  - seoul_population_quarterly의 외래 코드 6개도 포함 (dong_name NULL)

Revision ID: d1a2b3c4e5f6
Revises: c9d4e5f1a8b3
Create Date: 2026-04-25 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "d1a2b3c4e5f6"
down_revision: Union[str, Sequence[str], None] = "c9d4e5f1a8b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1단계: 마스터 테이블 신설
    op.execute("""
        CREATE TABLE IF NOT EXISTS seoul_dong_master (
            dong_code VARCHAR(8) PRIMARY KEY,
            dong_name TEXT,
            sgg_code  VARCHAR(5),
            comment   TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_seoul_dong_master_sgg
        ON seoul_dong_master (sgg_code)
    """)

    # 2단계: 데이터 적재 (효율화 — DISTINCT 먼저 + LEFT JOIN)
    # 큰 테이블(seoul_adstrd_stor 849k 등)은 SELECT DISTINCT로 먼저 축소
    # outer query에 서브쿼리 대신 LEFT JOIN + GROUP BY 사용
    op.execute("""
        WITH all_codes AS (
            SELECT DISTINCT dong_code FROM dong_mapping WHERE dong_code IS NOT NULL
            UNION SELECT DISTINCT dong_code FROM seoul_district_sales WHERE dong_code IS NOT NULL
            UNION SELECT DISTINCT dong_code FROM seoul_district_stores WHERE dong_code IS NOT NULL
            UNION SELECT DISTINCT dong_code FROM seoul_population_quarterly WHERE dong_code IS NOT NULL
            UNION SELECT DISTINCT dong_code FROM seoul_training_dataset WHERE dong_code IS NOT NULL
            UNION SELECT DISTINCT dong_code FROM seoul_golmok_rent WHERE dong_code IS NOT NULL
            UNION SELECT DISTINCT dong_code FROM district_sales_seoul WHERE dong_code IS NOT NULL
            UNION SELECT DISTINCT dong_code FROM seoul_adstrd_change_ix WHERE dong_code IS NOT NULL
            UNION SELECT DISTINCT dong_code FROM seoul_adstrd_flpop WHERE dong_code IS NOT NULL
            UNION SELECT DISTINCT dong_code FROM seoul_adstrd_stor WHERE dong_code IS NOT NULL
            UNION SELECT DISTINCT dong_code FROM seoul_adstrd_fclty WHERE dong_code IS NOT NULL
            UNION SELECT DISTINCT dong_code FROM dong_subway_access WHERE dong_code IS NOT NULL
            UNION SELECT DISTINCT dong_code FROM seoul_resident_pop_quarterly WHERE dong_code IS NOT NULL
        ),
        pair_pool AS (
            SELECT DISTINCT dong_code, REPLACE(dong_name, '?', '·') AS name
              FROM dong_mapping WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
            UNION SELECT DISTINCT dong_code, REPLACE(dong_name, '?', '·')
              FROM seoul_district_sales WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
            UNION SELECT DISTINCT dong_code, REPLACE(dong_name, '?', '·')
              FROM seoul_district_stores WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
            UNION SELECT DISTINCT dong_code, REPLACE(dong_name, '?', '·')
              FROM seoul_golmok_rent WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
            UNION SELECT DISTINCT dong_code, REPLACE(dong_name, '?', '·')
              FROM seoul_adstrd_change_ix WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
            UNION SELECT DISTINCT dong_code, REPLACE(dong_name, '?', '·')
              FROM seoul_adstrd_flpop WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
            UNION SELECT DISTINCT dong_code, REPLACE(dong_name, '?', '·')
              FROM seoul_adstrd_stor WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
            UNION SELECT DISTINCT dong_code, REPLACE(dong_name, '?', '·')
              FROM seoul_adstrd_fclty WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
        ),
        resolved AS (
            SELECT dong_code, MAX(name) AS dong_name
            FROM pair_pool
            GROUP BY dong_code
        )
        INSERT INTO seoul_dong_master (dong_code, dong_name, sgg_code)
        SELECT c.dong_code, r.dong_name, LEFT(c.dong_code, 5)
        FROM all_codes c
        LEFT JOIN resolved r USING (dong_code)
        ON CONFLICT (dong_code) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_seoul_dong_master_sgg")
    op.execute("DROP TABLE IF EXISTS seoul_dong_master")
