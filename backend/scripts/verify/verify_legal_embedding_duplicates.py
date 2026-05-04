"""langchain_pg_embedding 중복/무결성 검증.

체크 항목:
  1) total rows vs unique chunk_id (NULL chunk_id 잔존 포함)
  2) chunk_id 별 dup TOP 10
  3) document 본문 해시 dup TOP 10 (참고: chunk_id 다른데 본문 같음 = 부칙/공통문 정상)
  4) langchain_pg_collection 1행 정상성
  5) embedding NULL / 차원 불일치
  6) chunks.json vs DB chunk_id 차집합 (유령/미적재)
  7) law_legislations / law_precedents 본문 채움률

사용법:
  cd backend
  POSTGRES_URL=... python scripts/verify/verify_legal_embedding_duplicates.py

종료 코드:
  0: 이상 무
  1: 중복 / 유령 / NULL chunk_id / 차원 불일치 검출
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

# Windows cp949 stdout 회피 - 한글/유니코드 출력 강제 utf-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# .env 로드 (worktree/루트 양쪽)
for env_path in (Path(__file__).parents[2] / ".env", Path(__file__).parents[3] / ".env"):
    if env_path.exists():
        load_dotenv(env_path)
        break

_DEFAULT_DB_URL = os.environ.get(
    "POSTGRES_URL",
    "postgresql://postgres:postgres@localhost:5432/mapo_simulator",
)

CHUNKS_PATH = Path(__file__).parents[2] / "data" / "legal" / "processed" / "chunks.json"


def _print_header(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def check_row_vs_unique(cur) -> tuple[int, int, int]:
    cur.execute(
        """
        SELECT
            COUNT(*) AS total_rows,
            COUNT(DISTINCT cmetadata->>'chunk_id') AS unique_chunk_id,
            COUNT(*) FILTER (WHERE cmetadata->>'chunk_id' IS NULL) AS null_chunk_id
        FROM langchain_pg_embedding
        """
    )
    total, uniq, nulls = cur.fetchone()
    _print_header("1) total rows vs unique chunk_id")
    print(f"  total_rows       : {total:,}")
    print(f"  unique_chunk_id  : {uniq:,}")
    print(f"  null_chunk_id    : {nulls:,}")
    if total == 0:
        print("  WARN: 테이블 비어 있음")
    elif total > uniq:
        print(f"  FAIL: 중복 {total - uniq:,}행 ({(total - uniq) / total * 100:.1f}%)")
    else:
        print("  OK: 중복 없음")
    return total, uniq, nulls


def check_chunk_id_dup(cur) -> int:
    cur.execute(
        """
        SELECT cmetadata->>'chunk_id' AS chunk_id, COUNT(*) AS dup_count
        FROM langchain_pg_embedding
        WHERE cmetadata ? 'chunk_id'
        GROUP BY 1
        HAVING COUNT(*) > 1
        ORDER BY dup_count DESC
        LIMIT 10
        """
    )
    rows = cur.fetchall()
    _print_header("2) chunk_id 중복 TOP 10")
    if not rows:
        print("  OK: chunk_id 중복 0건")
    else:
        for chunk_id, dup in rows:
            print(f"  {chunk_id}  x{dup}")
    return len(rows)


def check_document_dup(cur) -> int:
    """본문 같은 다중 chunk_id 는 부칙/공통문 정상 패턴. NULL chunk_id 와 결합된 경우만 FAIL.

    반환: 진짜 중복 그룹 수 (NULL chunk_id 가 같은 본문 그룹에 섞여 있는 경우)
    """
    cur.execute(
        """
        SELECT
            md5(document) AS doc_hash,
            COUNT(*) AS dup_count,
            COUNT(DISTINCT cmetadata->>'chunk_id') AS distinct_chunk_ids,
            COUNT(*) FILTER (WHERE cmetadata->>'chunk_id' IS NULL) AS null_in_group
        FROM langchain_pg_embedding
        GROUP BY 1
        HAVING COUNT(*) > 1
        ORDER BY dup_count DESC
        LIMIT 10
        """
    )
    rows = cur.fetchall()
    _print_header("3) document 본문 중복 TOP 10")
    if not rows:
        print("  OK: 본문 중복 0건")
        return 0
    bad = 0
    for doc_hash, dup, distinct_ids, null_in in rows:
        # chunk_id 가 다른데 본문 같음 -> 부칙/공통문 (정상)
        # chunk_id 가 같거나 NULL 행 섞임 -> 진짜 중복
        is_bad = null_in > 0 or distinct_ids < dup
        flag = "BAD" if is_bad else "INFO"
        if is_bad:
            bad += 1
        print(f"  [{flag}] md5={doc_hash}  total={dup}  distinct_id={distinct_ids}  null_id={null_in}")
    if bad == 0:
        print("  OK: 모든 본문 dup 그룹은 chunk_id distinct (정상 패턴)")
    return bad


def check_collection(cur) -> int:
    cur.execute("SELECT name, COUNT(*) FROM langchain_pg_collection GROUP BY 1")
    rows = cur.fetchall()
    _print_header("4) langchain_pg_collection 정상성")
    if not rows:
        print("  FAIL: collection 0행")
        return 1
    abnormal = 0
    for name, cnt in rows:
        flag = "OK" if name == "legal_documents" and cnt == 1 else "WARN"
        if flag == "WARN":
            abnormal += 1
        print(f"  [{flag}] name={name!r}  rows={cnt}")
    if len(rows) > 1:
        print(f"  WARN: collection 다중 ({len(rows)}개)")
    return abnormal


def check_embedding_integrity(cur) -> tuple[int, int]:
    # vector_dims 우선, 미설치 시 fallback
    try:
        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE embedding IS NULL) AS null_emb,
                COUNT(*) FILTER (WHERE embedding IS NOT NULL) AS not_null,
                MIN(vector_dims(embedding)) AS min_dim,
                MAX(vector_dims(embedding)) AS max_dim
            FROM langchain_pg_embedding
            """
        )
        null_emb, not_null, min_dim, max_dim = cur.fetchone()
    except psycopg.errors.UndefinedFunction:
        cur.connection.rollback()
        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE embedding IS NULL) AS null_emb,
                COUNT(*) FILTER (WHERE embedding IS NOT NULL) AS not_null
            FROM langchain_pg_embedding
            """
        )
        null_emb, not_null = cur.fetchone()
        min_dim = max_dim = None

    _print_header("5) embedding NULL / 차원")
    print(f"  null_embedding  : {null_emb:,}")
    print(f"  not_null        : {not_null:,}")
    if min_dim is not None:
        print(f"  vector_dims     : min={min_dim} / max={max_dim}")
        wrong = 0 if min_dim == max_dim else 1
        if wrong:
            print("  FAIL: 차원 불일치")
        else:
            print(f"  OK: 일관 차원 {min_dim}D")
    else:
        print("  WARN: vector_dims() 미설치 - 차원 검증 skip")
        wrong = 0
    return null_emb, wrong


def check_chunks_json_vs_db(cur) -> tuple[int, int, int]:
    _print_header("6) chunks.json vs DB chunk_id 차집합")
    if not CHUNKS_PATH.exists():
        print(f"  WARN: {CHUNKS_PATH} 없음 - skip")
        return 0, 0, 0

    with open(CHUNKS_PATH, encoding="utf-8") as f:
        chunks = json.load(f)
    json_ids = {c.get("metadata", {}).get("chunk_id") for c in chunks}
    json_ids.discard(None)

    cur.execute(
        """
        SELECT DISTINCT cmetadata->>'chunk_id'
        FROM langchain_pg_embedding
        WHERE cmetadata ? 'chunk_id'
        """
    )
    db_ids = {row[0] for row in cur.fetchall()}

    db_only = db_ids - json_ids
    json_only = json_ids - db_ids
    both = db_ids & json_ids

    print(f"  chunks.json chunk_id : {len(json_ids):,}")
    print(f"  DB unique chunk_id   : {len(db_ids):,}")
    print(f"  교집합 (적재됨)       : {len(both):,}")
    print(f"  DB only (유령)       : {len(db_only):,}")
    print(f"  JSON only (미적재)   : {len(json_only):,}")
    if db_only:
        sample = list(db_only)[:5]
        print(f"  유령 sample          : {sample}")
    if json_only:
        sample = list(json_only)[:5]
        print(f"  미적재 sample        : {sample}")
    return len(db_only), len(json_only), len(both)


def check_law_body_fill(cur) -> None:
    _print_header("7) law_legislations / law_precedents 본문 채움률")
    try:
        cur.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM law_legislations) AS leg_total,
                (SELECT COUNT(*) FROM law_legislations WHERE COALESCE(body_text, '') <> '') AS leg_body,
                (SELECT COUNT(*) FROM law_precedents) AS prec_total,
                (SELECT COUNT(*) FROM law_precedents WHERE COALESCE(body_text, '') <> '') AS prec_body
            """
        )
        leg_total, leg_body, prec_total, prec_body = cur.fetchone()
        leg_pct = (leg_body / leg_total * 100) if leg_total else 0
        prec_pct = (prec_body / prec_total * 100) if prec_total else 0
        print(f"  law_legislations : {leg_body:,}/{leg_total:,} ({leg_pct:.1f}%)")
        print(f"  law_precedents   : {prec_body:,}/{prec_total:,} ({prec_pct:.1f}%)")
    except psycopg.errors.UndefinedTable:
        cur.connection.rollback()
        print("  WARN: law_legislations / law_precedents 테이블 없음 - skip")


def main() -> int:
    print(f"DB: {_DEFAULT_DB_URL.split('@')[-1] if '@' in _DEFAULT_DB_URL else _DEFAULT_DB_URL}")
    fail = 0
    with psycopg.connect(_DEFAULT_DB_URL) as conn:
        with conn.cursor() as cur:
            total, uniq, nulls = check_row_vs_unique(cur)
            if total > uniq or nulls > 0:
                fail += 1

            if check_chunk_id_dup(cur) > 0:
                fail += 1

            if check_document_dup(cur) > 0:
                fail += 1

            if check_collection(cur) > 0:
                fail += 1

            null_emb, wrong_dim = check_embedding_integrity(cur)
            if null_emb > 0 or wrong_dim > 0:
                fail += 1

            db_only, _json_only, _both = check_chunks_json_vs_db(cur)
            if db_only > 0:
                fail += 1

            check_law_body_fill(cur)

    _print_header("요약")
    if fail == 0:
        print("  RESULT: PASS - 이상 무")
        return 0
    print(f"  RESULT: FAIL - {fail}개 항목 이상")
    return 1


if __name__ == "__main__":
    sys.exit(main())
