"""B-3.2: 그룹 B/C 11개 테이블 → seoul_dong_master FK 추가

대상:
  TEXT 컬럼:
    1. seoul_district_sales
    2. seoul_district_stores
    3. seoul_population_quarterly
    4. seoul_training_dataset
    5. seoul_golmok_rent
  VARCHAR(15):
    6. district_sales_seoul
    7. seoul_adstrd_change_ix
    8. seoul_adstrd_flpop
    9. seoul_adstrd_stor (849k 행 — VALIDATE 시간 소요 가능)
  VARCHAR(10):
    10. dong_subway_access
    11. seoul_resident_pop_quarterly

설계:
  - 모두 seoul_dong_master(dong_code) 참조 (8자리, dong_mapping 별개)
  - ON UPDATE CASCADE / ON DELETE NO ACTION (그룹 A/B-2와 동일)
  - NOT VALID + VALIDATE 패턴
  - PostgreSQL string family 호환 — TEXT/VARCHAR(15)/VARCHAR(10) 모두 VARCHAR(8) PK 참조 가능

선결 조건:
  ✅ seoul_dong_master 신설 + 적재 완료 (B-3.1, d1a2b3c4e5f6)
  ✅ 모든 자식 테이블 distinct dong_code가 master에 포함됨 (audit 검증)

Revision ID: e2b3c4d5f6a7
Revises: d1a2b3c4e5f6
Create Date: 2026-04-25 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "e2b3c4d5f6a7"
down_revision: Union[str, Sequence[str], None] = "d1a2b3c4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_FK_TARGETS: list[tuple[str, str, str]] = [
    ("fk_seoul_district_sales_dong", "seoul_district_sales", "dong_code"),
    ("fk_seoul_district_stores_dong", "seoul_district_stores", "dong_code"),
    ("fk_seoul_population_quarterly_dong", "seoul_population_quarterly", "dong_code"),
    ("fk_seoul_training_dataset_dong", "seoul_training_dataset", "dong_code"),
    ("fk_seoul_golmok_rent_dong", "seoul_golmok_rent", "dong_code"),
    ("fk_district_sales_seoul_dong", "district_sales_seoul", "dong_code"),
    ("fk_seoul_adstrd_change_ix_dong", "seoul_adstrd_change_ix", "dong_code"),
    ("fk_seoul_adstrd_flpop_dong", "seoul_adstrd_flpop", "dong_code"),
    ("fk_seoul_adstrd_stor_dong", "seoul_adstrd_stor", "dong_code"),
    ("fk_dong_subway_access_dong", "dong_subway_access", "dong_code"),
    ("fk_seoul_resident_pop_quarterly_dong", "seoul_resident_pop_quarterly", "dong_code"),
]


def upgrade() -> None:
    # 1단계: NOT VALID로 FK 추가
    for fk_name, child_table, child_column in _FK_TARGETS:
        op.execute(
            f"""
            ALTER TABLE {child_table}
            ADD CONSTRAINT {fk_name}
            FOREIGN KEY ({child_column})
            REFERENCES seoul_dong_master (dong_code)
            ON UPDATE CASCADE
            ON DELETE NO ACTION
            NOT VALID
            """
        )

    # 2단계: VALIDATE (seoul_adstrd_stor 849k는 시간 좀 걸림, SHARE 락)
    for fk_name, child_table, _ in _FK_TARGETS:
        op.execute(f"ALTER TABLE {child_table} VALIDATE CONSTRAINT {fk_name}")


def downgrade() -> None:
    for fk_name, child_table, _ in _FK_TARGETS:
        op.execute(f"ALTER TABLE {child_table} DROP CONSTRAINT IF EXISTS {fk_name}")
