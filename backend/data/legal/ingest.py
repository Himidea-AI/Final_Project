"""
법률 문서 ingest 스크립트 — chunks.json → pgvector

실행 방법 (Docker):
    docker run --rm -v <project>:/app --network <net> python:3.12-slim \
        bash -c "cd /app/backend && pip install ... && python data/legal/ingest.py"

환경변수:
    POSTGRES_URL: PostgreSQL 연결 주소 (기본: postgresql://postgres:postgres@db:5432/mapo_simulator)
"""
import json
import os
import sys
from pathlib import Path

CHUNKS_PATH = Path(__file__).parent / "processed" / "chunks.json"
POSTGRES_URL = os.getenv(
    "POSTGRES_URL", "postgresql://postgres:postgres@db:5432/mapo_simulator"
)
COLLECTION = "legal_documents"
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
BATCH_SIZE = 100


def main() -> None:
    from langchain_community.vectorstores import PGVector
    from langchain_core.documents import Document
    from langchain_huggingface import HuggingFaceEmbeddings

    print(f"임베딩 모델 로딩: {MODEL_NAME}")
    embeddings = HuggingFaceEmbeddings(
        model_name=MODEL_NAME,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    print(f"chunks.json 로딩: {CHUNKS_PATH}")
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        chunks = json.load(f)
    print(f"총 {len(chunks)}개 청크")

    docs = [Document(page_content=c["text"], metadata=c["metadata"]) for c in chunks]

    print("pgvector 컬렉션 초기화 (기존 데이터 삭제 후 재적재)")
    vectorstore = PGVector.from_documents(
        documents=docs[:1],
        embedding=embeddings,
        collection_name=COLLECTION,
        connection_string=POSTGRES_URL,
        pre_delete_collection=True,
    )

    print(f"배치 크기 {BATCH_SIZE}로 나머지 적재 중...")
    remaining = docs[1:]
    for i in range(0, len(remaining), BATCH_SIZE):
        batch = remaining[i : i + BATCH_SIZE]
        vectorstore.add_documents(batch)
        print(f"  {i + 1 + 1} / {len(docs)} 완료", end="\r")

    print(f"\n완료: 총 {len(docs)}개 청크 pgvector 적재")


if __name__ == "__main__":
    main()
