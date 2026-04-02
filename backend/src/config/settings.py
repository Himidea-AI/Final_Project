"""
환경 변수 로드 — .env 파일에서 API 키 등을 읽어옴.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API Keys
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # Database
    postgres_url: str = "postgresql://postgres:postgres@db:5432/mapo_simulator"
    postgres_password: str = "postgres"
    redis_url: str = "redis://redis:6379/0"
    chroma_host: str = "chromadb"
    chroma_port: int = 8000

    # External API Keys
    seoul_opendata_key: str = ""
    semas_api_key: str = ""
    sgis_api_key: str = ""
    sgis_secret_key: str = ""       # SGIS OAuth2 인증용 시크릿 키
    molit_api_key: str = ""

    # Naver DataLab API (SNS 트렌드 대체)
    naver_client_id: str = ""
    naver_client_secret: str = ""

    # LangSmith (환경 변수 설정만으로 자동 트레이싱 활성화)
    langchain_api_key: str = ""
    langchain_tracing_v2: bool = True
    langchain_project: str = "mapo-franchise-simulator"

    # App
    debug: bool = False
    demo_mode: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
