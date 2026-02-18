"""
Script to safely drop ONLY legacy database tables.
This preserves all current data in users, diary_entries, conversations, etc.
"""

import asyncio
import sys
from pathlib import Path
from sqlalchemy import text

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from memory.database_async import db
from core import configure_logging, get_logger

logger = get_logger(__name__)

LEGACY_TABLES = [
    "memorable_quotes",
    "personality_fragments",
    "user_preferences",
    "user_interests",
    "user_facts",
    "personality_traits",
    "user_knowledge",
    "user_values"
]

async def main():
    """Drop only legacy tables."""
    configure_logging(log_level="INFO")
    
    logger.info("Starting legacy table cleanup...")
    logger.info(f"Targeting tables: {', '.join(LEGACY_TABLES)}")

    try:
        async with db.get_session() as session:
            for table in LEGACY_TABLES:
                try:
                    # Check if table exists first (postgres specific or just try/except)
                    # We'll use IF EXISTS for simplicity
                    logger.info(f"Dropping table: {table}")
                    await session.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
                    await session.commit()
                except Exception as e:
                    logger.warning(f"Failed to drop {table}: {e}")
                    await session.rollback()
        
        logger.info("✓ Legacy tables cleaned up! Current data layout preserved.")

    except Exception as e:
        logger.error("Cleanup failed", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
