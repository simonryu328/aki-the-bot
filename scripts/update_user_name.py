#!/usr/bin/env python3
"""
Update a user's name in the database.

Usage:
    uv run python scripts/update_user_name.py <user_id> <new_name>
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.memory_manager_async import memory_manager


async def update_user_name(user_id: int, new_name: str):
    """Update user's name in database."""
    try:
        # Get current user info
        user = await memory_manager.db.get_user_by_id(user_id)
        if not user:
            print(f"❌ User {user_id} not found")
            return
        
        print(f"\n{'='*60}")
        print(f"  UPDATING USER NAME")
        print(f"{'='*60}\n")
        print(f"User ID: {user_id}")
        print(f"Old name: {user.name}")
        print(f"New name: {new_name}\n")
        
        # Update the name
        async with memory_manager.db.get_session() as session:
            from memory.models import User
            from sqlalchemy import select
            
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            db_user = result.scalar_one_or_none()
            
            if db_user:
                db_user.name = new_name
                await session.commit()
                print(f"✅ Successfully updated name to '{new_name}'")
            else:
                print(f"❌ User not found in database")
        
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/update_user_name.py <user_id> <new_name>")
        sys.exit(1)
    
    user_id = int(sys.argv[1])
    new_name = sys.argv[2]
    asyncio.run(update_user_name(user_id, new_name))

# Made with Bob
