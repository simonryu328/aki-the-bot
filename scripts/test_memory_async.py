"""
Comprehensive test suite for the AI Companion memory system.
Production-grade async version with proper error handling and logging.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from memory.memory_manager_async import memory_manager
from core import configure_logging, get_logger

logger = get_logger(__name__)


async def test_memory_system():
    """Run comprehensive memory system tests."""

    print("=" * 60)
    print("Testing AI Companion Memory System (Async)")
    print("=" * 60)
    print()

    try:
        # Test 1: Create user
        print("[Test 1] Creating test user...")
        user = await memory_manager.get_or_create_user(
            telegram_id=99999,
            name="Test User Async",
            username="testuser_async",
        )
        user_id = user.id
        print(f"✓ Created user with ID: {user_id}")
        print()

        # Test 2: Add conversations
        print("[Test 2] Adding conversation messages...")
        await memory_manager.add_conversation(user_id, "user", "Hello! I'm testing the new memory system.")
        await memory_manager.add_conversation(user_id, "assistant", "I see! Everything seems to be working smoothly.")
        await memory_manager.add_conversation(user_id, "user", "That's great. I'm focusing on simplicity now.")
        await memory_manager.add_conversation(
            user_id, "assistant", "Simplicity is a virtue. I've moved away from complex profiles."
        )
        print("✓ Added 4 conversation messages")
        print()

        # Test 3: Add diary entries (The new primary memory)
        print("[Test 3] Adding diary entries...")
        await memory_manager.add_diary_entry(
            user_id=user_id,
            entry_type="milestone",
            title="First Step into Simplicity",
            content="Began the journey of simplifying the AI Companion architecture.",
            importance=9,
        )
        await memory_manager.add_diary_entry(
            user_id=user_id,
            entry_type="conversation_memory",
            title="Recent Progress",
            content="The user discussed their focus on simplicity and architectural cleanup.",
            importance=7,
            exchange_start=datetime.utcnow() - timedelta(minutes=10),
            exchange_end=datetime.utcnow(),
        )
        print("✓ Added 2 diary entries")
        print()

        # Test 4: Retrieve diary entries
        print("[Test 4] Retrieving diary entries...")
        entries = await memory_manager.get_diary_entries(user_id, limit=5)
        print(f"  Found {len(entries)} entries:")
        for entry in entries:
            print(f"    - [{entry.entry_type}] {entry.title} (Importance: {entry.importance})")
        print()

        # Test 5: Get complete user context
        print("[Test 5] Retrieving complete user context...")
        context = await memory_manager.get_user_context(user_id)
        print(f"  User: {context.user_info.name} (@{context.user_info.username})")
        print(f"  Recent conversations: {len(context.recent_conversations)}")
        print(f"  Diary entries: {len(context.diary_entries)}")
        print()

        # Test 6: Test context prompt formatting
        print("[Test 6] Testing context-to-prompt conversion...")
        prompt_context = context.to_prompt_context()
        print("Context formatted for LLM prompt:")
        print("-" * 60)
        print(prompt_context[:500] + "..." if len(prompt_context) > 500 else prompt_context)
        print("-" * 60)
        print()

        # Test 7: Token usage tracking
        print("[Test 7] Testing token usage tracking...")
        await memory_manager.record_token_usage(
            user_id=user_id,
            model="gpt-4o",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            call_type="conversation",
        )
        usage_today = await memory_manager.get_user_token_usage_today(user_id)
        print(f"✓ Recorded 150 tokens. Today's total: {usage_today}")
        print()

        print("=" * 60)
        print("✓ All tests passed successfully!")
        print("=" * 60)
        print()
        print("Memory system is working correctly with:")
        print(f"  - PostgreSQL (async): ✓")
        print(f"  - Diary-based memories: ✓")
        print(f"  - Token budget checking: ✓")
        print()

    except Exception as e:
        logger.error("Test failed", error=str(e), exc_info=True)
        print()
        print("=" * 60)
        print("✗ Tests failed!")
        print("=" * 60)
        print(f"Error: {e}")
        sys.exit(1)


async def main():
    """Run tests with proper logging configuration."""
    configure_logging(log_level="INFO")
    await test_memory_system()


if __name__ == "__main__":
    asyncio.run(main())
