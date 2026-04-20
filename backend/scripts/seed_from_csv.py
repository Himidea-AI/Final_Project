"""
CSV → PostgreSQL 시드 로더

빈 PostgreSQL DB에 팀이 배포한 CSV 세트를 COPY로 적재한다.
이미 데이터가 있는 테이블은 스킵 (최초 1회 셋업 시나리오).

사용법
------
    # 1) 빈 DB 생성
    createdb mapo_simulator

    # 2) 스키마 마이그레이션
    cd backend && alembic upgrade head

    # 3) CSV 시드 (zip을 풀어서 --dir로 경로 지정)
    python -m scripts.seed_from_csv --dir C:/Users/804/Desktop/dbeaber

CLI 옵션
-------
    --dir PATH   CSV 디렉토리 (기본: backend/data/seed/)
    --dry-run    실제 로드 없이 실행 계획만 출력

환경변수
-------
    POSTGRES_URL  (기본: postgresql://postgres:postgres@localhost:5432/mapo_simulator)
"""

from __future__ import annotations

import argparse
import csv as csv_mod
import io
import os
import re
import sys
from pathlib import Path

import psycopg

DEFAULT_CSV_DIR = Path(__file__).resolve().parent.parent / "data" / "seed"
DEFAULT_DB_URL = "postgresql://postgres:postgres@localhost:5432/mapo_simulator"

SKIP_TABLES = {
    "alembic_version",
    "langchain_pg_collection",
    "langchain_pg_embedding",
}

# 앱 실행 중 쌓이는 데이터 → --force 시 보호 (--force-all 해야 덮어씀)
PROTECTED_TABLES = {
    "users",
    "manager_users",
    "invite_codes",
    "simulation_result",
    "biz_brand_mapping",
}

FILENAME_RE = re.compile(r"^(.+?)_\d{12}\.csv$")


def normalize_db_url(url: str) -> str:
    """async 드라이버 스킴을 동기로 변환."""
    return url.replace("+asyncpg", "").replace("+psycopg", "")


def discover_csvs(csv_dir: Path) -> dict[str, Path]:
    """{테이블명: CSV 경로} 매핑 생성."""
    result: dict[str, Path] = {}
    for path in sorted(csv_dir.glob("*.csv")):
        m = FILENAME_RE.match(path.name)
        if not m:
            print(f"[warn] 파일명 형식 불일치, 스킵: {path.name}")
            continue
        result[m.group(1)] = path
    return result


def existing_tables(conn: psycopg.Connection) -> set[str]:
    rows = conn.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'").fetchall()
    return {r[0] for r in rows}


def row_count(conn: psycopg.Connection, table: str) -> int:
    return conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]


def table_columns(conn: psycopg.Connection, table: str) -> set[str]:
    """public 스키마 테이블의 컬럼명 집합."""
    rows = conn.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table,),
    ).fetchall()
    return {r[0] for r in rows}


def identity_columns(conn: psycopg.Connection, table: str) -> set[str]:
    """SERIAL / IDENTITY 컬럼 (DB가 자동 생성하는 PK 컬럼) 조회."""
    rows = conn.execute(
        """
        SELECT a.attname
        FROM pg_attribute a
        JOIN pg_class c ON a.attrelid = c.oid
        JOIN pg_namespace n ON c.relnamespace = n.oid
        LEFT JOIN pg_attrdef d ON d.adrelid = c.oid AND d.adnum = a.attnum
        WHERE n.nspname = 'public'
          AND c.relname = %s
          AND a.attnum > 0
          AND NOT a.attisdropped
          AND (
            a.attidentity IN ('a', 'd')
            OR pg_get_expr(d.adbin, d.adrelid) LIKE 'nextval(%%'
          )
        """,
        (table,),
    ).fetchall()
    return {r[0] for r in rows}


def _stream_copy(
    conn: psycopg.Connection,
    table: str,
    csv_path: Path,
    header: list[str],
    output_cols: list[str],
    keep_empty_pk: bool,
    pk_cols: set[str],
) -> int:
    """CSV를 파싱해 필요한 row/column만 골라 COPY로 재전송.

    - Python csv.writer가 빈 값을 unquoted empty로 쓰므로 PG는 NULL로 인식
    - output_cols 에 포함된 컬럼만 COPY 대상
    - pk_cols 가 비어있는 row만 통과 (keep_empty_pk=True) 또는 그 반대
    """
    col_sql = ", ".join(f'"{c}"' for c in output_cols)
    sql = f'COPY "{table}" ({col_sql}) FROM STDIN WITH (FORMAT CSV)'

    output_idx = [header.index(c) for c in output_cols]
    pk_idx = [header.index(c) for c in pk_cols if c in header]

    count = 0
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv_mod.reader(f)
        next(reader)  # 헤더 스킵

        with conn.cursor() as cur, cur.copy(sql) as cp:
            buf = io.StringIO()
            writer = csv_mod.writer(buf, quoting=csv_mod.QUOTE_MINIMAL, lineterminator="\n")

            for row in reader:
                if pk_idx:
                    pk_empty = any(row[i] == "" for i in pk_idx)
                    if keep_empty_pk != pk_empty:
                        continue
                writer.writerow([row[i] for i in output_idx])
                count += 1
                if buf.tell() > 65536:
                    cp.write(buf.getvalue().encode("utf-8"))
                    buf.seek(0)
                    buf.truncate()

            if buf.tell() > 0:
                cp.write(buf.getvalue().encode("utf-8"))

    return count


def parse_csv_header(csv_path: Path) -> list[str]:
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv_mod.reader(f)
        return next(reader)


def copy_csv_into_table(conn: psycopg.Connection, table: str, csv_path: Path) -> int:
    """CSV를 테이블에 적재. identity PK가 NULL인 row는 해당 컬럼 제외해 DB가 생성하게 함."""
    header = parse_csv_header(csv_path)
    db_cols = table_columns(conn, table)

    # CSV에는 있지만 DB에 없는 컬럼은 드롭 (스키마 드리프트 대응)
    extra_in_csv = [c for c in header if c not in db_cols]
    if extra_in_csv:
        print(f"[warn] {table}: CSV에만 있는 컬럼 제외 → {extra_in_csv}")
    effective_cols = [c for c in header if c in db_cols]

    id_cols = identity_columns(conn, table)
    id_cols_in_csv = {c for c in id_cols if c in effective_cols}

    if not id_cols_in_csv:
        return _stream_copy(
            conn,
            table,
            csv_path,
            header,
            output_cols=effective_cols,
            keep_empty_pk=False,
            pk_cols=set(),
        )

    # 두 단계: (1) PK 있는 row → 그대로, (2) PK 없는 row → PK 컬럼 제외
    loaded_with_pk = _stream_copy(
        conn,
        table,
        csv_path,
        header,
        output_cols=effective_cols,
        keep_empty_pk=False,
        pk_cols=id_cols_in_csv,
    )

    # phase 1 이후 시퀀스를 MAX(id)+1 로 리셋 (phase 2에서 DB가 생성할 ID 충돌 방지)
    for col in id_cols_in_csv:
        conn.execute(
            f'SELECT setval(pg_get_serial_sequence(%s, %s), COALESCE((SELECT MAX("{col}") FROM "{table}"), 1))',
            (table, col),
        )

    cols_no_pk = [c for c in effective_cols if c not in id_cols_in_csv]
    loaded_without_pk = _stream_copy(
        conn,
        table,
        csv_path,
        header,
        output_cols=cols_no_pk,
        keep_empty_pk=True,
        pk_cols=id_cols_in_csv,
    )
    return loaded_with_pk + loaded_without_pk


def plan_actions(
    conn: psycopg.Connection,
    csv_map: dict[str, Path],
    db_tables: set[str],
    force: bool = False,
    force_all: bool = False,
) -> list[tuple[str, Path | None, str]]:
    """각 테이블별 수행할 액션 계산.

    force=False, force_all=False (기본):
        빈 테이블 → load / 이미 데이터 있으면 → has_data (skip)
    force=True, force_all=False (안전 모드):
        참조 데이터 테이블 → force_reload (TRUNCATE + COPY)
        앱 생성 테이블(PROTECTED_TABLES) → has_data (skip, 보호)
    force_all=True:
        모든 테이블 → force_reload
    """
    plan: list[tuple[str, Path | None, str]] = []
    for table, csv_path in csv_map.items():
        if table in SKIP_TABLES:
            plan.append((table, csv_path, "exclude"))
            continue
        if table not in db_tables:
            plan.append((table, csv_path, "no_table"))
            continue
        n = row_count(conn, table)

        if n == 0:
            plan.append((table, csv_path, "load"))
            continue

        # 데이터 있음 + force 모드
        if force_all or (force and table not in PROTECTED_TABLES):
            plan.append((table, csv_path, f"force_reload:{n}"))
        else:
            # force=True 이지만 PROTECTED_TABLES 에 해당하면 보호
            protected_note = "protected" if (force and table in PROTECTED_TABLES) else ""
            plan.append((table, csv_path, f"has_data:{n}:{protected_note}"))
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description="CSV → PostgreSQL 시드 로더")
    parser.add_argument(
        "--dir",
        type=Path,
        default=DEFAULT_CSV_DIR,
        help=f"CSV 디렉토리 (기본: {DEFAULT_CSV_DIR})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 로드 없이 실행 계획만 출력",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="참조 데이터 테이블을 TRUNCATE 후 CSV로 재적재 (앱 생성 데이터는 보호)",
    )
    parser.add_argument(
        "--force-all",
        action="store_true",
        help="모든 테이블을 TRUNCATE 후 재적재 (users/manager_users/invite_codes/simulation_result/biz_brand_mapping 포함)",
    )
    args = parser.parse_args()

    if args.force and args.force_all:
        args.force = False  # --force-all 이 우선순위 높음

    csv_dir: Path = args.dir
    if not csv_dir.is_dir():
        print(f"[error] CSV 디렉토리가 존재하지 않음: {csv_dir}")
        return 1

    csv_map = discover_csvs(csv_dir)
    if not csv_map:
        print(f"[error] CSV 파일 없음: {csv_dir}")
        return 1

    db_url = normalize_db_url(os.environ.get("POSTGRES_URL", DEFAULT_DB_URL))

    print(f"[seed] CSV 디렉토리: {csv_dir}")
    print(f"[seed] {len(csv_map)}개 CSV 발견")
    print(f"[seed] DB: {db_url.split('@')[-1]}")

    try:
        # with 문으로 열면 성공 시 commit, 예외 시 rollback 자동 처리
        with psycopg.connect(db_url) as conn:
            db_tables = existing_tables(conn)

            if "alembic_version" not in db_tables:
                print("[error] alembic_version 테이블이 없습니다.")
                print("[hint] 먼저 'cd backend && alembic upgrade head' 를 실행하세요.")
                return 1

            plan = plan_actions(conn, csv_map, db_tables, force=args.force, force_all=args.force_all)

            if args.force:
                print("[seed] --force: 참조 데이터만 재적재 (앱 생성 테이블은 보호)")
            elif args.force_all:
                print("[seed] --force-all: 모든 테이블 재적재")

            if args.dry_run:
                print("[dry-run] 실행 계획:")
                for table, csv_path, action in plan:
                    name = csv_path.name if csv_path else "-"
                    print(f"  {action:25s} {table:40s} ← {name}")
                return 0

            loaded = reloaded = skipped = warned = 0

            conn.execute("SET session_replication_role = replica")
            try:
                for table, csv_path, action in plan:
                    if action == "exclude":
                        print(f"[skip] {table}: 제외 대상")
                        skipped += 1
                    elif action == "no_table":
                        print(f"[warn] {table}: DB에 테이블이 없음")
                        warned += 1
                    elif action.startswith("has_data"):
                        parts = action.split(":")
                        n = parts[1]
                        note = parts[2] if len(parts) > 2 else ""
                        suffix = " (보호됨, --force-all 로 덮어쓰기 가능)" if note == "protected" else ""
                        print(f"[skip] {table}: 이미 {int(n):,}건 존재{suffix}")
                        skipped += 1
                    elif action.startswith("force_reload"):
                        assert csv_path is not None
                        old_n = int(action.split(":", 1)[1])
                        try:
                            conn.execute(f'TRUNCATE "{table}" RESTART IDENTITY CASCADE')
                            n = copy_csv_into_table(conn, table, csv_path)
                            print(f"[reload] {table}: {old_n:,} → {n:,}건 교체")
                            reloaded += 1
                        except Exception as e:
                            print(f"[error] {table} 재적재 실패: {e}")
                            raise
                    elif action == "load":
                        assert csv_path is not None
                        try:
                            n = copy_csv_into_table(conn, table, csv_path)
                            print(f"[load] {table}: {n:,}건 적재")
                            loaded += 1
                        except Exception as e:
                            print(f"[error] {table} COPY 실패: {e}")
                            raise
            finally:
                conn.execute("SET session_replication_role = DEFAULT")

            missing_csv = db_tables - set(csv_map.keys()) - SKIP_TABLES
            for table in sorted(missing_csv):
                print(f"[warn] {table}: DB 테이블은 있지만 CSV 없음")
                warned += 1

            summary = f"[done] 적재 {loaded} / 재적재 {reloaded} / 스킵 {skipped} / 경고 {warned}"
            print(summary)
            return 0

    except psycopg.OperationalError as e:
        print(f"[error] DB 연결 실패: {e}")
        print("[hint] POSTGRES_URL 환경변수를 확인하세요.")
        return 1
    except Exception as e:
        print(f"[error] 적재 중 오류: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
