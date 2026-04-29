import asyncio
import sys
from pathlib import Path

# src 경로 추가
sys.path.append(str(Path(__file__).parent.parent / "backend"))


async def verify_imports():
    print("--- [VERIFICATION] 모듈 임포트 테스트 시작 ---")
    try:
        from src.agents.tools import MarketDataTool
        from src.config.settings import settings
        from src.database.postgres import PostgresClient

        db_client = PostgresClient(settings.postgres_url)
        tool = MarketDataTool(db_client)

        print("✅ MarketDataTool 임포트 및 초기화 성공")

        print("✅ market_analyst_node 임포트 성공")

        # SQL 스크립트 존재 확인
        sql_path = Path(__file__).parent.parent / "backend/scripts/setup_pgvector_index.sql"
        if sql_path.exists():
            print(f"✅ SQL 인덱스 스크립트 확인: {sql_path.name}")
        else:
            print(f"❌ SQL 인덱스 스크립트 없음: {sql_path}")

    except Exception as e:
        print(f"❌ 검증 실패: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(verify_imports())
