"""
법률 청크 idempotent upsert 스크립트

chunks.json 기준으로 langchain_pg_embedding 동기화:
- 신규 chunk_id → INSERT
- 기존 chunk_id, 내용 변경 → UPDATE (ON CONFLICT)
- chunks.json에 없는 chunk_id → DELETE (유령 정리)

전제:
- alembic upgrade head 적용 완료 (uq_legal_chunk_id 인덱스 존재)
- chunks.json 모든 청크에 metadata.chunk_id 포함

실행:
    cd backend && python -m data.legal.reingest

환경변수:
    POSTGRES_URL: PostgreSQL 연결 주소
"""

import asyncio
import json
import os
import sys
import uuid
from collections.abc import Iterable
from pathlib import Path

# Windows 이벤트 루프 호환
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from dotenv import load_dotenv

load_dotenv()

CHUNKS_PATH = Path(__file__).parent / "processed" / "chunks.json"
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://postgres:postgres@db:5432/mapo_simulator")
COLLECTION = "legal_documents"
MODEL_NAME = "BAAI/bge-m3"
BATCH_SIZE = 50


def _load_chunks() -> list[dict]:
    print(f"chunks.json 로딩: {CHUNKS_PATH}")
    if not CHUNKS_PATH.exists():
        raise FileNotFoundError(f"{CHUNKS_PATH} 없음. 먼저 parse_pdfs.py 실행하세요.")
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        chunks = json.load(f)

    # 사전 검증: chunk_id 모든 청크에 존재
    missing = [i for i, c in enumerate(chunks) if not c.get("metadata", {}).get("chunk_id")]
    if missing:
        raise ValueError(f"chunk_id 누락 {len(missing)}개 청크. parse_pdfs.py 재실행 필요. 예: index {missing[:3]}")
    print(f"  총 {len(chunks)}개 청크 (모두 chunk_id 있음)")
    return chunks


def _load_embeddings():
    from langchain_huggingface import HuggingFaceEmbeddings

    print(f"임베딩 모델 로딩: {MODEL_NAME}")
    embeddings = HuggingFaceEmbeddings(
        model_name=MODEL_NAME,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    test_vec = embeddings.embed_query("테스트")
    print(f"  임베딩 차원: {len(test_vec)}D")
    return embeddings


def _ensure_indexes(conn) -> None:
    """alembic migration의 인덱스가 사라졌을 때 (DROP CASCADE 후) 재생성. 멱등."""
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_legal_chunk_id
            ON langchain_pg_embedding ((cmetadata->>'chunk_id'))
            WHERE cmetadata ? 'chunk_id'
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_legal_cmetadata_gin
            ON langchain_pg_embedding USING GIN (cmetadata jsonb_path_ops)
            """
        )
        conn.commit()
    print("  인덱스 OK (uq_legal_chunk_id, idx_legal_cmetadata_gin)")


def _ensure_collection(conn, name: str) -> str:
    """legal_documents 컬렉션 확보. 테이블 없으면 LangChain PGVector로 초기화.

    반환: collection_id (uuid str)
    """
    import psycopg

    # 1) 기존 컬렉션 조회 시도. 테이블 없으면 UndefinedTable → 초기화 경로
    needs_init = False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT uuid FROM langchain_pg_collection WHERE name = %s",
                (name,),
            )
            row = cur.fetchone()
            if row:
                _ensure_indexes(conn)
                return str(row[0])
    except psycopg.errors.UndefinedTable:
        # 테이블 자체 없음 — DROP CASCADE 직후 시나리오
        conn.rollback()
        needs_init = True

    # 2) 테이블 또는 collection 없음 → LangChain이 테이블 생성하도록 빈 적재 1회
    from langchain_core.documents import Document
    from langchain_postgres.vectorstores import PGVector

    if needs_init:
        print("  langchain_pg_* 테이블 없음 - LangChain으로 신규 생성")
    else:
        print(f"  컬렉션 '{name}' 신규 생성")

    conn_string = POSTGRES_URL.replace("postgresql://", "postgresql+psycopg://", 1)
    embeddings = _load_embeddings()
    PGVector.from_documents(
        documents=[Document(page_content="__init__", metadata={"__init__": True})],
        embedding=embeddings,
        collection_name=name,
        connection=conn_string,
        use_jsonb=True,
    )

    # 테이블 생성 후 인덱스 재구성 (alembic migration 효과 복구)
    _ensure_indexes(conn)

    # 더미 행 즉시 삭제
    with conn.cursor() as cur:
        cur.execute("DELETE FROM langchain_pg_embedding WHERE cmetadata ? '__init__'")
        conn.commit()
        cur.execute("SELECT uuid FROM langchain_pg_collection WHERE name = %s", (name,))
        row = cur.fetchone()
    if not row:
        raise RuntimeError(f"컬렉션 '{name}' 생성 실패")
    return str(row[0])


def _fetch_existing_chunk_ids(conn, collection_id: str) -> set[str]:
    """현재 DB에 적재된 chunk_id 집합 조회"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT cmetadata->>'chunk_id'
            FROM langchain_pg_embedding
            WHERE collection_id = %s AND cmetadata ? 'chunk_id'
            """,
            (collection_id,),
        )
        return {row[0] for row in cur.fetchall() if row[0]}


def _upsert_batch(conn, collection_id: str, chunks: list[dict], vectors: list[list[float]]) -> None:
    """ON CONFLICT 기반 upsert.

    부분 UNIQUE 인덱스 (uq_legal_chunk_id)를 사용:
    INSERT ... ON CONFLICT ((cmetadata->>'chunk_id')) WHERE cmetadata ? 'chunk_id' DO UPDATE
    """
    sql = """
        INSERT INTO langchain_pg_embedding
            (id, collection_id, embedding, document, cmetadata)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT ((cmetadata->>'chunk_id')) WHERE cmetadata ? 'chunk_id'
        DO UPDATE SET
            embedding = EXCLUDED.embedding,
            document = EXCLUDED.document,
            cmetadata = EXCLUDED.cmetadata
    """
    with conn.cursor() as cur:
        for chunk, vec in zip(chunks, vectors, strict=True):
            cur.execute(
                sql,
                (
                    str(uuid.uuid4()),
                    collection_id,
                    vec,
                    chunk["text"],
                    json.dumps(chunk["metadata"], ensure_ascii=False),
                ),
            )


def _delete_by_chunk_ids(conn, collection_id: str, chunk_ids: Iterable[str]) -> int:
    """유령 chunk_id 일괄 삭제. 반환: 삭제 행 수."""
    ids = list(chunk_ids)
    if not ids:
        return 0
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM langchain_pg_embedding
            WHERE collection_id = %s
              AND cmetadata->>'chunk_id' = ANY(%s)
            """,
            (collection_id, ids),
        )
        return cur.rowcount


def _verify_invariants(conn, collection_id: str, expected: int) -> None:
    """SP1 정합성 4가지 invariant 검증. 위반 시 AssertionError."""
    with conn.cursor() as cur:
        # 1) NULL chunk_id 0건
        cur.execute(
            """
            SELECT COUNT(*) FROM langchain_pg_embedding
            WHERE collection_id = %s AND (cmetadata->>'chunk_id') IS NULL
            """,
            (collection_id,),
        )
        null_count = cur.fetchone()[0]
        assert null_count == 0, f"chunk_id NULL인 행 {null_count}개"

        # 2) chunk_id UNIQUE
        cur.execute(
            """
            SELECT COUNT(*) - COUNT(DISTINCT cmetadata->>'chunk_id')
            FROM langchain_pg_embedding
            WHERE collection_id = %s
            """,
            (collection_id,),
        )
        dup_count = cur.fetchone()[0]
        assert dup_count == 0, f"chunk_id 중복 {dup_count}건"

        # 3) 행 수 = chunks.json 청크 수
        cur.execute(
            "SELECT COUNT(*) FROM langchain_pg_embedding WHERE collection_id = %s",
            (collection_id,),
        )
        actual = cur.fetchone()[0]
        assert actual == expected, f"DB={actual} vs chunks.json={expected}"

    print(f"  invariants OK ({actual}행, 모두 unique chunk_id)")


def main() -> None:
    import psycopg

    chunks = _load_chunks()
    embeddings = _load_embeddings()
    new_ids = {c["metadata"]["chunk_id"] for c in chunks}

    # 임베딩 일괄 계산 (CPU 모델, 5K 청크 ~ 분 단위)
    print(f"임베딩 계산 시작 (배치 {BATCH_SIZE})...")
    texts = [c["text"] for c in chunks]
    vectors: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        vectors.extend(embeddings.embed_documents(batch))
        done = min(i + BATCH_SIZE, len(texts))
        print(f"  임베딩 {done}/{len(texts)} ({done * 100 // len(texts)}%)")

    with psycopg.connect(POSTGRES_URL) as conn:
        collection_id = _ensure_collection(conn, COLLECTION)
        existing_ids = _fetch_existing_chunk_ids(conn, collection_id)
        ghost_ids = existing_ids - new_ids
        print(f"  기존 chunk_id {len(existing_ids)}개 / 신규 chunk_id {len(new_ids)}개 / 유령 {len(ghost_ids)}개")

        # 트랜잭션: upsert + ghost 삭제를 원자적으로
        with conn.transaction():
            print(f"upsert 시작 (배치 {BATCH_SIZE})...")
            for i in range(0, len(chunks), BATCH_SIZE):
                batch_chunks = chunks[i : i + BATCH_SIZE]
                batch_vectors = vectors[i : i + BATCH_SIZE]
                _upsert_batch(conn, collection_id, batch_chunks, batch_vectors)
                done = min(i + BATCH_SIZE, len(chunks))
                print(f"  upsert {done}/{len(chunks)} ({done * 100 // len(chunks)}%)")

            if ghost_ids:
                deleted = _delete_by_chunk_ids(conn, collection_id, ghost_ids)
                print(f"유령 청크 {deleted}개 삭제")

        _verify_invariants(conn, collection_id, expected=len(chunks))

    print(f"\n완료: {len(chunks)}개 청크 동기화 ({MODEL_NAME})")


if __name__ == "__main__":
    main()
