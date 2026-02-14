#!/usr/bin/env python3
import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.database_async import db
from memory.models import DiaryEntry, Conversation
from sqlalchemy import delete

async def rollback_to_time(user_id: int, cutoff_str: str):
    # Parse the cutoff string
    try:
        cutoff = datetime.fromisoformat(cutoff_str)
        print(f"Rolling back user {user_id} data to before {cutoff}...")
    except ValueError:
        print(f"Invalid date format: {cutoff_str}. Use YYYY-MM-DD HH:MM:SS")
        return

    async with db.get_session() as session:
        # Delete DiaryEntries (memories and summaries)
        diary_stmt = (
            delete(DiaryEntry)
            .where(
                DiaryEntry.user_id == user_id,
                DiaryEntry.entry_type.in_(['conversation_memory', 'compact_summary']),
                DiaryEntry.timestamp > cutoff
            )
        )
        
        # Delete Conversations
        conv_stmt = (
            delete(Conversation)
            .where(
                Conversation.user_id == user_id,
                Conversation.timestamp > cutoff
            )
        )
        
        res_diary = await session.execute(diary_stmt)
        res_conv = await session.execute(conv_stmt)
        
        print(f"Deleted {res_diary.rowcount} memory/summary entries.")
        print(f"Deleted {res_conv.rowcount} conversation messages.")
        
    print("Done.")

if __name__ == "__main__":
    # 2026-02-13 21:28:00
    cutoff_str = "2026-02-13T21:28:00"
    user_id = 1
    
    if len(sys.argv) > 1:
        user_id = int(sys.argv[1])
    if len(sys.argv) > 2:
        cutoff_str = sys.argv[2]
        
    asyncio.run(rollback_to_time(user_id, cutoff_str))
