import asyncio
import asyncpg
import os
from dotenv import load_dotenv

async def test():
    load_dotenv()
    db_url = os.getenv("POSTGRES_URL").replace("localhost", "127.0.0.1")
    print(f"Testing table info on: {db_url}")
    
    try:
        conn = await asyncpg.connect(db_url)
        # Final attempt to find the column name
        res = await conn.fetch("""
            SELECT attname 
            FROM pg_attribute 
            WHERE attrelid = 'store_info'::regclass 
            AND attnum > 0 
            AND NOT attisdropped;
        """)
        cols = [r['attname'] for r in res]
        print(f"All columns in 'store_info': {cols}")
        
        # Also test the vector cast itself
        try:
            res = await conn.fetchval("SELECT '[0.1, 0.2]'::vector;")
            print(f"Vector cast test: {res}")
        except Exception as ve:
            print(f"Vector cast test failed: {ve}")
            
        await conn.close()
    except Exception as e:
        print(f"Diagnostic failed: {e}")

if __name__ == "__main__":
    asyncio.run(test())
