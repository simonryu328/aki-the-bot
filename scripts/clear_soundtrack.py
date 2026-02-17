
import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from memory.database_async import db
from memory.models import DiaryEntry
from sqlalchemy import delete
from datetime import datetime, timedelta

async def clear_todays_soundtrack():
    print("Connecting to DB...")
    async with db.get_session() as session:
        # Calculate start of today (UTC)
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        print(f"Deleting daily_soundtrack entries created after {today_start}...")
        
        stmt = delete(DiaryEntry).where(
            DiaryEntry.entry_type == "daily_soundtrack",
            DiaryEntry.timestamp >= today_start
        )
        result = await session.execute(stmt)
        await session.commit()
        
        print(f"Deleted {result.rowcount} entries.")

if __name__ == "__main__":
    asyncio.run(clear_todays_soundtrack())
