
import asyncio
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from agents.soul_agent import soul_agent
from memory.memory_manager_async import memory_manager
from memory.database_async import db
from memory.models import DiaryEntry
from sqlalchemy import delete
from core import get_logger

logger = get_logger(__name__)

async def retrigger_daily_messages():
    print("Connecting to DB...")
    
    # 1. Clear today's messages
    async with db.get_session() as session:
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        print(f"Clearing daily_message entries created after {today_start} UTC...")
        stmt = delete(DiaryEntry).where(
            DiaryEntry.entry_type == "daily_message",
            DiaryEntry.timestamp >= today_start
        )
        result = await session.execute(stmt)
        print(f"Deleted {result.rowcount} entries.")

    # 2. Generate new messages for all users
    print("Fetching all users...")
    users = await memory_manager.get_all_users()
    print(f"Found {len(users)} users.")
    
    for user in users:
        print(f"\nGenerating message for: {user.name} (ID: {user.id})")
        try:
            content, is_fallback = await soul_agent.generate_daily_message(user.id)
            
            # Use the memory manager directly to store the entry
            await memory_manager.add_diary_entry(
                user_id=user.id,
                entry_type="daily_message",
                title="Daily Message" if not is_fallback else "Daily Message (Fallback)",
                content=content,
                importance=10 if not is_fallback else 5
            )
            print(f"Generated: {content[:50]}...")
        except Exception as e:
            print(f"Failed for user {user.id}: {e}")
            
    print("\nAll daily messages retriggered.")

if __name__ == "__main__":
    asyncio.run(retrigger_daily_messages())
