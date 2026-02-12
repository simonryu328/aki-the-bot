"""
Migration script to add missing indexes for performance optimization.

Adds:
- idx_conversations_user_timestamp on conversations(user_id, timestamp DESC)
- idx_users_reach_out on users(reach_out_enabled) WHERE reach_out_enabled = TRUE
- idx_profile_facts_user_category on profile_facts(user_id, category)
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from memory.database_async import AsyncDatabase
from core import get_logger

logger = get_logger(__name__)


async def migrate():
    """Add indexes to database tables."""
    db = AsyncDatabase()
    
    try:
        async with db.get_session() as session:
            logger.info("Starting index migration...")
            
            # 1. Conversations index
            try:
                logger.info("Adding idx_conversations_user_timestamp...")
                await session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_conversations_user_timestamp
                    ON conversations(user_id, timestamp DESC)
                """))
                logger.info("✓ Added idx_conversations_user_timestamp")
            except Exception as e:
                logger.warning(f"Could not add idx_conversations_user_timestamp: {e}")

            # 2. Users reach_out index (partial index)
            try:
                logger.info("Adding idx_users_reach_out...")
                # SQLite doesn't support partial indexes the same way Postgres does in all versions,
                # but SQLAlchemy/Postgres standard is what we're aiming for.
                # If using SQLite, standard index is fine.
                # We'll try the partial index syntax first (Postgres compatible).
                await session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_users_reach_out
                    ON users(reach_out_enabled) WHERE reach_out_enabled = TRUE
                """))
                logger.info("✓ Added idx_users_reach_out")
            except Exception as e:
                logger.warning(f"Partial index failed (might be SQLite limitation), trying standard index: {e}")
                try:
                    await session.execute(text("""
                        CREATE INDEX IF NOT EXISTS idx_users_reach_out
                        ON users(reach_out_enabled)
                    """))
                    logger.info("✓ Added standard idx_users_reach_out")
                except Exception as e2:
                    logger.error(f"Could not add idx_users_reach_out: {e2}")

            # 3. Profile facts composite index
            try:
                logger.info("Adding idx_profile_facts_user_category...")
                await session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_profile_facts_user_category
                    ON profile_facts(user_id, category)
                """))
                logger.info("✓ Added idx_profile_facts_user_category")
            except Exception as e:
                logger.warning(f"Could not add idx_profile_facts_user_category: {e}")
            
            await session.commit()
            logger.info("✅ Migration completed successfully")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        await db.engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
