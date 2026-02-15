
import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from agents.soul_agent import soul_agent
from memory.memory_manager_async import memory_manager

async def force_trigger_check(user_id):
    print(f"Force triggering memory check for user_id: {user_id}")
    
    # Check if we have enough messages
    await soul_agent._maybe_create_compact_summary(user_id)
    
    # Wait for background tasks to finish since it uses asyncio.create_task internally
    # Wait, actually _maybe_create_compact_summary in my fix awaits the gather.
    # Let me check soul_agent.py again.
    
    print("Done check.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        uid = int(sys.argv[1])
    else:
        uid = 1
    asyncio.run(force_trigger_check(uid))
