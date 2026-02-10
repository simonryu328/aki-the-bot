#!/usr/bin/env python3
"""
Debug script to check if compact summaries and conversation history are being passed correctly.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytz
from memory.memory_manager_async import memory_manager
from config.settings import settings
from agents.soul_agent import soul_agent


async def debug_context(user_id: int):
    """Check what context is being built for the agent."""
    print(f"\n{'='*60}")
    print(f"  DEBUGGING CONTEXT FOR USER {user_id}")
    print(f"{'='*60}\n")
    
    tz = pytz.timezone(settings.TIMEZONE)
    
    # 1. Check diary entries (compact summaries)
    print("1. CHECKING DIARY ENTRIES (COMPACT SUMMARIES)")
    print("-" * 60)
    diary_entries = await memory_manager.get_diary_entries(user_id, limit=settings.DIARY_FETCH_LIMIT)
    compact_summaries = [e for e in diary_entries if e.entry_type == 'compact_summary']
    
    print(f"Total diary entries fetched: {len(diary_entries)}")
    print(f"Compact summaries found: {len(compact_summaries)}")
    print(f"COMPACT_SUMMARY_LIMIT setting: {settings.COMPACT_SUMMARY_LIMIT}")
    
    if compact_summaries:
        print("\nCompact summaries (newest first):")
        for i, compact in enumerate(compact_summaries[:settings.COMPACT_SUMMARY_LIMIT]):
            print(f"\n  [{i+1}] ID: {compact.id}")
            print(f"      Timestamp: {compact.timestamp}")
            print(f"      Exchange Start: {compact.exchange_start}")
            print(f"      Exchange End: {compact.exchange_end}")
            print(f"      Content: {compact.content[:100]}...")
    else:
        print("\n  ⚠️  NO COMPACT SUMMARIES FOUND!")
    
    # 2. Check recent conversations
    print(f"\n\n2. CHECKING RECENT CONVERSATIONS")
    print("-" * 60)
    recent_convos = await memory_manager.db.get_recent_conversations(
        user_id, limit=settings.CONVERSATION_CONTEXT_LIMIT
    )
    print(f"Recent conversations fetched: {len(recent_convos)}")
    print(f"CONVERSATION_CONTEXT_LIMIT setting: {settings.CONVERSATION_CONTEXT_LIMIT}")
    
    if recent_convos:
        print("\nMost recent 5 conversations:")
        for i, conv in enumerate(recent_convos[-5:]):
            role = "USER" if conv.role == "user" else "BOT"
            print(f"  [{i+1}] {role}: {conv.message[:60]}... (at {conv.timestamp})")
    
    # 3. Test the _build_conversation_context method
    print(f"\n\n3. TESTING _build_conversation_context METHOD")
    print("-" * 60)
    
    recent_exchanges_text, current_conversation_text = await soul_agent._build_conversation_context(
        user_id=user_id,
        conversation_history=recent_convos
    )
    
    print("\nRECENT EXCHANGES TEXT:")
    print("-" * 60)
    if recent_exchanges_text:
        print(recent_exchanges_text[:500])
        if len(recent_exchanges_text) > 500:
            print(f"\n... (truncated, total length: {len(recent_exchanges_text)} chars)")
    else:
        print("  ⚠️  EMPTY OR NONE!")
    
    print("\n\nCURRENT CONVERSATION TEXT:")
    print("-" * 60)
    if current_conversation_text:
        print(current_conversation_text[:500])
        if len(current_conversation_text) > 500:
            print(f"\n... (truncated, total length: {len(current_conversation_text)} chars)")
    else:
        print("  ⚠️  EMPTY OR NONE!")
    
    # 4. Check if conversations are after last compact
    if compact_summaries:
        print(f"\n\n4. CHECKING CONVERSATION FILTERING")
        print("-" * 60)
        last_compact = compact_summaries[0]
        last_compact_end = last_compact.exchange_end
        
        print(f"Last compact end time: {last_compact_end}")
        
        if last_compact_end:
            convos_after = await memory_manager.db.get_conversations_after(
                user_id=user_id,
                after=last_compact_end,
                limit=settings.CONVERSATION_CONTEXT_LIMIT
            )
            print(f"Conversations AFTER last compact: {len(convos_after)}")
        else:
            convos_after = []
            print("  ⚠️  Last compact has no exchange_end timestamp!")
            print(f"Conversations AFTER last compact: 0")
        
        if convos_after:
            print("\nFirst 3 conversations after last compact:")
            for i, conv in enumerate(convos_after[:3]):
                role = "USER" if conv.role == "user" else "BOT"
                print(f"  [{i+1}] {role} at {conv.timestamp}: {conv.message[:60]}...")
        else:
            print("  ⚠️  NO CONVERSATIONS AFTER LAST COMPACT!")
    
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/debug_context.py <user_id>")
        sys.exit(1)
    
    user_id = int(sys.argv[1])
    asyncio.run(debug_context(user_id))

# Made with Bob
