"""
테스트용 계정 생성 스크립트 — 사업자등록번호 없이 바로 로그인 테스트

기본 계정
--------
    email:       test@spotter.local
    password:    test1234
    biz_number:  0000000000 (더미)
    plan:        starter

사용법
------
    cd backend
    python -m scripts.create_test_user

    # 커스텀:
    python -m scripts.create_test_user --email me@test.local --password mypass

환경변수
-------
    POSTGRES_URL  (기본: postgresql://postgres:postgres@localhost:5432/mapo_simulator)

동작
----
    - 같은 email 또는 biz_number 로 이미 계정이 있으면 스킵 (idempotent)
    - users 테이블에 직접 INSERT (회원가입 API 우회)
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import datetime, timezone

import bcrypt
import psycopg

DEFAULT_DB_URL = "postgresql://postgres:postgres@localhost:5432/mapo_simulator"

DEFAULTS = {
    "email": "test@spotter.local",
    "password": "test1234",
    "biz_number": "0000000000",
    "company_name": "테스트 기업",
    "contact_name": "테스트 사용자",
    "phone": "01000000000",
    "position": "개발자",
    "store_count": 0,
    "plan": "starter",
}


def _normalize_db_url(url: str) -> str:
    return url.replace("+asyncpg", "").replace("+psycopg", "")


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="테스트 계정 생성 (사업자등록번호 우회)")
    parser.add_argument("--email", default=DEFAULTS["email"])
    parser.add_argument("--password", default=DEFAULTS["password"])
    parser.add_argument("--biz-number", default=DEFAULTS["biz_number"])
    parser.add_argument("--company-name", default=DEFAULTS["company_name"])
    parser.add_argument("--contact-name", default=DEFAULTS["contact_name"])
    parser.add_argument("--phone", default=DEFAULTS["phone"])
    args = parser.parse_args()

    db_url = _normalize_db_url(os.environ.get("POSTGRES_URL", DEFAULT_DB_URL))
    print(f"[create_test_user] DB: {db_url.split('@')[-1]}")

    try:
        with psycopg.connect(db_url) as conn:
            # users 테이블 존재 확인
            exists = conn.execute("SELECT to_regclass('public.users')").fetchone()[0]
            if not exists:
                print("[error] users 테이블이 없습니다. 먼저 alembic upgrade head 를 실행하세요.")
                return 1

            # 중복 체크
            existing = conn.execute(
                "SELECT id, email, biz_number FROM users WHERE email = %s OR biz_number = %s",
                (args.email, args.biz_number),
            ).fetchone()
            if existing:
                uid, mail, biz = existing
                print(f"[skip] 이미 계정 존재: {mail} (biz_number={biz}, id={uid})")
                print(f"[info] 로그인: email={args.email} / password={args.password}")
                return 0

            # INSERT
            user_id = uuid.uuid4()
            password_hash = _hash_password(args.password)
            now = datetime.now(timezone.utc)

            conn.execute(
                """
                INSERT INTO users (
                    id, company_name, biz_number, contact_name, position,
                    email, phone, store_count, password_hash, plan,
                    agree_terms, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s
                )
                """,
                (
                    user_id,
                    args.company_name,
                    args.biz_number,
                    args.contact_name,
                    DEFAULTS["position"],
                    args.email,
                    args.phone,
                    DEFAULTS["store_count"],
                    password_hash,
                    DEFAULTS["plan"],
                    True,
                    now,
                ),
            )

        print("[ok] 테스트 계정 생성 완료")
        print("    email:      ", args.email)
        print("    password:   ", args.password)
        print("    biz_number: ", args.biz_number)
        print("    id:         ", user_id)
        return 0

    except psycopg.OperationalError as e:
        print(f"[error] DB 연결 실패: {e}")
        return 1
    except Exception as e:
        print(f"[error] 계정 생성 실패: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
