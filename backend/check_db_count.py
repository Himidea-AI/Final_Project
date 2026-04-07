from src.database.vector_db import legal_db
from src.config.settings import settings
import asyncio

async def check_db():
    print(f"Current App Mode: {settings.app_mode}")
    count = legal_db.get_total_count()
    print(f"Total documents in Legal DB: {count}")

if __name__ == "__main__":
    asyncio.run(check_db())
