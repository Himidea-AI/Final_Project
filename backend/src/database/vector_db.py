"""
벡터 DB 클라이언트 — RAG용 문서 저장/검색

클라이언트 종류:
- VectorDBClient    : ChromaDB 기반 (로컬 개발 / 기본값)
- PGVectorDBClient  : pgvector(PostgreSQL) 기반 (프로덕션 대체)
"""

from typing import List, Dict, Any

from langchain_postgres.vectorstores import PGVector
from langchain_huggingface import HuggingFaceEmbeddings
from sqlalchemy.ext.asyncio import create_async_engine
from src.config.settings import settings
from dotenv import load_dotenv

# 커넥션 풀 설정 — 동시 요청 대응
_POOL_SIZE = 10  # 기본 커넥션 수
_MAX_OVERFLOW = 20  # 초과 허용 커넥션 수 (최대 30개 동시 접속)
_POOL_TIMEOUT = 30  # 커넥션 대기 타임아웃(초)
_POOL_PRE_PING = True  # 끊긴 커넥션 자동 재연결

load_dotenv()

_LOCAL_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


class LegalVectorDB:
    """
    지연 초기화 방식의 PGVector 클라이언트 — DEV 모드 완벽 지원

    langchain_postgres (JSONB 스키마) 기반.
    langchain_community.PGVector와 스키마 비호환 — 혼용 금지.
    """

    def __init__(self, collection_name: str = "legal_documents"):
        self.collection_name = collection_name
        self._vectorstore = None
        self._embeddings = None

    @property
    def embeddings(self):
        if self._embeddings is None:
            self._embeddings = HuggingFaceEmbeddings(
                model_name=_LOCAL_EMBEDDING_MODEL,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
        return self._embeddings

    @property
    def vectorstore(self):
        if settings.app_mode == "DEV":
            return None

        if self._vectorstore is None:
            conn_string = settings.postgres_url.replace("postgresql://", "postgresql+psycopg://", 1)
            async_engine = create_async_engine(
                conn_string,
                pool_size=_POOL_SIZE,
                max_overflow=_MAX_OVERFLOW,
                pool_timeout=_POOL_TIMEOUT,
                pool_pre_ping=_POOL_PRE_PING,
            )
            self._vectorstore = PGVector(
                connection=async_engine,
                embeddings=self.embeddings,
                collection_name=self.collection_name,
                use_jsonb=True,
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
        if vs is None:
            return []

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
        if settings.app_mode == "DEV":
            return 42  # Mock count

        try:
            import psycopg2

            # settings에서 주소를 가져옵니다.
            conn = psycopg2.connect(settings.postgres_url)
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM langchain_pg_embedding e "
                "JOIN langchain_pg_collection c ON e.collection_id = c.uuid "
                "WHERE c.name = %s",
                (self.collection_name,),
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
