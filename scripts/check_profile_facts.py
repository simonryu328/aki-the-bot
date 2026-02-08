#!/usr/bin/env python3
"""Check profile facts for a user."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.memory_manager_async import memory_manager
from sqlalchemy import select
from memory.models import ProfileFact


async def check_facts(user_id: int):
    """Check profile facts for a user."""
    user = await memory_manager.db.get_user_by_id(user_id)
    if not user:
        print(f"User {user_id} not found")
        return
    
    print(f"\nProfile facts for {user.name} (ID: {user_id}):\n")
    
    # Query profile facts directly
    async with memory_manager.db.get_session() as session:
        result = await session.execute(
            select(ProfileFact)
            .where(ProfileFact.user_id == user_id)
            .order_by(ProfileFact.observed_at.desc())
        )
        facts = result.scalars().all()
    
    if not facts:
        print("No profile facts found")
        return
    
    for fact in facts:
        print(f"[{fact.category}] {fact.value}")
        print(f"  Observed: {fact.observed_at}")
        print(f"  Confidence: {fact.confidence}")
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/check_profile_facts.py <user_id>")
        sys.exit(1)
    
    user_id = int(sys.argv[1])
    asyncio.run(check_facts(user_id))

# Made with Bob
