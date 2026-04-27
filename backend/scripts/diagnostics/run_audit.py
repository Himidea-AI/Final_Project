"""
진단 SQL 파일을 Python으로 실행 (psql 없는 환경 대응).

사용:
    # 기본 (01_audit_dong_code.sql 실행)
    python backend/scripts/diagnostics/run_audit.py

    # 결과를 파일로
    python backend/scripts/diagnostics/run_audit.py > audit_result.txt

    # 다른 SQL 파일 지정
    python backend/scripts/diagnostics/run_audit.py path/to/other.sql

전제:
    .env 에 POSTGRES_URL 설정되어 있어야 함.
    sqlalchemy + psycopg2(or psycopg) + python-dotenv 설치 필요 (백엔드 의존성에 포함).

특징:
    • psql 메타커맨드(\\echo, \\timing 등)는 자동으로 무시
    • 세미콜론 단위로 statement 분리 후 순차 실행
    • SELECT 결과는 표 형태로 출력
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


_REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_REPO_ROOT / ".env")

DB_URL = os.getenv("POSTGRES_URL")
if not DB_URL:
    sys.exit("ERROR: POSTGRES_URL not set in .env")


def split_statements(sql: str) -> list[str]:
    """psql 메타커맨드를 제거하고 세미콜론 단위로 statement 분리."""
    lines = [ln for ln in sql.splitlines() if not ln.lstrip().startswith("\\")]
    cleaned = "\n".join(lines)
    return [s.strip() for s in cleaned.split(";") if s.strip()]


def first_comment(stmt: str) -> str:
    """statement 첫 주석을 섹션 제목으로 사용."""
    for ln in stmt.splitlines():
        s = ln.strip()
        if s.startswith("--"):
            return s.lstrip("- ").strip()
    return "(unnamed)"


def print_table(cols: list[str], rows: list[tuple]) -> None:
    if not rows:
        print("(no rows)")
        return
    str_rows = [[str(v) if v is not None else "" for v in r] for r in rows]
    widths = [max(len(c), max((len(r[i]) for r in str_rows), default=0)) for i, c in enumerate(cols)]
    print(" | ".join(c.ljust(widths[i]) for i, c in enumerate(cols)))
    print("-+-".join("-" * w for w in widths))
    for r in str_rows:
        print(" | ".join(r[i].ljust(widths[i]) for i in range(len(cols))))


def main(sql_path: Path) -> None:
    statements = split_statements(sql_path.read_text(encoding="utf-8"))
    print(f"# Audit: {sql_path.name}  (statements: {len(statements)})")

    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        for i, stmt in enumerate(statements, 1):
            print(f"\n{'=' * 70}")
            print(f"  #{i:02d} {first_comment(stmt)}")
            print(f"{'=' * 70}")
            try:
                result = conn.execute(text(stmt))
                if result.returns_rows:
                    print_table(list(result.keys()), result.fetchall())
                else:
                    print(f"(rowcount={result.rowcount})")
            except Exception as e:
                print(f"ERROR: {type(e).__name__}: {e}")


if __name__ == "__main__":
    default_sql = Path(__file__).parent / "01_audit_dong_code.sql"
    sql_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else default_sql
    if not sql_arg.exists():
        sys.exit(f"ERROR: {sql_arg} not found")
    main(sql_arg)
