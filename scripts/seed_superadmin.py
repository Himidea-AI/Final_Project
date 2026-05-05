"""기존 master 계정에 superadmin 권한 부여 스크립트.

사용:
    python -m scripts.seed_superadmin --email admin@example.com [--revoke]

동작:
- 이메일로 users 테이블 lookup. is_superadmin = true (또는 --revoke 시 false) UPDATE.
- 신규 가입은 일반 회원가입(/auth/signup)으로 진행 후 본 스크립트로 권한 부여.
- 보안: 본 스크립트는 관리자가 직접 실행. 자동 시드 / 환경변수 자동 부여 일체 금지.
- bizNumber 검증·브랜드 매핑 필요한 신규 본부 회원가입 흐름과 분리해 둔다.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# 프로젝트 루트에서 실행 시 backend/ 를 sys.path 에 추가하여 src.* import 보장
_BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy import text


def _resolve_db_url() -> str:
    """settings.postgres_url을 우선 사용, 없으면 DATABASE_URL fallback."""
    try:
        from src.config.settings import settings  # type: ignore[import-not-found]

        url = getattr(settings, "postgres_url", None)
        if url:
            return str(url)
    except Exception:
        pass
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise SystemExit("DATABASE_URL 미설정. .env 또는 환경변수 확인.")
    return url


def grant_superadmin(email: str, *, revoke: bool = False, db_url: str | None = None) -> dict:
    """이메일로 users 테이블 lookup 후 is_superadmin 토글."""
    from src.database.sync_engine import get_sync_engine  # type: ignore[import-not-found]

    db_url = db_url or _resolve_db_url()
    engine = get_sync_engine(db_url)
    new_value = not revoke

    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id, contact_name, is_superadmin FROM users WHERE email = :email"),
            {"email": email},
        ).fetchone()
        if not row:
            return {"status": "error", "message": f"가입되지 않은 이메일: {email}"}

        current = bool(row._mapping["is_superadmin"])
        if current == new_value:
            return {
                "status": "noop",
                "message": f"already {'superadmin' if new_value else 'master'}: {email}",
            }

        conn.execute(
            text("UPDATE users SET is_superadmin = :v, updated_at = now() WHERE email = :email"),
            {"v": new_value, "email": email},
        )

    return {
        "status": "success",
        "email": email,
        "user_id": str(row._mapping["id"]),
        "contact_name": row._mapping["contact_name"],
        "is_superadmin": new_value,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="superadmin 권한 부여/회수")
    parser.add_argument("--email", required=True, help="대상 사용자 이메일 (users.email)")
    parser.add_argument(
        "--revoke",
        action="store_true",
        help="권한 회수 (is_superadmin=false). 미지정 시 부여 (true).",
    )
    args = parser.parse_args(argv)

    result = grant_superadmin(args.email, revoke=args.revoke)
    print(result)
    return 0 if result["status"] in {"success", "noop"} else 1


if __name__ == "__main__":
    sys.exit(main())
