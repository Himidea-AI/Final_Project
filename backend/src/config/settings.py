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

    # NTS (국세청)
    nts_api_key: str = os.getenv("NTS_API_KEY", "")

    # JWT — dev fallback 제공, 운영에선 반드시 .env의 강력한 secret으로 덮어쓰기
    jwt_secret_key: str = os.getenv(
        "JWT_SECRET_KEY", "dev-only-not-secret-replace-in-prod"
    )
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # 정의되지 않은 환경 변수는 무시


settings = Settings()
