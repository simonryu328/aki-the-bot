
import asyncio
import os
import sys
from sqlalchemy import text

# Add project root to path
sys.path.append(os.getcwd())

from memory.database_async import db

async def migrate():
    print("Starting database migration...")
    async with db.engine.begin() as conn:
        try:
            # Check if columns exist first to be safe
            print("Adding cache_read_tokens to token_usage...")
            await conn.execute(text("ALTER TABLE token_usage ADD COLUMN IF NOT EXISTS cache_read_tokens INTEGER DEFAULT 0"))
            
            print("Adding cache_creation_tokens to token_usage...")
            await conn.execute(text("ALTER TABLE token_usage ADD COLUMN IF NOT EXISTS cache_creation_tokens INTEGER DEFAULT 0"))
            
            print("Adding cost to token_usage...")
            await conn.execute(text("ALTER TABLE token_usage ADD COLUMN IF NOT EXISTS cost FLOAT"))
            
            print("Migration successful!")
        except Exception as e:
            print(f"Migration failed: {e}")
            if "already exists" in str(e):
                print("Columns already exist, skipping.")
            else:
                raise e

if __name__ == "__main__":
    asyncio.run(migrate())
