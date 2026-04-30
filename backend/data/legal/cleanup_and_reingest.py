"""
1회용: 누적 중복 데이터 청소 + 깨끗한 상태로 재적재

법률 RAG 데이터 정합성 회복 (SP1)을 위한 1회 wipe 스크립트.
운영 후엔 비상시에만 실행 — 평상시 갱신은 reingest.py 사용.

흐름:
    1. 안전장치 검사 (--yes-wipe-data, interactive 확인)
    2. pg_dump로 langchain_pg_embedding/collection 백업
    3. DROP TABLE CASCADE (트랜잭션 내, 실패 시 raise)
    4. parse_pdfs.py 실행 → chunks.json 갱신
    5. reingest.py 실행 (빈 테이블 → INSERT만 동작)
    6. invariant 검증

실행:
    cd backend && python -m data.legal.cleanup_and_reingest --yes-wipe-data
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Windows 이벤트 루프 호환 (subprocess가 reingest 호출 시)
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from dotenv import load_dotenv

load_dotenv()

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://postgres:postgres@db:5432/mapo_simulator")
BACKUP_DIR = Path(__file__).parent / "backups"
COLLECTION = "legal_documents"


def _check_flags() -> None:
    if "--yes-wipe-data" not in sys.argv:
        print("위험: 이 스크립트는 langchain_pg_embedding 전체를 삭제합니다.")
        print("실행 방법: python -m data.legal.cleanup_and_reingest --yes-wipe-data")
        sys.exit(1)


def _backup_tables() -> Path | None:
    """pg_dump로 백업 시도. pg_dump 없으면 경고 후 None 반환 (데이터는 PDF로 재생성 가능)."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"langchain_pg_embedding_{timestamp}.sql"

    print(f"1단계: 백업 -> {backup_path}")
    try:
        subprocess.check_call(
            [
                "pg_dump",
                POSTGRES_URL,
                "-t",
                "langchain_pg_embedding",
                "-t",
                "langchain_pg_collection",
                "-f",
                str(backup_path),
            ]
        )
    except FileNotFoundError:
        print("  WARNING: pg_dump 명령 없음 - 백업 건너뜀")
        print("  (legal 데이터는 backend/data/legal/raw/ PDF에서 parse_pdfs.py + reingest.py로 재생성 가능)")
        return None
    print(f"  백업 완료: {backup_path.stat().st_size:,} bytes")
    return backup_path


def _show_current_state(conn) -> int:
    """langchain_pg_embedding 행 수 조회. 테이블 없으면 0 반환 (이전 cleanup 후 재실행 시나리오)."""
    with conn.cursor() as cur:
        try:
            cur.execute("SELECT COUNT(*), COUNT(DISTINCT document) FROM langchain_pg_embedding")
            row = cur.fetchone()
        except Exception as e:
            # UndefinedTable 등 — 테이블 자체가 없으므로 0
            print(f"  테이블 없음 (또는 조회 실패: {type(e).__name__}) - 행 수 0으로 진행")
            return 0
    if row is None:
        return 0
    total, distinct = row
    print(f"  현재 langchain_pg_embedding: {total}행 (unique document {distinct}개)")
    return total


def _confirm_interactive(row_count: int) -> None:
    # --yes-wipe-data가 이미 명시적 동의이므로 추가 확인은 interactive 환경에서만 수행
    # subprocess/CI/non-tty 환경에서는 input() 호출이 EOFError 일으키므로 회피
    if not sys.stdin.isatty():
        print(f"  non-interactive 환경 - {row_count}행 삭제 진행 (--yes-wipe-data로 이미 동의)")
        return
    try:
        ans = input(f"{row_count}행을 삭제하고 재적재합니다. 계속? [yes/N]: ")
    except EOFError:
        print(f"  stdin 비어있음 - {row_count}행 삭제 진행 (--yes-wipe-data로 이미 동의)")
        return
    if ans.strip().lower() != "yes":
        print("취소됨")
        sys.exit(0)


def _drop_tables(conn) -> None:
    print("2단계: 테이블 삭제 (트랜잭션)")
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS langchain_pg_embedding CASCADE")
            cur.execute("DROP TABLE IF EXISTS langchain_pg_collection CASCADE")
    print("  langchain_pg_embedding, langchain_pg_collection DROP 완료")


def _run_parse_pdfs() -> None:
    print("3단계: parse_pdfs.py 실행 → chunks.json 갱신")
    subprocess.check_call(
        [sys.executable, "-m", "data.legal.parse_pdfs"],
        cwd=str(Path(__file__).resolve().parents[2]),  # backend/
    )


def _run_reingest() -> None:
    print("4단계: reingest.py 실행 (빈 테이블 → 일반 INSERT 동작)")
    subprocess.check_call(
        [sys.executable, "-m", "data.legal.reingest"],
        cwd=str(Path(__file__).resolve().parents[2]),  # backend/
    )


def main() -> None:
    import psycopg

    _check_flags()

    print("0단계: 현재 상태 확인")
    with psycopg.connect(POSTGRES_URL) as conn:
        row_count = _show_current_state(conn)

    _confirm_interactive(row_count)
    _backup_tables()

    with psycopg.connect(POSTGRES_URL) as conn:
        _drop_tables(conn)

    _run_parse_pdfs()
    _run_reingest()

    print("\n5단계: 최종 invariants 검증 (reingest 내부에서 자동 수행됨)")
    print("\n완료: 데이터 정합성 회복 (SP1)")


if __name__ == "__main__":
    main()
