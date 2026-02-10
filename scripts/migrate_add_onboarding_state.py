"""
Migration script to add onboarding_state field to users table.

Adds:
- onboarding_state (string, nullable) - tracks onboarding progress: null (completed), 'awaiting_name', 'name_options_sent'
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
    """Add onboarding_state field to users table."""
    db = AsyncDatabase()
    
    try:
        async with db.get_session() as session:
            # Check if column already exists
            result = await session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='users' AND column_name='onboarding_state'
            """))
            
            if result.fetchone():
                logger.info("onboarding_state field already exists, skipping migration")
                return
            
            logger.info("Adding onboarding_state field to users table...")
            
            # Add onboarding_state column (nullable, null means onboarding complete)
            await session.execute(text("""
                ALTER TABLE users 
                ADD COLUMN onboarding_state VARCHAR(50)
            """))
            
            await session.commit()
            logger.info("✅ Successfully added onboarding_state field to users table")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        await db.engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())

# Made with Bob
