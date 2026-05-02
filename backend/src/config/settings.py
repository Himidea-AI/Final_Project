"""
환경 변수 로드 — .env 파일에서 API 키 등을 읽어옴.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# [B1 트랙 개선] 어떤 모듈에서 설정을 임포트하더라도 최우선으로 .env를 로드하도록 보강
# cwd가 backend/ 또는 repo root 어느 쪽이든 repo root의 .env를 찾도록 명시.
# backend/src/config/settings.py → parents[3] = repo root
_REPO_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
if _REPO_ROOT_ENV.exists():
    load_dotenv(_REPO_ROOT_ENV)
else:
    load_dotenv()  # fallback — cwd 기준


class Settings(BaseSettings):
    # API Keys
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")

    # Database
    # 기본값을 db가 아닌 localhost로 설정하여 로컬 개발 편의성 증대
    postgres_url: str = os.getenv("POSTGRES_URL", "postgresql://postgres:postgres@localhost:5432/mapo_simulator")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    chroma_host: str = os.getenv("CHROMA_HOST", "localhost")
    chroma_port: int = int(os.getenv("CHROMA_PORT", "8000"))
    chroma_persist_dir: str = os.getenv("CHROMA_PERSIST_DIR", "")
    embedding_mode: str = os.getenv("EMBEDDING_MODE", "openai")

    # External API Keys
    seoul_opendata_key: str = os.getenv("SEOUL_OPENDATA_KEY", "")
    semas_api_key: str = os.getenv("SEMAS_API_KEY", "")
    sgis_api_key: str = os.getenv("SGIS_API_KEY", "")
    sgis_secret_key: str = os.getenv("SGIS_SECRET_KEY", "")
    molit_api_key: str = os.getenv("MOLIT_API_KEY", "")
    ftc_api_key: str = os.getenv("FTC_API_KEY", "")
    law_oc: str = os.getenv("LAW_OC", "")

    # Naver DataLab API
    naver_client_id: str = os.getenv("NAVER_CLIENT_ID", "")
    naver_client_secret: str = os.getenv("NAVER_CLIENT_SECRET", "")

    # LangSmith
    langchain_api_key: str = os.getenv("LANGCHAIN_API_KEY", "")
    langchain_tracing_v2: bool = os.getenv("LANGCHAIN_TRACING_V2", "true").lower() == "true"
    langchain_project: str = os.getenv("LANGCHAIN_PROJECT", "mapo-franchise-simulator")

    # App
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    app_mode: str = os.getenv("APP_MODE", "PROD")  # "DEV" | "PROD"
    demo_mode: bool = os.getenv("DEMO_MODE", "false").lower() == "true"

    # HyDE (Hypothetical Document Embeddings) — LLM 기반 쿼리 확장
    hyde_enabled: bool = os.getenv("HYDE_ENABLED", "false").lower() == "true"

    # RRF (Reciprocal Rank Fusion) — vector + BM25 결합 가중치
    # SP3 grid search 결과 (2026-05-01, 29 케이스 골든셋, BGE-m3 + Kiwi BM25):
    #   vec=0.3/bm25=0.7  Recall 0.408 NDCG 0.263 Hit 62.1%
    #   vec=0.4/bm25=0.6  Recall 0.408 NDCG 0.273 Hit 62.1%  ← 최적 (NDCG/MRR 최고)
    #   vec=0.5/bm25=0.5  Recall 0.351 NDCG 0.248 Hit 55.2%  (이전 baseline)
    #   vec=0.6/bm25=0.4  Recall 0.316 NDCG 0.235 Hit 48.3%
    #   vec=0.7/bm25=0.3  Recall 0.333 NDCG 0.241 Hit 48.3%
    # 한국어 법률 텍스트는 키워드 매칭(BM25)이 의미 매칭(vector)보다 강력.
    rrf_k: int = int(os.getenv("RRF_K", "60"))
    rrf_vector_weight: float = float(os.getenv("RRF_VECTOR_WEIGHT", "0.4"))
    rrf_bm25_weight: float = float(os.getenv("RRF_BM25_WEIGHT", "0.6"))

    # Reranker — Cross-encoder로 top-K 재정렬 (정밀도 ↑, 검색 속도 ↓ ~500ms/쿼리)
    # 이전 baseline (MiniLM 384D, 4배 중복 데이터) 측정 시 F1 -0.030, 비활성됨.
    # SP3 후 (BGE-m3 + Kiwi BM25 + 정상 9484 청크) 환경에서 재측정 가치 있음.
    # default OFF — RERANK_ENABLED=true env로 활성화 후 bench 비교 권장.
    rerank_enabled: bool = os.getenv("RERANK_ENABLED", "false").lower() == "true"
    rerank_model: str = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
    rerank_initial_k: int = int(os.getenv("RERANK_INITIAL_K", "30"))  # 1차 검색 K
    rerank_final_k: int = int(os.getenv("RERANK_FINAL_K", "10"))  # 재정렬 후 반환 K

    # Chunk Compression — cheap LLM으로 RAG 청크를 1~2문장 핵심 요약 → 메인 LLM 컨텍스트 ↓
    # default OFF. CHUNK_COMPRESSION_ENABLED=true 활성화. cheap model: gemini-flash/gpt-4o-mini.
    chunk_compression_enabled: bool = os.getenv("CHUNK_COMPRESSION_ENABLED", "false").lower() == "true"
    chunk_compression_model: str = os.getenv("CHUNK_COMPRESSION_MODEL", "gpt-4.1-mini")

    # Multi-query expansion — cheap LLM이 1쿼리 → N개 변형 → 병렬 검색 후 RRF fusion.
    # 기대: Recall +10~15%. 비용: cheap LLM 1회 + RAG 검색 N배.
    multi_query_enabled: bool = os.getenv("MULTI_QUERY_ENABLED", "false").lower() == "true"
    multi_query_n: int = int(os.getenv("MULTI_QUERY_N", "3"))
    multi_query_model: str = os.getenv("MULTI_QUERY_MODEL", "gpt-4.1-mini")

    # Legal Rule Engine — 8 룰 + 4 specialist 하이브리드 (2026-05-02).
    # 단일 모드로 전환 (legacy single-LLM batch 경로 제거). flag 자체는 호환을 위해 보존.
    # 스펙: docs/superpowers/specs/2026-05-02-legal-rule-engine-design.md
    legal_rule_engine_enabled: bool = (
        os.getenv("LEGAL_RULE_ENGINE_ENABLED", "true").lower() == "true"
    )

    # NTS (국세청)
    nts_api_key: str = os.getenv("NTS_API_KEY", "")

    # JWT — dev fallback 제공, 운영에선 반드시 .env의 강력한 secret으로 덮어쓰기
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "dev-only-not-secret-replace-in-prod")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # 정의되지 않은 환경 변수는 무시


settings = Settings()
