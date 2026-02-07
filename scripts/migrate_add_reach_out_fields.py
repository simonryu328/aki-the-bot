"""
Migration script to add reach-out configuration fields to users table.

Adds:
- reach_out_enabled (boolean, default True)
- reach_out_min_silence_hours (integer, default 6)
- reach_out_max_silence_days (integer, default 3)
- last_reach_out_at (datetime, nullable)
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from memory.database_async import AsyncDatabase
from config.settings import settings
from core import get_logger

logger = get_logger(__name__)


async def migrate():
    """Add reach-out fields to users table."""
    db = AsyncDatabase()
    
    try:
        async with db.get_session() as session:
            # Check if columns already exist
            result = await session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='users' AND column_name='reach_out_enabled'
            """))
            
            if result.fetchone():
                logger.info("Reach-out fields already exist, skipping migration")
                return
            
            logger.info("Adding reach-out fields to users table...")
            
            # Add reach_out_enabled column
            await session.execute(text("""
                ALTER TABLE users 
                ADD COLUMN reach_out_enabled BOOLEAN DEFAULT TRUE NOT NULL
            """))
            
            # Add reach_out_min_silence_hours column
            await session.execute(text("""
                ALTER TABLE users 
                ADD COLUMN reach_out_min_silence_hours INTEGER DEFAULT 6 NOT NULL
            """))
            
            # Add reach_out_max_silence_days column
            await session.execute(text("""
                ALTER TABLE users 
                ADD COLUMN reach_out_max_silence_days INTEGER DEFAULT 3 NOT NULL
            """))
            
            # Add last_reach_out_at column
            await session.execute(text("""
                ALTER TABLE users 
                ADD COLUMN last_reach_out_at TIMESTAMP
            """))
            
            await session.commit()
            logger.info("✅ Successfully added reach-out fields to users table")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        await db.engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())

# Made with Bob
