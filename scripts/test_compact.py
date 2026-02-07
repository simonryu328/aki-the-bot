#!/usr/bin/env python3
"""
Test script for compact summarization feature.

Usage:
    uv run python scripts/test_compact.py <user_id>
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


async def test_compact(user_id: int):
    """Test compact summarization for a specific user."""
    from memory.memory_manager_async import memory_manager
    from agents.soul_agent import soul_agent
    from schemas import UserContextSchema

    # Get user info
    user = await memory_manager.get_user_by_id(user_id)
    if not user:
        print(f"User {user_id} not found.")
        return

    user_name = user.name or "them"
    print(f"Testing compact summarization for user {user_id} ({user_name})...")

    # Get user context
    context = await memory_manager.get_user_context(user_id)
    
    # Build profile context (similar to what respond() does)
    profile_context = soul_agent._build_profile_context(context)
    
    print(f"\n{'='*60}")
    print(f"PROFILE CONTEXT ({len(profile_context)} chars)")
    print(f"{'='*60}")
    print(profile_context)
    print(f"{'='*60}\n")

    # Get recent conversations
    recent_convos = await memory_manager.db.get_recent_conversations(user_id, limit=20)
    print(f"Recent conversations: {len(recent_convos)} messages")
    
    if not recent_convos:
        print("No conversations to summarize.")
        return

    # Show first and last message timestamps
    if recent_convos:
        first = recent_convos[0]
        last = recent_convos[-1]
        print(f"First message: {first.timestamp}")
        print(f"Last message: {last.timestamp}")

    # Run compact summarization
    print("\nRunning compact summarization...")
    await soul_agent._create_compact_summary(
        user_id=user_id,
        profile_context=profile_context,
    )

    # Get the most recent diary entry (should be the compact summary)
    diary_entries = await memory_manager.get_diary_entries(user_id, limit=5)
    
    print(f"\nRecent diary entries: {len(diary_entries)}")
    for entry in diary_entries:
        if entry.entry_type == "compact_summary":
            print(f"\n✅ Compact Summary (created at {entry.timestamp}):")
            print(f"Title: {entry.title}")
            print(f"Content:\n{entry.content}")
            print()
            break
    else:
        print("\n⚠️ No compact summary found in diary entries")

    # Show the last compact prompt for debugging
    if user_id in soul_agent._last_compact_prompt:
        print("\n--- Last Compact Prompt (first 500 chars) ---")
        print(soul_agent._last_compact_prompt[user_id][:500])
        print("...")


def main():
    parser = argparse.ArgumentParser(description="Test compact summarization")
    parser.add_argument("user_id", type=int, help="User ID to test compact summarization for")
    args = parser.parse_args()
    asyncio.run(test_compact(args.user_id))


if __name__ == "__main__":
    main()

# Made with Bob
