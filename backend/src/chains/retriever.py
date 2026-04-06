"""
RAG 문서 검색 — 가맹사업법/상가임대차보호법 문서를 Vector DB에서 검색
"""
import json
from pathlib import Path

from src.config.settings import settings
from src.database.vector_db import VectorDBClient

# 거리 임계값 (cosine distance 기준: 0=동일, 1=직교, 2=반대)
# 1.0 초과 = 반대 방향 벡터, 사실상 무관한 문서
DISTANCE_THRESHOLD = 1.0


class LegalDocumentRetriever:
    """법률 문서 검색기 — Vector DB 기반 RAG"""

    def __init__(self):
        self._db = VectorDBClient(
            collection_name="legal_documents",
            host=settings.chroma_host,
            port=settings.chroma_port,
            persist_dir=settings.chroma_persist_dir or None,
        )

    # 청크가 인덱싱된 source 메타데이터 값 (parse_pdfs.py의 파일명 stem과 일치)
    FRANCHISE_LAW_SOURCES = [
        "가맹사업거래의 공정화에 관한 법률(법률)(제20712호)(20250121)",
        "가맹사업거래의 공정화에 관한 법률 시행령(대통령령)(제36220호)(20260324)",
    ]
    LEASE_LAW_SOURCES = [
        "상가건물 임대차보호법(법률)(제21065호)(20260102)",
        "상가건물 임대차보호법 시행령(대통령령)(제35947호)(20260102)",
        "서울시_2023_상가임대차_상담사례집_내지_전자책",
    ]
    MAPO_SOURCES = [
        "서울특별시 마포구 지역상권 상생협력에 관한 조례",
    ]

    async def search(
        self,
        query: str,
        top_k: int = 5,
        source_filter: list[str] | None = None,
    ) -> list[dict]:
        """
        법률 문서 검색

        Args:
            query: 검색 쿼리
            top_k: 반환할 문서 수
            source_filter: 검색할 source 목록 (None이면 전체 검색)
                           예) LegalDocumentRetriever.FRANCHISE_LAW_SOURCES

        Returns:
            list[dict]: 관련 법률 문서 리스트 (text, metadata, score)
            score는 0~1 범위, 1에 가까울수록 관련도 높음
        """
        where: dict | None = None
        if source_filter and len(source_filter) == 1:
            # 단일 소스 — ChromaDB $eq 연산자
            where = {"source": {"$eq": source_filter[0]}}
        elif source_filter and len(source_filter) > 1:
            # 복수 소스 — ChromaDB $in 연산자
            where = {"source": {"$in": source_filter}}

        results = await self._db.search(query, top_k=top_k, where=where)

        # 거리 임계값 초과 항목 제거 후 score로 변환
        filtered = [
            {
                "text": r["text"],
                "metadata": r["metadata"],
                # cosine distance → similarity score (0~1)
                "score": round(1 - r["distance"] / 2, 4),
            }
            for r in results
            if r["distance"] < DISTANCE_THRESHOLD
        ]

        # score 내림차순 정렬
        filtered.sort(key=lambda x: x["score"], reverse=True)
        return filtered

    async def add_documents(self, documents: list[dict]) -> None:
        """
        법률 문서 추가 — Vector DB에 새 문서 인덱싱

        Args:
            documents: [{"id": str, "text": str, "metadata": dict}, ...]
        """
        await self._db.add_documents(documents)

    async def ingest_from_json(self, json_path: str | Path) -> int:
        """
        processed/chunks.json을 읽어 ChromaDB에 일괄 적재

        parse_pdfs.py 실행 후 이 메서드로 인덱싱하는 흐름:
            1. python data/legal/parse_pdfs.py
            2. retriever.ingest_from_json("data/legal/processed/chunks.json")

        Args:
            json_path: chunks.json 경로

        Returns:
            int: 적재된 청크 수
        """
        with open(json_path, encoding="utf-8") as f:
            chunks = json.load(f)

        await self.add_documents(chunks)
        return len(chunks)
