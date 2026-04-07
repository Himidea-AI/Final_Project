"""
환경 변수 로드 — .env 파일에서 API 키 등을 읽어옴.
"""
import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# [B1 트랙 개선] 어떤 모듈에서 설정을 임포트하더라도 최우선으로 .env를 로드하도록 보강
load_dotenv()

class Settings(BaseSettings):
    # API Keys
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")

    # Database
    # 기본값을 db가 아닌 localhost로 설정하여 로컬 개발 편의성 증대
    postgres_url: str = os.getenv(
        "POSTGRES_URL", 
        "postgresql://postgres:postgres@localhost:5432/mapo_simulator"
    )
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

    # Naver DataLab API
    naver_client_id: str = os.getenv("NAVER_CLIENT_ID", "")
    naver_client_secret: str = os.getenv("NAVER_CLIENT_SECRET", "")

    # LangSmith
    langchain_api_key: str = os.getenv("LANGCHAIN_API_KEY", "")
    langchain_tracing_v2: bool = os.getenv("LANGCHAIN_TRACING_V2", "true").lower() == "true"
    langchain_project: str = os.getenv("LANGCHAIN_PROJECT", "mapo-franchise-simulator")

    # App
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    app_mode: str = os.getenv("APP_MODE", "PROD") # "DEV" | "PROD"
    demo_mode: bool = os.getenv("DEMO_MODE", "false").lower() == "true"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore" # 정의되지 않은 환경 변수는 무시

settings = Settings()
