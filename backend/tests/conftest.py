"""
A2 테스트 공통 설정

- APP_MODE=PROD : pgvector 실제 연결 활성화
- POSTGRES_URL  : .env에 설정된 값 우선, 없으면 localhost fallback
- EMBEDDING_MODE=local : HuggingFace 로컬 임베딩 사용
"""

import asyncio
import os
import sys

# Windows + psycopg3 비호환 문제 해결
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# .env 파일 로드 — settings.py 임포트 전에 실행하여 POSTGRES_URL 등 반영
from dotenv import load_dotenv

load_dotenv()

# settings 모듈 임포트 전에 환경변수 설정 (싱글톤 초기화 시 반영됨)
os.environ["APP_MODE"] = "PROD"
# .env 파일에 POSTGRES_URL이 설정되어 있으면 그대로 사용, 없으면 localhost fallback
if "POSTGRES_URL" not in os.environ:
    os.environ["POSTGRES_URL"] = "postgresql://postgres:postgres@localhost:5432/mapo_simulator"
os.environ["EMBEDDING_MODE"] = "local"
