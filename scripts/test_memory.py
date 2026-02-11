#!/usr/bin/env python3
"""
Test script for conversation memory generation.
Tests the new memory entry feature that captures who the user is and what matters to them.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.memory_manager_async import memory_manager
from agents.soul_agent import SoulAgent
from config.settings import settings


async def test_memory_generation():
    """Test memory entry generation for a user."""
    
    print("=" * 60)
    print("CONVERSATION MEMORY TEST")
    print("=" * 60)
    
    # Get a user with conversations
    async with memory_manager.db.get_session() as session:
        from memory.models import User, Conversation
        from sqlalchemy import select, func
        
        # Find user with most conversations
        result = await session.execute(
            select(User.id, User.name, func.count(Conversation.id).label('conv_count'))
            .join(Conversation, User.id == Conversation.user_id)
            .group_by(User.id, User.name)
            .order_by(func.count(Conversation.id).desc())
            .limit(1)
        )
        user_data = result.first()
        
        if not user_data:
            print("❌ No users with conversations found")
            return
        
        user_id = user_data[0]
        user_name = user_data[1]
        conv_count = user_data[2]
        
        print(f"\n📊 Testing with user: {user_name} (ID: {user_id})")
        print(f"   Total conversations: {conv_count}")
    
    # Create soul agent
    soul_agent = SoulAgent()
    
    # Run memory generation
    print("\n🧠 Generating conversation memory...")
    await soul_agent._create_memory_entry(user_id=user_id)
    
    # Fetch and display the generated memory
    print("\n" + "=" * 60)
    print("GENERATED MEMORY ENTRIES")
    print("=" * 60)
    
    diary_entries = await memory_manager.get_diary_entries(user_id, limit=10)
    
    memory_found = False
    for entry in diary_entries:
        if entry.entry_type == "conversation_memory":
            memory_found = True
            print(f"\n✅ Memory Entry (created at {entry.timestamp}):")
            print(f"   Exchange: {entry.exchange_start} → {entry.exchange_end}")
            print(f"\n{entry.content}")
            print("\n" + "-" * 60)
    
    if not memory_found:
        print("\n❌ No memory entries found")
    
    # Also show compact summaries for comparison
    print("\n" + "=" * 60)
    print("COMPACT SUMMARIES (for comparison)")
    print("=" * 60)
    
    compact_found = False
    for entry in diary_entries:
        if entry.entry_type == "compact_summary":
            compact_found = True
            print(f"\n📝 Compact Summary (created at {entry.timestamp}):")
            print(f"   Exchange: {entry.exchange_start} → {entry.exchange_end}")
            print(f"\n{entry.content}")
            print("\n" + "-" * 60)
            break  # Just show the most recent one
    
    if not compact_found:
        print("\n❌ No compact summaries found")


if __name__ == "__main__":
    asyncio.run(test_memory_generation())

# Made with Bob
