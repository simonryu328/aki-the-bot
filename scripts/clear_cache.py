
import asyncio
import os
import sys
from sqlalchemy import delete

# Add project root to path
sys.path.append(os.getcwd())

from memory.database_async import db
from memory.models import DiaryEntry

async def clear_daily_message_cache():
    print("Clearing daily message cache from database...")
    async with db.transaction() as session:
        # Delete all entries of type 'daily_message'
        stmt = delete(DiaryEntry).where(DiaryEntry.entry_type == 'daily_message')
        await session.execute(stmt)
    print("Done. Cache cleared.")

if __name__ == "__main__":
    asyncio.run(clear_daily_message_cache())
