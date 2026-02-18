
import asyncio
import os
import sys
from sqlalchemy import select, func

# Add project root to path
sys.path.append(os.getcwd())

from memory.database_async import db
from memory.models import TokenUsage

async def check_count():
    async with db.get_session() as session:
        stmt = select(func.count(TokenUsage.id))
        result = await session.execute(stmt)
        print(f"Total TokenUsage records: {result.scalar()}")
        
        # Also check most recent 5
        stmt_recent = select(TokenUsage).order_by(TokenUsage.timestamp.desc()).limit(5)
        result_recent = await session.execute(stmt_recent)
        recent = result_recent.scalars().all()
        print("\nLast 5 records:")
        for r in recent:
            print(f" - {r.timestamp}: {r.model} ({r.call_type})")

if __name__ == "__main__":
    asyncio.run(check_count())
