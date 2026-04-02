"""
RAG 문서 검색 — 가맹사업법/상가임대차보호법 문서를 Vector DB에서 검색
"""


class LegalDocumentRetriever:
    """법률 문서 검색기 — Vector DB 기반 RAG"""

    def __init__(self):
        # TODO: Vector DB 클라이언트 초기화 (ChromaDB or Pinecone)
        pass

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        법률 문서 검색

        Args:
            query: 검색 쿼리
            top_k: 반환할 문서 수

        Returns:
            list[dict]: 관련 법률 문서 리스트 (text, metadata, score)
        """
        # TODO: 쿼리 임베딩 생성
        # TODO: Vector DB에서 유사 문서 검색
        # TODO: 결과 정렬 및 반환
        pass

    async def add_documents(self, documents: list[dict]) -> None:
        """
        법률 문서 추가 — Vector DB에 새 문서 인덱싱

        Args:
            documents: 추가할 문서 리스트 (text, metadata)
        """
        # TODO: 문서 청킹
        # TODO: 임베딩 생성
        # TODO: Vector DB에 저장
        pass
