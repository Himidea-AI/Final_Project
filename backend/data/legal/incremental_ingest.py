"""신규 chunk_id만 임베딩 + upsert (메모리 절약).

reingest.py는 10341 청크 전량 임베딩 후 upsert → 메모리 폭발 (SIGSEGV).
이 스크립트는:
- DB 기존 chunk_id 조회
- chunks.json에서 신규 chunk_id만 추출
- 작은 batch + 즉시 upsert (메모리 streaming)
- gc.collect() 명시 호출

ghost 청크 삭제는 reingest.py에 위임. 여기는 add-only.
"""

from __future__ import annotations

import gc
import json
import os
import sys
import uuid
from pathlib import Path

if sys.platform == "win32":
    import asyncio

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from data.legal.reingest import (  # noqa: E402
    COLLECTION,
    MODEL_NAME,
    _ensure_collection,
    _fetch_existing_chunk_ids,
    _upsert_batch,
)

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://postgres:postgres@localhost:5432/mapo_simulator")
CHUNKS_PATH = Path(__file__).parent / "processed" / "chunks.json"
BATCH_SIZE = 16  # 작게 — bge-m3 CPU 메모리 안정


def main() -> None:
    import psycopg
    from langchain_huggingface import HuggingFaceEmbeddings

    print(f"chunks.json: {CHUNKS_PATH}")
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        chunks = json.load(f)
    print(f"  총 청크: {len(chunks)}")

    with psycopg.connect(POSTGRES_URL) as conn:
        collection_id = _ensure_collection(conn, COLLECTION)
        existing = _fetch_existing_chunk_ids(conn, collection_id)
        print(f"  DB 기존 chunk_id: {len(existing)}")

    # 신규만 필터
    new_chunks = [c for c in chunks if c["metadata"]["chunk_id"] not in existing]
    print(f"  신규 청크: {len(new_chunks)}")
    if not new_chunks:
        print("신규 청크 없음. 종료.")
        return

    print(f"임베딩 모델: {MODEL_NAME}")
    embeddings = HuggingFaceEmbeddings(
        model_name=MODEL_NAME,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True, "batch_size": 8},
    )

    print(f"증분 임베딩+upsert 시작 (배치 {BATCH_SIZE})...")
    with psycopg.connect(POSTGRES_URL) as conn:
        for i in range(0, len(new_chunks), BATCH_SIZE):
            batch = new_chunks[i : i + BATCH_SIZE]
            texts = [c["text"] for c in batch]
            vectors = embeddings.embed_documents(texts)

            with conn.transaction():
                _upsert_batch(conn, collection_id, batch, vectors)

            done = min(i + BATCH_SIZE, len(new_chunks))
            if done % (BATCH_SIZE * 10) == 0 or done == len(new_chunks):
                pct = done * 100 // len(new_chunks)
                print(f"  진행 {done}/{len(new_chunks)} ({pct}%)")

            del vectors, texts, batch
            if i % (BATCH_SIZE * 50) == 0:
                gc.collect()

    print(f"\n완료: 신규 {len(new_chunks)}개 청크 추가")
    # 최종 행 수
    with psycopg.connect(POSTGRES_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM langchain_pg_embedding WHERE collection_id = %s",
                (collection_id,),
            )
            total = cur.fetchone()[0]
    print(f"DB 최종 행 수: {total}")


if __name__ == "__main__":
    main()
