"""add dong_code FK on B-2 tables (living_population_grid, seoul_adstrd_fclty)

대상 (마포만 적재되어 0 고아 확인된 테이블 — VARCHAR(15) 그룹 중 즉시 가능):
  1. living_population_grid.dong_code → dong_mapping.dong_code  (10.5M행, 16동)
  2. seoul_adstrd_fclty.dong_code     → dong_mapping.dong_code  (336행, 16동)

설계 결정:
  • 자식 컬럼은 VARCHAR(15)지만 dong_mapping(dong_code)은 VARCHAR(10).
    PostgreSQL string family 호환이라 FK 가능 — 컬럼 타입 변경은 별도 안건.
  • ON UPDATE CASCADE / ON DELETE NO ACTION (그룹 A와 동일 정책)
  • NOT VALID + VALIDATE 패턴 (락 최소화)

선결 조건:
  ✅ 01_audit_dong_code.sql + 03_inspect_special_cases.sql 실행으로
     두 테이블 0 고아 확인 완료 (2026-04-25)
  ✅ profile_builder.py / agents/tools.py 등 백엔드 코드 점검 — INSERT 0건

후속 (별도 revision 예정):
  • B-1: golmok_rent + mapo_resident_pop cleanup → FK
  • B-3: 그룹 B/C 나머지 — seoul_dong_master 신설 결정 후

Revision ID: b8c4d2e1f395
Revises: e7a9f1c3b5d2
Create Date: 2026-04-25 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "b8c4d2e1f395"
down_revision: Union[str, Sequence[str], None] = "e7a9f1c3b5d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (FK 이름, 자식 테이블, 컬럼)
_FK_TARGETS: list[tuple[str, str, str]] = [
    ("fk_living_population_grid_dong", "living_population_grid", "dong_code"),
    ("fk_seoul_adstrd_fclty_dong", "seoul_adstrd_fclty", "dong_code"),
]


def upgrade() -> None:
    # 1단계: NOT VALID로 FK 추가 (락 짧음)
    for fk_name, child_table, child_column in _FK_TARGETS:
        op.execute(
            f"""
            ALTER TABLE {child_table}
            ADD CONSTRAINT {fk_name}
            FOREIGN KEY ({child_column})
            REFERENCES dong_mapping (dong_code)
            ON UPDATE CASCADE
            ON DELETE NO ACTION
            NOT VALID
            """
        )

    # 2단계: 기존 데이터 검증 (SHARE 락)
    # living_population_grid 10.5M 행 검증은 수십 초~분 단위 소요 가능
    for fk_name, child_table, _ in _FK_TARGETS:
        op.execute(f"ALTER TABLE {child_table} VALIDATE CONSTRAINT {fk_name}")


def downgrade() -> None:
    for fk_name, child_table, _ in _FK_TARGETS:
        op.execute(f"ALTER TABLE {child_table} DROP CONSTRAINT IF EXISTS {fk_name}")
