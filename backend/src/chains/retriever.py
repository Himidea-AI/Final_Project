"""
RAG 문서 검색 — 가맹사업법/상가임대차보호법 문서를 Vector DB에서 검색
"""

import json
from pathlib import Path

from ..database.vector_db import LegalVectorDB


class LegalDocumentRetriever:
    """법률 문서 검색기 — pgvector 기반 RAG"""

    def __init__(self):
        self._db = LegalVectorDB()

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
    FOOD_HYGIENE_SOURCES = [
        "식품위생법(법률)(제21065호)(20251001)",
        "식품위생법 시행규칙(총리령)(제02077호)(20260301)",
        "[한국외식업중앙회] 2026 위생교육교재 (표지 포함)",
    ]
    SAFETY_SOURCES = [
        "210226_ 「다중이용업소의 안전관리에 관한 특별법」업무처리 지침",
        "제4차(2024~2028) 다중이용업소 안전관리 기본계획(전문)",
    ]
    BUILDING_LAW_SOURCES = [
        "건축법(법률)(20250101)",
    ]
    FIRE_SAFETY_SOURCES = [
        "소방시설 설치 및 관리에 관한 법률(법률)(20250101)",
    ]
    LABOR_LAW_SOURCES = [
        "근로기준법(법률)(20250101)",
        "최저임금법(법률)(제17326호)(20200526)",
    ]
    VAT_LAW_SOURCES = [
        "부가가치세법(법률)(제21065호)(20260102)",
    ]
    PRIVACY_LAW_SOURCES = [
        "개인정보 보호법(법률)(제20897호)(20251002)",
    ]
    ACCESSIBILITY_LAW_SOURCES = [
        "장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률(법률)(제20594호)(20251221)",
    ]
    FAIR_TRADE_SOURCES = [
        "독점규제 및 공정거래에 관한 법률(법률)(제21066호)(20251001)",
    ]
    SEWAGE_LAW_SOURCES = [
        "하수도법(법률)(제21065호)(20251001)",
        "물환경보전법(법률)(제21368호)(20260219)",
    ]
    LIQUOR_LAW_SOURCES = [
        "주세법(법률)(제20618호)(20250101)",
    ]

    async def search(
        self,
        query: str,
        top_k: int = 5,
        source_filter: list[str] | None = None,
    ) -> list[dict]:
        """
        법률 문서 검색

        검색 결과가 0건이면 source_filter를 제거하고 전체 컬렉션에서 fallback 재검색.

        Args:
            query: 검색 쿼리
            top_k: 반환할 문서 수
            source_filter: 검색할 source 목록 (None이면 전체 검색)
                           예) LegalDocumentRetriever.FRANCHISE_LAW_SOURCES

        Returns:
            list[dict]: 관련 법률 문서 리스트
            반환 형식: {"content": str, "metadata": {"source": ..., "relevance": float, ...}}
            relevance는 0~1 범위, 1에 가까울수록 관련도 높음
        """
        vs = self._db.vectorstore
        if vs is None:
            return []

        filter_dict = {"source": {"$in": source_filter}} if source_filter else None
        docs_with_score = await vs.asimilarity_search_with_relevance_scores(query, k=top_k, filter=filter_dict)

        # 결과 0건이고 source_filter가 있었으면 필터 없이 fallback 재검색
        if not docs_with_score and source_filter:
            docs_with_score = await vs.asimilarity_search_with_relevance_scores(query, k=top_k)

        results = [
            {
                "content": doc.page_content,
                "metadata": {
                    **doc.metadata,
                    "relevance": round(score, 4),
                },
            }
            for doc, score in docs_with_score
        ]
        results.sort(key=lambda x: x["metadata"]["relevance"], reverse=True)
        return results

    async def ingest_from_json(self, json_path: str | Path) -> int:
        """
        processed/chunks.json을 읽어 pgvector에 일괄 적재

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

        from langchain_core.documents import Document

        docs = [Document(page_content=c["text"], metadata=c["metadata"]) for c in chunks]

        vs = self._db.vectorstore
        await vs.aadd_documents(docs)
        return len(docs)
