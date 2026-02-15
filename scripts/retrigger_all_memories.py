
import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from agents.soul_agent import soul_agent
from memory.memory_manager_async import memory_manager
from core import get_logger

logger = get_logger(__name__)

async def retrigger_all():
    print("Fetching all users...")
    users = await memory_manager.get_all_users()
    print(f"Found {len(users)} users.")
    
    for user in users:
        print(f"\nProcessing Group/User: {user.name} (ID: {user.id})")
        try:
            # This will now correctly check the threshold and summarize if needed
            # because of the fix in soul_agent.py
            await soul_agent._maybe_create_compact_summary(user.id)
        except Exception as e:
            print(f"Failed for user {user.id}: {e}")
            
    print("\nAll users processed.")

if __name__ == "__main__":
    asyncio.run(retrigger_all())
