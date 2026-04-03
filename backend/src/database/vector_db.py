"""
ChromaDB 연결 — 가맹사업법, 판례, 분석 리포트 저장/검색 (RAG용)

임베딩 모드 (EMBEDDING_MODE 환경변수로 전환):
- "openai" : OpenAI text-embedding-3-small (기본값, 프로덕션)
- "local"  : sentence-transformers paraphrase-multilingual-MiniLM-L12-v2 (개발용, 무료)

ChromaDB 실행 모드 (CHROMA_PERSIST_DIR 환경변수로 전환):
- 값 있음: PersistentClient — 로컬 파일 저장 (Docker 불필요)
- 비어있음: HttpClient     — Docker chromadb 컨테이너 연결 (프로덕션)
"""
import asyncio
from typing import Optional

import chromadb
import openai

from src.config.settings import settings


class VectorDBClient:
    """ChromaDB 클라이언트 + 임베딩 (OpenAI or 로컬 모델)"""

    OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
    LOCAL_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

    def __init__(
        self,
        collection_name: str = "legal_documents",
        host: str = "chromadb",
        port: int = 8000,
        persist_dir: Optional[str] = None,
    ):
        self.collection_name = collection_name
        self._embedding_mode = settings.embedding_mode

        # ChromaDB 클라이언트 초기화
        if persist_dir:
            # 로컬 개발 모드 — 파일 시스템에 저장 (Docker 불필요)
            self._client = chromadb.PersistentClient(path=persist_dir)
        else:
            # 프로덕션 모드 — HTTP 서버 (Docker chromadb 컨테이너)
            self._client = chromadb.HttpClient(host=host, port=port)

        # 임베딩 클라이언트 초기화
        if self._embedding_mode == "openai":
            self._openai = openai.OpenAI(api_key=settings.openai_api_key)
            self._local_model = None
        else:
            # 로컬 모드 — sentence-transformers (첫 실행 시 모델 자동 다운로드)
            from sentence_transformers import SentenceTransformer
            self._local_model = SentenceTransformer(self.LOCAL_EMBEDDING_MODEL)
            self._openai = None

        # cosine 거리 메트릭 사용 — L2(기본값)보다 문장 임베딩에 적합
        self._collection = self._client.get_or_create_collection(
            collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """
        임베딩 생성 — EMBEDDING_MODE에 따라 OpenAI 또는 로컬 모델 사용

        Args:
            texts: 임베딩할 텍스트 리스트

        Returns:
            list[list[float]]: 임베딩 벡터 리스트
        """
        if self._embedding_mode == "openai":
            response = self._openai.embeddings.create(
                model=self.OPENAI_EMBEDDING_MODEL, input=texts
            )
            return [item.embedding for item in response.data]
        else:
            # sentence-transformers: ndarray → list 변환
            return self._local_model.encode(texts).tolist()

    async def add_documents(self, documents: list[dict], batch_size: int = 100) -> None:
        """
        문서 추가 — 임베딩 생성 후 ChromaDB에 저장 (upsert로 중복 방지)

        Args:
            documents: [{"id": str, "text": str, "metadata": dict}, ...]
            batch_size: 한 번에 임베딩/저장할 문서 수 (OpenAI API 한도 대응)
        """
        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            ids = [doc["id"] for doc in batch]
            texts = [doc["text"] for doc in batch]
            metadatas = [doc["metadata"] for doc in batch]

            embeddings = await asyncio.to_thread(self._embed, texts)
            # upsert: 이미 존재하는 ID는 덮어쓰기 → 재실행 시 DuplicateIDError 방지
            await asyncio.to_thread(
                self._collection.upsert,
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        유사 문서 검색

        Args:
            query: 검색 쿼리
            top_k: 반환할 문서 수

        Returns:
            list[dict]: [{text, metadata, distance}, ...]
        """
        query_embedding = await asyncio.to_thread(self._embed, [query])
        results = await asyncio.to_thread(
            self._collection.query,
            query_embeddings=query_embedding,
            n_results=top_k,
        )

        return [
            {
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            }
            for i in range(len(results["documents"][0]))
        ]

    async def delete_collection(self) -> None:
        """컬렉션 삭제"""
        await asyncio.to_thread(self._client.delete_collection, self.collection_name)
