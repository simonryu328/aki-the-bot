from datetime import datetime
import asyncio
from memory.database_async import AsyncDatabase
from sqlalchemy import select, desc
from memory.models import User

async def reset_last_active():
    db = AsyncDatabase()
    async with db.get_session() as session:
        # Find the most recently active user
        result = await session.execute(
            select(User).order_by(desc(User.last_interaction)).limit(1)
        )
        user = result.scalar_one_or_none()
        
        if user:
            print(f"Resetting state for {user.name} (TG: {user.telegram_id})...")
            user.onboarding_state = "awaiting_setup"
            await session.commit()
            print("Done.")
        else:
            print("No users found to reset.")

if __name__ == "__main__":
    asyncio.run(reset_last_active())
