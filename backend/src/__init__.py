"""
마포구 프랜차이즈 상권분석 시뮬레이터 — 백엔드 루트 패키지

FastAPI 기반 백엔드. 하위 모듈:
  - config/    : 환경 변수, 비즈니스 상수, 프롬프트 설정
  - agents/    : LangGraph 에이전트 워크플로우 (8개 분석 노드 + supervisor)
  - schemas/   : Pydantic 입출력 스키마 (API 요청/응답, Agent 상태)
  - chains/    : LangChain RAG 및 프롬프트 관리
  - services/  : 외부 API 클라이언트 (공공데이터 7개 소스)
  - database/  : PostgreSQL, Redis, ChromaDB 연결
"""

# ─── Windows event loop policy 강제 ─────────────────────────────────────────
# psycopg 3 async 가 Windows default ProactorEventLoop 와 충돌해 legal RAG
# specialist 가 ``psycopg.InterfaceError`` 로 0건 반환되는 문제 해결.
# uvicorn `--reload` worker subprocess 가 src 패키지를 import 하는 순간
# (다른 모듈 import 전) 정책이 적용되도록 패키지 init 에 위치시킨다.
# https://sqlalche.me/e/20/rvf5
import sys as _sys

if _sys.platform == "win32":
    import asyncio as _asyncio

    _asyncio.set_event_loop_policy(_asyncio.WindowsSelectorEventLoopPolicy())
