
import asyncio
import os
import sys
from sqlalchemy import select

# Add project root to path
sys.path.append(os.getcwd())

from memory.database_async import db
from memory.models import TokenUsage

async def list_models():
    async with db.get_session() as session:
        stmt = select(TokenUsage.model).distinct()
        result = await session.execute(stmt)
        models = [row[0] for row in result.all()]
        print("Models in database:")
        for m in models:
            print(f" - {m}")

if __name__ == "__main__":
    asyncio.run(list_models())
