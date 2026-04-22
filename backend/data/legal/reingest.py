"""
임베딩 모델 교체 후 재인덱싱 스크립트

기존 컬렉션 삭제 → 새 임베딩으로 전체 재적재
실행: cd backend && python data/legal/reingest.py
"""

import json
import os
import sys
import selectors
import asyncio
from pathlib import Path

# Windows 이벤트 루프 호환
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from dotenv import load_dotenv
load_dotenv()

CHUNKS_PATH = Path(__file__).parent / "processed" / "chunks.json"
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://postgres:postgres@db:5432/mapo_simulator")
COLLECTION = "legal_documents"
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
BATCH_SIZE = 50


def main() -> None:
    import psycopg2

    # 1) 기존 컬렉션 + 임베딩 테이블 완전 삭제 (차원 384→1024 변경)
    print("pgvector embedding table drop + recreate...")
    try:
        conn = psycopg2.connect(POSTGRES_URL)
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS langchain_pg_embedding CASCADE")
        cur.execute("DROP TABLE IF EXISTS langchain_pg_collection CASCADE")
        conn.commit()
        print("  tables dropped")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"  drop failed (continuing): {e}")

    # 2) 임베딩 모델 로드
    from langchain_huggingface import HuggingFaceEmbeddings

    print(f"임베딩 모델 로딩: {MODEL_NAME}")
    embeddings = HuggingFaceEmbeddings(
        model_name=MODEL_NAME,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    # 테스트 임베딩
    test_vec = embeddings.embed_query("테스트")
    print(f"  임베딩 차원: {len(test_vec)}D")

    # 3) chunks.json 로드
    print(f"chunks.json 로딩: {CHUNKS_PATH}")
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        chunks = json.load(f)
    print(f"  총 {len(chunks)}개 청크")

    from langchain_core.documents import Document
    from langchain_postgres.vectorstores import PGVector

    docs = [Document(page_content=c["text"], metadata=c["metadata"]) for c in chunks]

    conn_string = POSTGRES_URL.replace("postgresql://", "postgresql+psycopg://", 1)

    # 4) 첫 번째 문서로 컬렉션 생성
    print("새 컬렉션 생성 + 첫 문서 적재...")
    vectorstore = PGVector.from_documents(
        documents=docs[:1],
        embedding=embeddings,
        collection_name=COLLECTION,
        connection=conn_string,
        use_jsonb=True,
    )

    # 5) 나머지 배치 적재
    remaining = docs[1:]
    total = len(docs)
    print(f"배치 적재 시작 ({BATCH_SIZE}개씩)...")
    for i in range(0, len(remaining), BATCH_SIZE):
        batch = remaining[i : i + BATCH_SIZE]
        vectorstore.add_documents(batch)
        done = min(i + BATCH_SIZE + 1, total)
        print(f"  {done}/{total} ({done * 100 // total}%)")

    print(f"\n완료: {total}개 청크를 {MODEL_NAME} ({len(test_vec)}D) 임베딩으로 적재")


if __name__ == "__main__":
    main()
