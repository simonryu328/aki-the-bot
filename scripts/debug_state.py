import asyncio
from memory.database_async import AsyncDatabase
from sqlalchemy import select
from memory.models import User

async def check():
    db = AsyncDatabase()
    async with db.get_session() as session:
        result = await session.execute(select(User.telegram_id, User.name, User.onboarding_state))
        for row in result.all():
            print(f"TG_ID: {row.telegram_id}, Name: {row.name}, State: {row.onboarding_state}")

if __name__ == "__main__":
    asyncio.run(check())
