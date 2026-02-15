#!/usr/bin/env python3
"""
Test script to verify Chapter generation using interleaved paired entries.
Fetches actual compact summaries and conversation memories from DB,
pairs them, and generates a 'Chapter' using the LLM. Dry-run only (no DB writes).
"""
import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.database_async import db
from memory.models import DiaryEntry
from sqlalchemy import select, desc
from config.settings import settings
from utils.llm_client import llm_client
from prompts.chapter import CHAPTER_PROMPT


async def fetch_and_pair(user_id: int) -> list:
    """Fetch compact summaries and conversation memories, pair them by timestamp."""
    async with db.get_session() as session:
        # Fetch both types
        stmt = (
            select(DiaryEntry)
            .where(
                DiaryEntry.user_id == user_id,
                DiaryEntry.entry_type.in_(['compact_summary', 'conversation_memory'])
            )
            .order_by(desc(DiaryEntry.timestamp))
            .limit(40)  # Enough for ~20 pairs
        )
        result = await session.execute(stmt)
        entries = list(result.scalars().all())
    
    # Separate by type
    summaries = [e for e in entries if e.entry_type == 'compact_summary']
    memories = [e for e in entries if e.entry_type == 'conversation_memory']
    
    print(f"  Found {len(summaries)} compact summaries")
    print(f"  Found {len(memories)} conversation memories")
    
    # Pair by matching exchange_start and exchange_end
    pairs = []
    used_memory_ids = set()
    
    for summ in summaries:
        for mem in memories:
            if mem.id in used_memory_ids:
                continue
            # Match by time range (within 5 seconds tolerance)
            if summ.exchange_start and mem.exchange_start and summ.exchange_end and mem.exchange_end:
                start_diff = abs((summ.exchange_start - mem.exchange_start).total_seconds())
                end_diff = abs((summ.exchange_end - mem.exchange_end).total_seconds())
                if start_diff < 5.0 and end_diff < 5.0:
                    pairs.append((summ, mem))
                    used_memory_ids.add(mem.id)
                    break
    
    # Sort pairs chronologically (oldest first)
    pairs.sort(key=lambda p: p[0].timestamp)
    
    print(f"  Paired {len(pairs)} entries successfully")
    return pairs


def format_paired_entries(pairs: list) -> str:
    """Format paired entries into the FACTS/MEANING input structure."""
    sections = []
    for i, (summ, mem) in enumerate(pairs, 1):
        date_str = summ.timestamp.strftime("%Y-%m-%d")
        section = (
            f"--- Exchange {i} [{date_str}] ---\n"
            f"FACTS: {summ.content.strip()}\n"
            f"MEANING: {mem.content.strip()}"
        )
        sections.append(section)
    return "\n\n".join(sections)


async def test_chapter_generation(user_id: int = 1):
    print(f"=== Chapter Generation Test (User {user_id}) ===\n")
    
    # 1. Fetch and pair entries
    print("1. Fetching and pairing entries...")
    pairs = await fetch_and_pair(user_id)
    
    if len(pairs) < 2:
        print("Not enough paired entries to generate a chapter.")
        return
    
    # Get user name
    from memory.memory_manager_async import memory_manager
    user = await memory_manager.get_user_by_id(user_id)
    user_name = user.name if user and user.name else "User"

    # 2. Group into batches of 5 pairs
    batch_size = 5
    batches = [pairs[i:i + batch_size] for i in range(0, len(pairs), batch_size)]
    
    for batch_idx, batch in enumerate(batches):
        print(f"\n{'='*60}")
        print(f"Chapter {batch_idx + 1}: {len(batch)} pairs")
        print(f"Timeframe: {batch[0][0].timestamp.strftime('%Y-%m-%d %H:%M')} → {batch[-1][0].timestamp.strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*60}")
        
        # Format input
        paired_text = format_paired_entries(batch)
        
        # Show input snippet
        print(f"\n--- Input Snippet (first 500 chars) ---")
        print(paired_text[:500] + ("..." if len(paired_text) > 500 else ""))
        
        # Build prompt
        prompt = CHAPTER_PROMPT.format(
            user_name=user_name,
            pair_count=len(batch),
            paired_entries=paired_text,
        )
        
        # Token estimate (rough: ~4 chars per token)
        token_estimate = len(prompt) // 4
        print(f"\n📊 Estimated input tokens: ~{token_estimate}")
        
        # Generate chapter
        print("\n⏳ Generating chapter...")
        try:
            response = await llm_client.chat(
                model=settings.MODEL_MEMORY,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1000,
            )
            
            print(f"\n{'>'*20} GENERATED CHAPTER {'<'*20}")
            print(response)
            print(f"{'>'*20} END {'<'*20}")
            print(f"\n📊 Output length: {len(response)} chars (~{len(response)//4} tokens)")
            
        except Exception as e:
            print(f"❌ Error generating chapter: {e}")


if __name__ == "__main__":
    user_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    asyncio.run(test_chapter_generation(user_id))
