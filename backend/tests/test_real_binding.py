import sys
import os
import asyncio
from pathlib import Path

# backend/src 경로 추가 (backend/tests/ 에서 실행됨을 가정)
# 현재 파일 위치: backend/tests/test_real_binding.py
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent # Final_Project/
backend_src = project_root / "backend"

if str(backend_src) not in sys.path:
    sys.path.append(str(backend_src))

async def verify_imports():
    print("--- [VERIFICATION] 실데이터 바인딩 모듈 테스트 시작 ---")
    try:
        from src.agents.tools import MarketDataTool
        from src.database.postgres import PostgresClient
        from src.config.settings import settings
        
        # 1. DB 클라이언트 초기화 가능 여부
        db_client = PostgresClient(settings.postgres_url)
        print(f"✅ PostgresClient 설정 확인: {settings.postgres_url[:20]}...")
        
        # 2. Tool 초기화 가능 여부
        tool = MarketDataTool(db_client)
        print("✅ MarketDataTool 초기화 성공")
        
        # 3. 에이전트 노드 임포트 성공 여부
        from src.agents.nodes.market_analyst import market_analyst_node
        print("✅ market_analyst_node (실데이터 버전) 임포트 성공")
        
        # 4. SQL 스크립트 존재 확인
        sql_path = project_root / "backend/scripts/setup_pgvector_index.sql"
        if sql_path.exists():
            print(f"✅ HNSW 인덱스 스크립트 탐색 성공: {sql_path.name}")
        else:
            print(f"❌ SQL 스크립트 위치 확인 요망: {sql_path}")

    except Exception as e:
        print(f"❌ 검증 실패 (Import Error): {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(verify_imports())
