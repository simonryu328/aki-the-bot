
import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from memory.database_async import db
from memory.models import User
from sqlalchemy import select

async def debug_user(uid):
    print(f"Debugging user {uid}...")
    async with db.get_session() as session:
        result = await session.execute(select(User).where(User.id == uid))
        user = result.scalar_one_or_none()
        if not user:
            print("User not found")
            return
        
        print(f"Name: {user.name}")
        print(f"Reach-out enabled: {user.reach_out_enabled}")
        print(f"Min silence: {user.reach_out_min_silence_hours}")
        print(f"Max silence: {user.reach_out_max_silence_days}")
        print(f"Last reach-out: {user.last_reach_out_at}")

if __name__ == "__main__":
    uid = 1
    if len(sys.argv) > 1:
        uid = int(sys.argv[1])
    asyncio.run(debug_user(uid))
