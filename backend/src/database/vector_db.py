"""
ChromaDB 연결 — 가맹사업법, 판례, 분석 리포트 저장/검색 (RAG용)

임베딩: OpenAI text-embedding-3-small API 사용 (sentence-transformers 미사용)
Vector DB: ChromaDB 단독 사용 (Pinecone 미사용)
"""


class VectorDBClient:
    """ChromaDB 클라이언트 + OpenAI 임베딩"""

    EMBEDDING_MODEL = "text-embedding-3-small"

    def __init__(self, collection_name: str = "legal_documents", host: str = "chromadb", port: int = 8000):
        self.collection_name = collection_name
        self.host = host
        self.port = port
        # TODO: chromadb.HttpClient(host, port) 초기화
        # TODO: openai.OpenAI() 클라이언트 초기화 (임베딩용)
        # TODO: collection = client.get_or_create_collection(collection_name)

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """
        OpenAI text-embedding-3-small로 임베딩 생성

        Args:
            texts: 임베딩할 텍스트 리스트

        Returns:
            list[list[float]]: 임베딩 벡터 리스트
        """
        # TODO: openai_client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
        # TODO: 응답에서 벡터 추출
        pass

    async def add_documents(self, documents: list[dict]) -> None:
        """
        문서 추가 — OpenAI 임베딩 생성 후 ChromaDB에 저장

        Args:
            documents: [{"id": str, "text": str, "metadata": dict}, ...]
        """
        # TODO: 텍스트 추출 → _embed()로 임베딩
        # TODO: collection.add(ids, embeddings, documents, metadatas)
        pass

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        유사 문서 검색

        Args:
            query: 검색 쿼리
            top_k: 반환할 문서 수

        Returns:
            list[dict]: [{text, metadata, distance}, ...]
        """
        # TODO: 쿼리 임베딩 → collection.query(query_embeddings, n_results)
        pass

    async def delete_collection(self) -> None:
        """컬렉션 삭제"""
        # TODO: client.delete_collection(collection_name)
        pass
