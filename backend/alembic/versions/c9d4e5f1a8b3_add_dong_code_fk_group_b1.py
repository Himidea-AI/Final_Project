"""add dong_code FK on B-1 tables (cleanup 자치구 집계 행 → FK)

대상:
  1. golmok_rent.dong_code        → dong_mapping.dong_code
  2. mapo_resident_pop.dong_code  → dong_mapping.dong_code

Cleanup 정책 (옵션 A — 가장 안전):
  - golmok_rent의 '11440' (5자리, gubun='gu', 자치구 합계) 24행 → dong_code NULL
  - mapo_resident_pop의 '11440000' (자치구 합계, dong_name='서울특별시 마포구') 24행 → dong_code NULL
  - 데이터 손실 없음: dong_name + gubun으로 자치구 행 식별 가능
  - 두 컬럼 모두 nullable이라 NULL 변경 가능

영향 분석 (사전 점검):
  - 두 테이블에 INSERT 하는 코드: 0건
  - 두 테이블에서 dong_code 직접 매칭(`= '11440'`) 사용 코드: 0건
  - LIKE 패턴 매칭(`LIKE '11440%'`)에서 자치구 합계는 자연 제외 (학습 노이즈 감소 효과)

Revision ID: c9d4e5f1a8b3
Revises: b8c4d2e1f395
Create Date: 2026-04-25 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "c9d4e5f1a8b3"
down_revision: Union[str, Sequence[str], None] = "b8c4d2e1f395"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_FK_TARGETS: list[tuple[str, str, str]] = [
    ("fk_golmok_rent_dong", "golmok_rent", "dong_code"),
    ("fk_mapo_resident_pop_dong", "mapo_resident_pop", "dong_code"),
]


def upgrade() -> None:
    # 1단계: 자치구 집계 행의 dong_code를 NULL로 변경
    # (자치구 식별 정보는 dong_name/gubun에 그대로 남음)
    op.execute("""
        UPDATE golmok_rent
        SET dong_code = NULL
        WHERE dong_code = '11440'
    """)
    op.execute("""
        UPDATE mapo_resident_pop
        SET dong_code = NULL
        WHERE dong_code = '11440000'
    """)

    # 2단계: NOT VALID로 FK 추가
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

    # 3단계: 검증
    for fk_name, child_table, _ in _FK_TARGETS:
        op.execute(f"ALTER TABLE {child_table} VALIDATE CONSTRAINT {fk_name}")


def downgrade() -> None:
    # FK 제거
    for fk_name, child_table, _ in _FK_TARGETS:
        op.execute(f"ALTER TABLE {child_table} DROP CONSTRAINT IF EXISTS {fk_name}")

    # NULL → 원래 자치구 코드 복원 (dong_name + gubun 기반)
    # ※ 만약 마이그레이션 후 신규로 NULL 행이 들어왔다면 잘못 매칭될 수 있음 — 주의
    op.execute("""
        UPDATE golmok_rent
        SET dong_code = '11440'
        WHERE dong_code IS NULL AND gubun = 'gu' AND dong_name = '마포구'
    """)
    op.execute("""
        UPDATE mapo_resident_pop
        SET dong_code = '11440000'
        WHERE dong_code IS NULL AND dong_name = '서울특별시 마포구'
    """)
