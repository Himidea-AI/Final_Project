"""users / manager_users 라이프사이클 컬럼 4종 보강 (소급 마이그레이션).

배경:
    2026-04-25 13:48:10 KST 시점 RDS 운영 DB에 다음 컬럼이 ALTER TABLE 로 직접
    추가되었으나, 마이그레이션 파일이 함께 작성되지 않아 alembic chain 에 부재.

    이후 commit 3e2c44a (IM3-252, 2026-04-26) 가 다음 컬럼들을 사용하기 시작:
        - users.is_active           : 회원 탈퇴 (소프트 삭제)
        - users.last_login_at       : 로그인 시각 기록
        - users.updated_at          : 변경 추적
        - users.email_verified      : 이메일 인증 상태
        - manager_users.is_active / last_login_at / updated_at / email_verified

    그 결과 ORM 모델(`backend/src/database/models.py:User`) 과 실제 DB 스키마가
    drift 된 상태. 본 마이그레이션은 그 drift 를 alembic chain 에 정상 등록하기
    위한 소급(catch-up) 마이그레이션.

동작:
    - 이미 컬럼이 존재하는 RDS 환경: IF NOT EXISTS 로 NO-OP
    - 신규/로컬 환경: 동일한 컬럼을 정식으로 ADD
    - 결과적으로 어느 환경이든 동일 스키마 보장

Revision ID: c5e9a1f3d7b2
Revises: b9c5d7e1f2a3
Create Date: 2026-04-30 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "c5e9a1f3d7b2"
down_revision: Union[str, Sequence[str], None] = "b9c5d7e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE users
            ADD COLUMN IF NOT EXISTS updated_at      TIMESTAMPTZ DEFAULT NOW(),
            ADD COLUMN IF NOT EXISTS last_login_at   TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS is_active       BOOLEAN     DEFAULT TRUE,
            ADD COLUMN IF NOT EXISTS email_verified  BOOLEAN     DEFAULT FALSE
        """
    )

    op.execute(
        """
        ALTER TABLE manager_users
            ADD COLUMN IF NOT EXISTS updated_at      TIMESTAMPTZ DEFAULT NOW(),
            ADD COLUMN IF NOT EXISTS last_login_at   TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS is_active       BOOLEAN     DEFAULT TRUE,
            ADD COLUMN IF NOT EXISTS email_verified  BOOLEAN     DEFAULT FALSE
        """
    )

    op.execute("COMMENT ON COLUMN users.updated_at      IS '레코드 최종 수정 시각'")
    op.execute("COMMENT ON COLUMN users.last_login_at   IS '마지막 로그인 시각 (auth.login 에서 갱신)'")
    op.execute("COMMENT ON COLUMN users.is_active       IS '계정 활성 여부 (소프트 삭제: false=탈퇴)'")
    op.execute("COMMENT ON COLUMN users.email_verified  IS '이메일 인증 완료 여부'")

    op.execute("COMMENT ON COLUMN manager_users.updated_at      IS '레코드 최종 수정 시각'")
    op.execute("COMMENT ON COLUMN manager_users.last_login_at   IS '마지막 로그인 시각 (auth.manager_login 에서 갱신)'")
    op.execute(
        "COMMENT ON COLUMN manager_users.is_active       IS '매니저 계정 활성 여부 (소속 팀장 탈퇴 시 false 전파)'"
    )
    op.execute("COMMENT ON COLUMN manager_users.email_verified  IS '이메일 인증 완료 여부'")


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE manager_users
            DROP COLUMN IF EXISTS email_verified,
            DROP COLUMN IF EXISTS is_active,
            DROP COLUMN IF EXISTS last_login_at,
            DROP COLUMN IF EXISTS updated_at
        """
    )

    op.execute(
        """
        ALTER TABLE users
            DROP COLUMN IF EXISTS email_verified,
            DROP COLUMN IF EXISTS is_active,
            DROP COLUMN IF EXISTS last_login_at,
            DROP COLUMN IF EXISTS updated_at
        """
    )
