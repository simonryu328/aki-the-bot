"""
Migration script to create the token_usage table.

Tracks LLM token consumption per user per call.
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
    """Create token_usage table."""
    db = AsyncDatabase()

    try:
        async with db.get_session() as session:
            # Check if table already exists
            result = await session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'token_usage'
                )
            """))

            if result.scalar():
                logger.info("token_usage table already exists, skipping migration")
                return

            logger.info("Creating token_usage table...")

            await session.execute(text("""
                CREATE TABLE token_usage (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    model VARCHAR(255) NOT NULL,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    call_type VARCHAR(100) NOT NULL,
                    timestamp TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """))

            # Add indexes for common queries
            await session.execute(text("""
                CREATE INDEX idx_token_usage_user_timestamp
                ON token_usage(user_id, timestamp DESC)
            """))

            await session.execute(text("""
                CREATE INDEX idx_token_usage_user_date
                ON token_usage(user_id, (timestamp::date))
            """))

            await session.commit()
            logger.info("✅ Successfully created token_usage table")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        await db.engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
