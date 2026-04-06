"""
ChromaDB 인제스트 스크립트 — A2 담당

사용법:
    # 프로젝트 루트에서 실행
    python data/legal/ingest_to_chroma.py

    # 로컬 임베딩 모드 (OpenAI API 키 불필요)
    EMBEDDING_MODE=local python data/legal/ingest_to_chroma.py

전제 조건:
    - data/legal/parse_pdfs.py 를 먼저 실행해서 chunks.json 이 생성되어 있어야 함
    - .env 에 CHROMA_PERSIST_DIR=data/chroma_local 설정 (로컬 개발)
      또는 chromadb 컨테이너가 실행 중이어야 함 (Docker 환경)
"""

import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (backend/src 임포트를 위해)
ROOT = Path(__file__).resolve().parents[2]  # Final_Project/
sys.path.insert(0, str(ROOT / "backend"))

from src.chains.retriever import LegalDocumentRetriever  # noqa: E402

CHUNKS_PATH = Path(__file__).parent / "processed" / "chunks.json"


async def main() -> None:
    if not CHUNKS_PATH.exists():
        print(f"[오류] {CHUNKS_PATH} 파일이 없습니다.")
        print("  → 먼저 python data/legal/parse_pdfs.py 를 실행하세요.")
        sys.exit(1)

    retriever = LegalDocumentRetriever()
    print(f"[인제스트 시작] {CHUNKS_PATH}")

    count = await retriever.ingest_from_json(CHUNKS_PATH)

    print(f"[완료] {count}개 청크를 ChromaDB에 적재했습니다.")
    print("이제 retriever.search(query) 로 검색할 수 있습니다.")


if __name__ == "__main__":
    asyncio.run(main())
