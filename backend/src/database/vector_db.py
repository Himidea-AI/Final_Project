"""
벡터 DB 클라이언트 — RAG용 문서 저장/검색

클라이언트 종류:
- VectorDBClient    : ChromaDB 기반 (로컬 개발 / 기본값)
- PGVectorDBClient  : pgvector(PostgreSQL) 기반 (프로덕션 대체)
"""

import os
import asyncio
import concurrent.futures
import json
from typing import List, Dict, Any, Optional

import chromadb
import openai
from langchain_community.vectorstores import PGVector
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from src.config.settings import settings
from dotenv import load_dotenv

# [보강] settings 모듈에서 이미 로드했을 수 있으나, 만약을 위해 호출 유지
load_dotenv()

class VectorDBClient:
    """
    ChromaDB 기반 벡터 DB 클라이언트.
    """
    def __init__(
        self,
        collection_name: str,
        host: Optional[str] = None,
        port: Optional[int] = None,
        persist_dir: Optional[str] = None,
    ):
        self.collection_name = collection_name
        self._embedding_mode = settings.embedding_mode

        # DEV 모드에서는 HttpClient 사용 시도 자체를 건너뜁니다.
        if settings.app_mode == "DEV":
            print("DEBUG: [VectorDBClient] DEV 모드 - ChromaDB 연결을 건너뜁니다.")
            self._client = None
            self._collection = None
            return

        if persist_dir:
            self._client = chromadb.PersistentClient(path=persist_dir)
        else:
            self._client = chromadb.HttpClient(
                host=host or settings.chroma_host, 
                port=port or settings.chroma_port
            )
        self._collection = self._client.get_or_create_collection(name=collection_name)

        # 임베딩 초기화
        if self._embedding_mode == "openai":
            self._openai = openai.OpenAI(api_key=settings.openai_api_key)
            self._local_model = None
        else:
            from sentence_transformers import SentenceTransformer
            self._local_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            self._openai = None

    async def search(self, query: str, top_k: int = 5) -> list:
        if settings.app_mode == "DEV": 
            return [{"text": "Mock Data", "metadata": {}, "distance": 0.1}]
        # ... (이후 로직 생략)
        return []

class LegalVectorDB:
    """
    지연 초기화 방식의 PGVector 클라이언트 — DEV 모드 완벽 지원
    """
    def __init__(self, collection_name: str = "legal_documents"):
        self.collection_name = collection_name
        self._vectorstore = None
        self._embeddings = None

    @property
    def embeddings(self):
        if self._embeddings is None:
            # 설정에서 API 키를 가져옵니다.
            google_api_key = settings.google_api_key
            self._embeddings = GoogleGenerativeAIEmbeddings(
                model="models/text-embedding-004",
                google_api_key=google_api_key,
            )
        return self._embeddings

    @property
    def vectorstore(self):
        # DEV 모드일 때는 PGVector 인스턴스 생성을 시도하지도 않습니다. (psycopg2 에러 방지)
        if settings.app_mode == "DEV":
            return None

        if self._vectorstore is None:
            # settings에서 실시간으로 연결 주소를 가져옵니다.
            conn_string = settings.postgres_url
            self._vectorstore = PGVector(
                connection_string=conn_string,
                embedding_function=self.embeddings,
                collection_name=self.collection_name,
                # [중요] 외부에서 PGVector를 로드할 때 확장 프로그램 설치를 시도하지 않도록 할 수 있으나
                # 여기서는 연결 자체를 안 하는 것이 핵심입니다.
            )
        return self._vectorstore

    async def asearch_legal_docs(self, query: str, search_k: int = 5) -> List[Dict[str, Any]]:
        # [강화] PGVector 호출 전 다시 한번 DEV 체크
        if settings.app_mode == "DEV":
            print("DEBUG: [LegalVectorDB] DEV 모드 - Mock 데이터를 반환합니다.")
            return [
                {
                    "content": "상가건물 임대차보호법 (DEV 모드 가짜 데이터): 임대료 인상 제한 및 권리금 보호 가이드라인",
                    "metadata": {"source": "법률 가이드", "relevance": 1.0},
                }
            ]
            
        vs = self.vectorstore
        if vs is None: return []

        try:
            docs_with_score = await vs.asimilarity_search_with_relevance_scores(query, k=search_k)
            return [
                {
                    "content": doc.page_content,
                    "metadata": {**doc.metadata, "relevance": round(score, 2)},
                }
                for doc, score in docs_with_score
            ]
        except Exception as e:
            print(f"!!! [VECTOR DB ERROR] !!! {str(e)}")
            return []

    def get_total_count(self) -> int:
        # DEV 모드에서는 DB 접속 없이 즉시 반환
        if settings.app_mode == "DEV": return 42 # Mock count

        try:
            import psycopg2
            # settings에서 주소를 가져옵니다.
            conn = psycopg2.connect(settings.postgres_url)
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM langchain_pg_embedding e "
                "JOIN langchain_pg_collection c ON e.collection_id = c.uuid "
                "WHERE c.name = %s",
                (self.collection_name,)
            )
            count = cur.fetchone()[0]
            cur.close()
            conn.close()
            return count
        except Exception as e:
            print(f"DEBUG: DB Count 조회 실패 - {str(e)}")
            return 0

# 싱글톤 인터페이스 제공
legal_db = LegalVectorDB()
