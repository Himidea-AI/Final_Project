"""
벡터 DB 클라이언트 — RAG용 문서 저장/검색

클라이언트 종류:
- VectorDBClient    : ChromaDB 기반 (로컬 개발 / 기본값)
- PGVectorDBClient  : pgvector(PostgreSQL) 기반 (프로덕션 대체)
"""

from langchain_postgres.vectorstores import PGVector
from langchain_huggingface import HuggingFaceEmbeddings
from sqlalchemy.ext.asyncio import create_async_engine
from src.config.settings import settings
from dotenv import load_dotenv

# 커넥션 풀 설정 — RDS max_connections=81 제약 고려
# db_client(market/ranking)가 별도 풀을 사용하므로 RAG용은 최소화
_POOL_SIZE = 3  # 기본 커넥션 수 (10→3 축소)
_MAX_OVERFLOW = 5  # 초과 허용 커넥션 수 (20→5 축소, 최대 8개)
_POOL_TIMEOUT = 30  # 커넥션 대기 타임아웃(초)
_POOL_PRE_PING = True  # 끊긴 커넥션 자동 재연결

load_dotenv()

_LOCAL_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


# 모듈 레벨 싱글톤 — 매 요청마다 엔진/임베딩 재생성 방지
_singleton_instance: "LegalVectorDB | None" = None


class LegalVectorDB:
    """
    지연 초기화 방식의 PGVector 클라이언트 — DEV 모드 완벽 지원

    langchain_postgres (JSONB 스키마) 기반.
    langchain_community.PGVector와 스키마 비호환 — 혼용 금지.
    싱글톤: 동일 collection_name이면 엔진/임베딩을 재사용.
    """

    def __new__(cls, collection_name: str = "legal_documents"):
        global _singleton_instance
        if _singleton_instance is None or _singleton_instance.collection_name != collection_name:
            _singleton_instance = super().__new__(cls)
            _singleton_instance.collection_name = collection_name
            _singleton_instance._vectorstore = None
            _singleton_instance._embeddings = None
        return _singleton_instance

    def __init__(self, collection_name: str = "legal_documents"):
        # __new__에서 이미 초기화됨 — 중복 초기화 방지
        pass

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
        if self._vectorstore is None:
            if not settings.postgres_url:
                print("[LegalVectorDB] WARNING: POSTGRES_URL이 설정되지 않아 RAG 검색을 사용할 수 없습니다.")
                return None
            try:
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
            except Exception as e:
                print(f"[LegalVectorDB] WARNING: PGVector 초기화 실패 - RAG 검색 불가 ({e})")
                return None
        return self._vectorstore

    def get_total_count(self) -> int:
        if not settings.postgres_url:
            print("[LegalVectorDB] WARNING: POSTGRES_URL이 설정되지 않아 count 조회를 건너뜁니다.")
            return 0
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
