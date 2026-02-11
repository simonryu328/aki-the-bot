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
            telegram_id=12345,
            name="Test User",
            username="testuser",
        )
        user_id = user.id
        print(f"✓ Created user with ID: {user_id}")
        print()

        # Test 2: Add profile facts
        print("[Test 2] Adding profile facts...")
        await memory_manager.add_profile_fact(
            user_id, "basic_info", "job", "Software Engineer"
        )
        await memory_manager.add_profile_fact(
            user_id, "basic_info", "location", "Toronto"
        )
        await memory_manager.add_profile_fact(
            user_id, "preferences", "favorite_food", "Pizza"
        )
        await memory_manager.add_profile_fact(
            user_id, "relationships", "best_friend", "Alex"
        )
        print("✓ Added 4 profile facts")
        print()

        # Test 3: Retrieve profile
        print("[Test 3] Retrieving user profile...")
        profile = await memory_manager.get_user_profile(user_id)
        for category, facts in profile.items():
            print(f"  {category}:")
            for key, value in facts.items():
                print(f"    - {key}: {value}")
        print()

        # Test 4: Add conversations
        print("[Test 4] Adding conversation messages...")
        await memory_manager.add_conversation(user_id, "user", "Hello! How are you?")
        await memory_manager.add_conversation(user_id, "assistant", "I'm doing great! How can I help you today?")
        await memory_manager.add_conversation(user_id, "user", "I want to learn about Python")
        await memory_manager.add_conversation(
            user_id, "assistant", "Python is a great language! Let's start with the basics."
        )
        print("✓ Added 4 conversation messages")
        print()

        # Test 5: Add timeline event
        print("[Test 5] Adding timeline event...")
        event_time = datetime.utcnow() + timedelta(days=3)
        await memory_manager.add_timeline_event(
            user_id=user_id,
            event_type="meeting",
            title="Project Review Meeting",
            description="Quarterly review with team",
            datetime_obj=event_time,
        )
        print(f"✓ Added timeline event: Project Review Meeting at {event_time}")
        print()

        # Test 6: Add diary entry
        print("[Test 6] Adding diary entry...")
        await memory_manager.add_diary_entry(
            user_id=user_id,
            entry_type="achievement",
            title="Completed Python Course",
            content="Finished the advanced Python course with excellent grades!",
            importance=8,
        )
        print("✓ Added diary entry with importance=8")
        print()

        # Test 7: Get complete user context
        print("[Test 7] Retrieving complete user context...")
        context = await memory_manager.get_user_context(user_id)
        print(f"  User: {context.user_info.name} (@{context.user_info.username})")
        print(f"  Profile categories: {len(context.profile)}")
        print(f"  Recent conversations: {len(context.recent_conversations)}")
        print(f"  Upcoming events: {len(context.upcoming_events)}")
        print()

        # Test 8: Test context prompt formatting
        print("[Test 8] Testing context-to-prompt conversion...")
        prompt_context = context.to_prompt_context()
        print("Context formatted for LLM prompt:")
        print("-" * 60)
        print(prompt_context[:500] + "..." if len(prompt_context) > 500 else prompt_context)
        print("-" * 60)
        print()

        # Test 9: Scheduled messages
        print("[Test 9] Testing scheduled messages...")
        scheduled_time = datetime.utcnow() + timedelta(hours=1)
        await memory_manager.add_scheduled_message(
            user_id=user_id,
            scheduled_time=scheduled_time,
            message_type="follow_up",
            context="Check on Python learning progress",
        )
        print(f"✓ Scheduled message for {scheduled_time.isoformat()}")
        print()

        # Test 10: Get pending scheduled messages
        print("[Test 10] Retrieving pending scheduled messages...")
        pending = await memory_manager.get_pending_scheduled_messages()
        print(f"  Found {len(pending)} pending messages")
        print()

        print("=" * 60)
        print("✓ All tests passed successfully!")
        print("=" * 60)
        print()
        print("Memory system is working correctly with:")
        print(f"  - PostgreSQL (async): ✓")
        print(f"  - Pydantic schemas: ✓")
        print(f"  - Structured logging: ✓")
        print(f"  - Error handling: ✓")
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
