"""
벡터 DB 클라이언트 — RAG용 문서 저장/검색

클라이언트 종류:
- VectorDBClient    : ChromaDB 기반 (로컬 개발 / 기본값)
- PGVectorDBClient  : pgvector(PostgreSQL) 기반 (프로덕션 대체)

임베딩 모드 (EMBEDDING_MODE 환경변수로 전환):
- "openai" : OpenAI text-embedding-3-small (기본값, 프로덕션)
- "local"  : sentence-transformers paraphrase-multilingual-MiniLM-L12-v2 (개발용, 무료)

ChromaDB 실행 모드 (CHROMA_PERSIST_DIR 환경변수로 전환):
- 값 있음: PersistentClient — 로컬 파일 저장 (Docker 불필요)
- 비어있음: HttpClient     — Docker chromadb 컨테이너 연결 (프로덕션)
"""

import asyncio
import json
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
            response = self._openai.embeddings.create(model=self.OPENAI_EMBEDDING_MODEL, input=texts)
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

    async def search(self, query: str, top_k: int = 5, where: Optional[dict] = None) -> list[dict]:
        """
        유사 문서 검색

        Args:
            query: 검색 쿼리
            top_k: 반환할 문서 수
            where: ChromaDB 메타데이터 필터 (예: {"source": "가맹사업법"})
                   None이면 필터 없이 전체 검색

        Returns:
            list[dict]: [{text, metadata, distance}, ...]
        """
        query_embedding = await asyncio.to_thread(self._embed, [query])

        query_kwargs: dict = {"query_embeddings": query_embedding, "n_results": top_k}
        if where:
            query_kwargs["where"] = where

        results = await asyncio.to_thread(self._collection.query, **query_kwargs)

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


class PGVectorDBClient:
    """
    pgvector(PostgreSQL) 기반 벡터 DB 클라이언트.

    VectorDBClient(ChromaDB)와 동일한 메서드 시그니처를 유지하므로
    B1(에이전트 팀) 코드 변경 없이 교체 가능.

    테이블 컬럼:
        id       TEXT PRIMARY KEY
        content  TEXT            — 원문 텍스트 (documents의 "text" 필드)
        embedding vector(N)     — 임베딩 벡터 (N: 모드별 차원)
        metadata JSONB          — 법률명, 조문번호 등 메타데이터

    사용 예:
        client = PGVectorDBClient(connection_url=settings.postgres_url)
        await client.add_documents(chunks)
        results = await client.search("영업지역 보장", top_k=5)
    """

    OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
    LOCAL_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
    OPENAI_EMBEDDING_DIM = 1536  # text-embedding-3-small 출력 차원
    LOCAL_EMBEDDING_DIM = 384  # paraphrase-multilingual-MiniLM-L12-v2 출력 차원

    def __init__(self, connection_url: str, table_name: str = "legal_documents"):
        self._connection_url = connection_url
        self._table_name = table_name
        self._embedding_mode = settings.embedding_mode
        self._pool = None  # lazy init — asyncpg.create_pool()은 async이므로 첫 호출 시 생성

        self._embedding_dim = (
            self.OPENAI_EMBEDDING_DIM if self._embedding_mode == "openai" else self.LOCAL_EMBEDDING_DIM
        )

        # 임베딩 클라이언트 초기화 (VectorDBClient와 동일)
        if self._embedding_mode == "openai":
            self._openai = openai.OpenAI(api_key=settings.openai_api_key)
            self._local_model = None
        else:
            from sentence_transformers import SentenceTransformer

            self._local_model = SentenceTransformer(self.LOCAL_EMBEDDING_MODEL)
            self._openai = None

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """임베딩 생성 — VectorDBClient._embed()와 동일 로직."""
        if self._embedding_mode == "openai":
            response = self._openai.embeddings.create(model=self.OPENAI_EMBEDDING_MODEL, input=texts)
            return [item.embedding for item in response.data]
        else:
            return self._local_model.encode(texts).tolist()

    @staticmethod
    def _vec_to_str(vector: list[float]) -> str:
        """pgvector 입력용 문자열 변환. 예) [0.1, 0.2] → '[0.1,0.2]'"""
        return "[" + ",".join(str(x) for x in vector) + "]"

    async def _get_pool(self):
        """연결풀 lazy init + 테이블/인덱스 자동 생성."""
        if self._pool is None:
            import asyncpg

            self._pool = await asyncpg.create_pool(self._connection_url)
            await self._setup_table()
        return self._pool

    async def _setup_table(self) -> None:
        """pgvector extension, 테이블, HNSW 인덱스를 존재하지 않을 경우에만 생성."""
        async with self._pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._table_name} (
                    id       TEXT PRIMARY KEY,
                    content  TEXT NOT NULL,
                    embedding vector({self._embedding_dim}),
                    metadata JSONB
                )
                """
            )
            # HNSW 인덱스 — ivfflat과 달리 빈 테이블에서도 생성 가능
            await conn.execute(
                f"""
                CREATE INDEX IF NOT EXISTS {self._table_name}_embedding_hnsw_idx
                ON {self._table_name}
                USING hnsw (embedding vector_cosine_ops)
                """
            )

    def _build_where_sql(self, where: dict, start_param: int) -> tuple[str, list]:
        """
        ChromaDB 스타일 where dict를 PostgreSQL JSONB 조건절로 변환.

        지원 연산자:
            $eq  : metadata->>'field' = $N
            $in  : metadata->>'field' = ANY($N::text[])

        Args:
            where: {"source": {"$eq": "가맹사업법"}} 형식
            start_param: 첫 번째 파라미터 인덱스 ($N)

        Returns:
            (sql_clause, params) — sql_clause는 WHERE 이후 조건, params는 바인딩 값
        """
        conditions: list[str] = []
        params: list = []
        idx = start_param

        for field, condition in where.items():
            if not isinstance(condition, dict):
                continue
            for op, value in condition.items():
                if op == "$eq":
                    conditions.append(f"metadata->>'{field}' = ${idx}")
                    params.append(str(value))
                    idx += 1
                elif op == "$in":
                    # asyncpg는 list를 ANY(${idx}::text[])로 바인딩 가능
                    conditions.append(f"metadata->>'{field}' = ANY(${idx}::text[])")
                    params.append([str(v) for v in value])
                    idx += 1

        return " AND ".join(conditions), params

    async def add_documents(self, documents: list[dict], batch_size: int = 100) -> None:
        """
        문서 추가 — 임베딩 생성 후 PostgreSQL에 저장 (upsert로 중복 방지).

        Args:
            documents: [{"id": str, "text": str, "metadata": dict}, ...]
            batch_size: 한 번에 임베딩/저장할 문서 수 (OpenAI API 한도 대응)
        """
        pool = await self._get_pool()

        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            ids = [doc["id"] for doc in batch]
            texts = [doc["text"] for doc in batch]
            metadatas = [doc["metadata"] for doc in batch]

            embeddings = await asyncio.to_thread(self._embed, texts)

            async with pool.acquire() as conn:
                # executemany로 배치 upsert
                await conn.executemany(
                    f"""
                    INSERT INTO {self._table_name} (id, content, embedding, metadata)
                    VALUES ($1, $2, $3::vector, $4::jsonb)
                    ON CONFLICT (id) DO UPDATE
                        SET content   = EXCLUDED.content,
                            embedding = EXCLUDED.embedding,
                            metadata  = EXCLUDED.metadata
                    """,
                    [
                        (doc_id, text, self._vec_to_str(emb), json.dumps(meta, ensure_ascii=False))
                        for doc_id, text, emb, meta in zip(ids, texts, embeddings, metadatas)
                    ],
                )

    async def search(self, query: str, top_k: int = 5, where: Optional[dict] = None) -> list[dict]:
        """
        코사인 유사도 기반 문서 검색.

        Args:
            query: 검색 쿼리
            top_k: 반환할 문서 수
            where: 메타데이터 필터 (ChromaDB 스타일)
                   예) {"source": {"$eq": "가맹사업법"}}
                       {"source": {"$in": ["가맹사업법", "가맹사업법 시행령"]}}

        Returns:
            list[dict]: [{"text": str, "metadata": dict, "distance": float}, ...]
                        VectorDBClient.search()와 동일한 반환 형식
        """
        pool = await self._get_pool()
        query_emb = await asyncio.to_thread(self._embed, [query])
        emb_str = self._vec_to_str(query_emb[0])

        # $1 = 쿼리 벡터 문자열, $2 = top_k / where 파라미터는 $3부터
        params: list = [emb_str, top_k]
        where_clause = ""

        if where:
            clause, where_params = self._build_where_sql(where, start_param=3)
            if clause:
                where_clause = f"WHERE {clause}"
                params.extend(where_params)

        sql = f"""
            SELECT content,
                   metadata,
                   embedding <=> $1::vector AS distance
            FROM   {self._table_name}
            {where_clause}
            ORDER  BY embedding <=> $1::vector
            LIMIT  $2
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        return [
            {
                "text": row["content"],
                # asyncpg는 JSONB를 dict로 자동 디코딩하지만 안전하게 처리
                "metadata": dict(row["metadata"]) if row["metadata"] else {},
                "distance": float(row["distance"]),
            }
            for row in rows
        ]

    async def delete_collection(self) -> None:
        """테이블 전체 레코드 삭제 (테이블 자체는 유지)."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(f"DELETE FROM {self._table_name}")
