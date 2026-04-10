import asyncio
import asyncpg
import os
from dotenv import load_dotenv

async def test():
    load_dotenv()
    db_url = os.getenv("POSTGRES_URL")
    print(f"Testing connection to: {db_url}")
    
    # Try 127.0.0.1 and 192.168.0.28
    ips_to_test = ["127.0.0.1", "192.168.0.28"]
    
    for ip in ips_to_test:
        test_url = f"postgresql://postgres:postgres@{ip}:5432/postgres"
        print(f"\nTesting connection to: {test_url}")
        try:
            conn = await asyncpg.connect(test_url, timeout=5)
            print(f"Successfully connected to {ip}!")
            databases = await conn.fetch("SELECT datname FROM pg_database;")
            print("Available databases:")
            for db in databases:
                print(f"- {db['datname']}")
            await conn.close()
            break
        except Exception as e:
            print(f"Connection to {ip} failed: {e}")

if __name__ == "__main__":
    asyncio.run(test())
