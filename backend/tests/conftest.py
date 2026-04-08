"""
A2 테스트 공통 설정

- APP_MODE=PROD : pgvector 실제 연결 활성화
- POSTGRES_URL  : Docker db → localhost 로 오버라이드 (로컬 테스트용)
- EMBEDDING_MODE=local : HuggingFace 로컬 임베딩 사용
"""

import asyncio
import os
import sys

# Windows + psycopg3 비호환 문제 해결
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# settings 모듈 임포트 전에 환경변수 설정 (싱글톤 초기화 시 반영됨)
os.environ["APP_MODE"] = "PROD"
os.environ["POSTGRES_URL"] = "postgresql://postgres:postgres@localhost:5432/mapo_simulator"
os.environ["EMBEDDING_MODE"] = "local"
