#!/usr/bin/env python3
"""
Simple script to remove the 10 most recent conversation_memory entries 
and 10 most recent compact_summary entries for a specific user.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.database_async import db
from memory.models import DiaryEntry
from sqlalchemy import select, delete, desc

async def remove_entries(user_id: int):
    print(f"Connecting to database to remove entries for user {user_id}...")
    
    async with db.get_session() as session:
        # Find the 10 most recent conversation_memory IDs
        stmt_mem = (
            select(DiaryEntry.id)
            .where(DiaryEntry.user_id == user_id, DiaryEntry.entry_type == 'conversation_memory')
            .order_by(desc(DiaryEntry.timestamp))
            .limit(10)
        )
        res_mem = await session.execute(stmt_mem)
        mem_ids = [r[0] for r in res_mem.fetchall()]
        
        # Find the 10 most recent compact_summary IDs
        stmt_sum = (
            select(DiaryEntry.id)
            .where(DiaryEntry.user_id == user_id, DiaryEntry.entry_type == 'compact_summary')
            .order_by(desc(DiaryEntry.timestamp))
            .limit(10)
        )
        res_sum = await session.execute(stmt_sum)
        sum_ids = [r[0] for r in res_sum.fetchall()]
        
        all_ids = mem_ids + sum_ids
        
        if not all_ids:
            print("No entries found to remove.")
            return

        print(f"Found {len(mem_ids)} memory entries and {len(sum_ids)} compact summaries to remove.")
        print(f"IDs to remove: {all_ids}")
        
        # Double check user before proceeding
        # (This script is intended for Simon, user_id 1)
        
        if all_ids:
            delete_stmt = delete(DiaryEntry).where(DiaryEntry.id.in_(all_ids))
            await session.execute(delete_stmt)
            print("Successfully deleted entries.")
        
    print("Done.")

if __name__ == "__main__":
    # Default to user_id 1 if not provided
    user_id = 1
    if len(sys.argv) > 1:
        try:
            user_id = int(sys.argv[1])
        except ValueError:
            print("Invalid user_id provided. Using default (1).")
    
    asyncio.run(remove_entries(user_id))
