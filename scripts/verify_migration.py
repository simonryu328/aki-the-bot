
import asyncio
import os
import sys
from sqlalchemy import text

# Add project root to path
sys.path.append(os.getcwd())

from memory.database_async import db

async def verify():
    print("Verifying token_usage columns...")
    async with db.engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'token_usage'
        """))
        columns = [row[0] for row in result.fetchall()]
        print(f"Columns found: {columns}")
        
        if 'cache_read_tokens' in columns:
            print("Verified: cache_read_tokens EXISTS")
        else:
            print("CRITICAL: cache_read_tokens MISSING")

if __name__ == "__main__":
    asyncio.run(verify())
