"""
통합 DB 초기화 스크립트 — 팀원 온보딩용

빈 PostgreSQL DB에 대해 스키마 생성 → CSV 적재 → RAG 임베딩 생성까지 한 번에 실행.

사용법
------
    # 1) 먼저 빈 DB가 있어야 함
    createdb mapo_simulator

    # 2) POSTGRES_URL 환경변수 설정 (로컬 비밀번호)
    export POSTGRES_URL=postgresql://postgres:<비번>@localhost:5432/mapo_simulator

    # 3) 이 스크립트 실행
    cd backend
    python -m scripts.init_db --csv-dir <CSV폴더경로>

옵션
----
    --csv-dir PATH   CSV 디렉토리 (필수)
    --skip-ingest    법률 RAG 임베딩 생성 단계 건너뛰기 (HF 모델 다운로드 시간 절약)
    --dry-run        실제 적재 없이 어떤 테이블이 로드될지만 출력 (seed 단계에 전달)

단계
----
    1) DB 연결 확인
    2) pgvector 확장 설치 (CREATE EXTENSION IF NOT EXISTS vector)
    3) alembic upgrade head  — 스키마 생성
    4) CSV 시드 (python -m scripts.seed_from_csv)
    5) 법률 RAG 임베딩 (python data/legal/ingest.py) — 건너뛰기 가능
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import psycopg

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_URL = "postgresql://postgres:postgres@localhost:5432/mapo_simulator"


def _normalize_db_url(url: str) -> str:
    return url.replace("+asyncpg", "").replace("+psycopg", "")


def _step(n: int, total: int, name: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"[{n}/{total}] {name}")
    print("=" * 60)


def check_connection(db_url: str) -> bool:
    try:
        with psycopg.connect(db_url, connect_timeout=5) as conn:
            ver = conn.execute("SELECT version()").fetchone()[0]
            print(f"[ok] {ver.split(',')[0]}")
            return True
    except psycopg.OperationalError as e:
        print(f"[error] DB 연결 실패: {e}")
        print("[hint] 먼저 'createdb mapo_simulator' 로 빈 DB를 생성하세요.")
        print("[hint] POSTGRES_URL 환경변수의 호스트/포트/비밀번호도 확인하세요.")
        return False


def ensure_pgvector(db_url: str) -> bool:
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            print("[ok] pgvector 확장 활성화됨")
            return True
    except psycopg.errors.InsufficientPrivilege:
        print("[error] pgvector 확장 설치 권한 부족")
        print("[hint] DB 소유자 또는 superuser 계정으로 실행하세요.")
        return False
    except Exception as e:
        err_msg = str(e)
        if "사용할 수 없습니다" in err_msg or "not available" in err_msg:
            print("[error] pgvector 확장이 PostgreSQL 서버에 설치되어 있지 않음")
            print("[hint] Windows: https://github.com/pgvector/pgvector#windows 참고")
            print("[hint] Linux: apt install postgresql-XX-pgvector (XX는 PG 버전)")
        else:
            print(f"[error] pgvector 확장 설치 실패: {e}")
        return False


def run_alembic() -> bool:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
    )
    if result.returncode != 0:
        print("[error] alembic upgrade 실패")
        return False
    print("[ok] 스키마 생성 완료")
    return True


def run_seed(csv_dir: Path, dry_run: bool, force: bool, force_all: bool) -> bool:
    args = [sys.executable, "-m", "scripts.seed_from_csv", "--dir", str(csv_dir)]
    if dry_run:
        args.append("--dry-run")
    if force:
        args.append("--force")
    if force_all:
        args.append("--force-all")
    result = subprocess.run(args, cwd=BACKEND_DIR)
    if result.returncode != 0:
        print("[error] CSV 시드 실패")
        return False
    return True


def run_legal_ingest() -> bool:
    ingest_script = BACKEND_DIR / "data" / "legal" / "ingest.py"
    if not ingest_script.exists():
        print(f"[warn] {ingest_script} 없음 — 단계 스킵")
        return True

    chunks = BACKEND_DIR / "data" / "legal" / "processed" / "chunks.json"
    if not chunks.exists():
        print(f"[warn] {chunks} 없음 — 법률 RAG 임베딩 스킵")
        return True

    print("[info] HuggingFace 모델 첫 실행 시 약 500MB 다운로드 후 진행합니다.")
    result = subprocess.run([sys.executable, "data/legal/ingest.py"], cwd=BACKEND_DIR)
    if result.returncode != 0:
        print("[error] 법률 RAG 임베딩 실패")
        return False
    print("[ok] RAG 임베딩 완료")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="통합 DB 초기화 스크립트")
    parser.add_argument("--csv-dir", type=Path, required=True, help="CSV 디렉토리 경로")
    parser.add_argument("--skip-ingest", action="store_true", help="법률 RAG 임베딩 단계 생략")
    parser.add_argument("--dry-run", action="store_true", help="CSV 시드 단계 dry-run")
    parser.add_argument(
        "--force",
        action="store_true",
        help="참조 데이터 테이블을 재적재 (앱 생성 데이터는 보호)",
    )
    parser.add_argument(
        "--force-all",
        action="store_true",
        help="모든 테이블을 재적재 (users 등 앱 생성 데이터 포함, 주의)",
    )
    args = parser.parse_args()

    if not args.csv_dir.is_dir():
        print(f"[error] CSV 디렉토리가 존재하지 않음: {args.csv_dir}")
        return 1

    db_url = _normalize_db_url(os.environ.get("POSTGRES_URL", DEFAULT_DB_URL))
    print(f"[init_db] 대상 DB: {db_url.split('@')[-1]}")

    # pgvector는 RAG 임베딩용 — --skip-ingest 시 생략
    total = 3 if args.skip_ingest else 5
    step_no = 0

    step_no += 1
    _step(step_no, total, "DB 연결 확인")
    if not check_connection(db_url):
        return 1

    if not args.skip_ingest:
        step_no += 1
        _step(step_no, total, "pgvector 확장 설치")
        if not ensure_pgvector(db_url):
            print("[hint] pgvector 없이 진행하려면 --skip-ingest 로 재실행하세요.")
            return 1

    step_no += 1
    _step(step_no, total, "alembic 마이그레이션 (스키마 생성)")
    if not run_alembic():
        return 1

    step_no += 1
    _step(step_no, total, "CSV 데이터 적재")
    if not run_seed(args.csv_dir, args.dry_run, args.force, args.force_all):
        return 1

    if not args.skip_ingest:
        step_no += 1
        _step(step_no, total, "법률 RAG 임베딩 재생성")
        if not run_legal_ingest():
            return 1

    print(f"\n{'=' * 60}")
    print("[done] 전체 초기화 완료")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
