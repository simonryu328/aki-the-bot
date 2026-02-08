#!/usr/bin/env python3
"""Test compact summary integration in system frame."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.memory_manager_async import memory_manager
from agents.soul_agent import SoulAgent


async def test_compact_context(user_id: int = 1):
    """Test the compact context building."""
    print(f"\n{'='*60}")
    print(f"Testing Compact Context for User {user_id}")
    print(f"{'='*60}\n")
    
    # Get user context
    context = await memory_manager.get_user_context(user_id)
    print(f"✓ Got user context for: {context.user_info.name}")
    
    # Get recent conversations
    recent_convos = await memory_manager.db.get_recent_conversations(user_id, limit=20)
    print(f"✓ Got {len(recent_convos)} recent conversations")
    
    # Initialize agent
    agent = SoulAgent()
    
    # Build conversation context (this is the new method)
    recent_exchanges, current_conversation = await agent._build_conversation_context(
        user_id, recent_convos
    )
    
    print(f"\n{'='*60}")
    print("RECENT EXCHANGES:")
    print(f"{'='*60}")
    print(recent_exchanges)
    
    print(f"\n{'='*60}")
    print("CURRENT CONVERSATION:")
    print(f"{'='*60}")
    print(current_conversation)
    
    print(f"\n{'='*60}")
    print("✅ Test Complete!")
    print(f"{'='*60}\n")


async def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        user_id = int(sys.argv[1])
    else:
        user_id = 1
    
    await test_compact_context(user_id)


if __name__ == "__main__":
    asyncio.run(main())

# Made with Bob
