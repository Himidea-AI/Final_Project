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

# 더미 계정용 기본 brand mapping — ftc_brand_franchise 매칭 실패 시 fallback.
# 실제 시뮬레이션이 동작하도록 마포 점포가 있는 보편 브랜드 사용.
DEFAULT_BRAND_MAPPING = {
    "brand_name": "메가엠지씨커피(MEGA MGC COFFEE)",
    "industry_large": "외식",
    "industry_medium": "커피",
    "franchise_count": 3325,
    "avg_sales": 388443,
    "mapo_store_count": 41,
}


def _lookup_brand_from_ftc(conn, company_name: str) -> dict | None:
    """ftc_brand_franchise 에서 company_name 으로 최상위 매칭 1건 조회."""
    row = conn.execute(
        """
        SELECT
            "brandNm"        AS brand_name,
            "indutyLclasNm"  AS industry_large,
            "indutyMlsfcNm"  AS industry_medium,
            "frcsCnt"        AS franchise_count,
            "avrgSlsAmt"     AS avg_sales
        FROM ftc_brand_franchise
        WHERE ("corpNm" ILIKE %s OR "brandNm" ILIKE %s)
        ORDER BY yr DESC, "frcsCnt" DESC NULLS LAST
        LIMIT 1
        """,
        (f"%{company_name}%", f"%{company_name}%"),
    ).fetchone()
    if not row:
        return None
    brand_name, industry_large, industry_medium, franchise_count, avg_sales = row
    mapo_count = (
        conn.execute(
            "SELECT COUNT(*) FROM store_info WHERE store_name ILIKE %s",
            (f"%{brand_name}%",),
        ).fetchone()[0]
        or 0
    )
    return {
        "brand_name": brand_name,
        "industry_large": industry_large or "기타",
        "industry_medium": industry_medium or "기타",
        "franchise_count": franchise_count or 0,
        "avg_sales": avg_sales or 0,
        "mapo_store_count": mapo_count,
    }


def _ensure_brand_mapping(conn, biz_number: str, company_name: str) -> dict:
    """biz_brand_mapping 에 row 보장. 없으면 ftc 조회 → 실패 시 기본값."""
    existing = conn.execute(
        "SELECT brand_name FROM biz_brand_mapping WHERE biz_number = %s",
        (biz_number,),
    ).fetchone()
    if existing:
        return {"action": "skip", "brand_name": existing[0]}

    brand = None
    try:
        brand = _lookup_brand_from_ftc(conn, company_name)
    except Exception:
        # ftc_brand_franchise / store_info 부재 환경에서도 동작하도록 가드
        brand = None

    if brand is None:
        brand = dict(DEFAULT_BRAND_MAPPING)

    conn.execute(
        """
        INSERT INTO biz_brand_mapping (
            biz_number, company_name, brand_name,
            industry_large, industry_medium,
            franchise_count, avg_sales, mapo_store_count
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (biz_number) DO NOTHING
        """,
        (
            biz_number,
            company_name,
            brand["brand_name"],
            brand["industry_large"],
            brand["industry_medium"],
            brand["franchise_count"],
            brand["avg_sales"],
            brand["mapo_store_count"],
        ),
    )
    return {"action": "inserted", **brand}


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
                # 기존 계정의 brand mapping 도 보장 (구버전에서 만들어진 계정 catch-up)
                mapping_res = _ensure_brand_mapping(conn, biz, args.company_name)
                if mapping_res["action"] == "inserted":
                    print(f"[mapping] biz_brand_mapping 신규 생성 → {mapping_res['brand_name']}")
                else:
                    print(f"[mapping] 기존 mapping 유지 → {mapping_res['brand_name']}")
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

            # biz_brand_mapping 동시 보장 — login 시 brand=null 회귀 방지
            mapping_res = _ensure_brand_mapping(conn, args.biz_number, args.company_name)

        print("[ok] 테스트 계정 생성 완료")
        print("    email:      ", args.email)
        print("    password:   ", args.password)
        print("    biz_number: ", args.biz_number)
        print("    id:         ", user_id)
        if mapping_res["action"] == "inserted":
            print(f"    brand:       {mapping_res['brand_name']} (mapo_store={mapping_res.get('mapo_store_count')})")
        return 0

    except psycopg.OperationalError as e:
        print(f"[error] DB 연결 실패: {e}")
        return 1
    except Exception as e:
        print(f"[error] 계정 생성 실패: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
