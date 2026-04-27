"""add dong_code FK on group A tables (NOT VALID + VALIDATE pattern)

대상 테이블 (그룹 A — VARCHAR(10), 고아 0% 확인됨):
  1. living_population.dong_code  → dong_mapping.dong_code  (968,064행, 16동, 0 고아)
  2. district_sales.dong_code     → dong_mapping.dong_code  (3,703행, 16동, 0 고아)
  3. store_info.dong_code         → dong_mapping.dong_code  (30,488행, 16동, 0 고아)
  4. store_quarterly.dong_code    → dong_mapping.dong_code  (3,840행, 16동, 0 고아)

별도 revision으로 분리 처리 예정:
  • golmok_rent — '11440'(자치구 코드) 24행 cleanup 필요
  • seoul_adstrd_fclty — 그룹 C이지만 마포만 있어 FK 가능
  • dong_subway_access, seoul_resident_pop_quarterly — 별도 정합성 검증 후
  • 그룹 B/C 나머지 — dong_mapping 서울 전체 확장 결정 후

설계 결정:
  • ON DELETE NO ACTION + ON UPDATE CASCADE
    - 마스터 행 삭제는 운영상 거의 없음 → CASCADE 위험 회피
    - dong_code 재배정 시(동 합병/분리 등) 자동 전파
  • NOT VALID 옵션으로 추가 → 기존 데이터 재검증 비용 회피
    (테이블 락 최소화, 신규 INSERT/UPDATE만 검증)
  • 별도 op.execute("ALTER TABLE ... VALIDATE CONSTRAINT ...") 단계로
    백그라운드에서 기존 데이터 검증

선결 조건 (이 마이그레이션 실행 전 필수):
  ✅ 01_audit_dong_code.sql 실행하여 4개 테이블 고아 0 확인 (2026-04-25 완료)

Revision ID: e7a9f1c3b5d2
Revises: a3b4c5d6e7f8
Create Date: 2026-04-25 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "e7a9f1c3b5d2"
down_revision: Union[str, Sequence[str], None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (FK 이름, 자식 테이블, 컬럼)
_FK_TARGETS: list[tuple[str, str, str]] = [
    ("fk_living_population_dong", "living_population", "dong_code"),
    ("fk_district_sales_dong", "district_sales", "dong_code"),
    ("fk_store_info_dong", "store_info", "dong_code"),
    ("fk_store_quarterly_dong", "store_quarterly", "dong_code"),
]


def upgrade() -> None:
    # 1단계: NOT VALID로 FK 추가 (락 짧음, 신규 데이터만 검증)
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

    # 2단계: 기존 데이터 검증 (백그라운드, 락은 SHARE)
    # 고아 행이 남아있으면 여기서 실패 → upgrade 롤백됨
    for fk_name, child_table, _ in _FK_TARGETS:
        op.execute(f"ALTER TABLE {child_table} VALIDATE CONSTRAINT {fk_name}")


def downgrade() -> None:
    for fk_name, child_table, _ in _FK_TARGETS:
        op.execute(f"ALTER TABLE {child_table} DROP CONSTRAINT IF EXISTS {fk_name}")
