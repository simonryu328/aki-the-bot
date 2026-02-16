
import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from memory.database_async import db
from memory.models import DiaryEntry, User
from sqlalchemy import select

async def check_daily_messages():
    print("Checking database for daily_message entries...")
    async with db.transaction() as session:
        stmt = select(DiaryEntry).where(DiaryEntry.entry_type == 'daily_message')
        result = await session.execute(stmt)
        entries = result.scalars().all()
        
        if not entries:
            print("No daily_message entries found in DB.")
        else:
            print(f"Found {len(entries)} daily_message entries:")
            for e in entries:
                print(f"ID: {e.id}, UserID: {e.user_id}, Title: {e.title}, Content: {e.content[:50]}...")

if __name__ == "__main__":
    asyncio.run(check_daily_messages())
