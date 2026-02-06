#!/usr/bin/env python3
"""
Migration script to add thinking column to conversations table.

This stores the LLM's internal reasoning alongside assistant messages
for debugging and monitoring purposes.

Run with: python -m scripts.migrate_add_thinking
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from memory.database_async import AsyncDatabase
from core import get_logger

logger = get_logger(__name__)


async def migrate():
    """Add thinking column to conversations table."""
    db = AsyncDatabase()

    logger.info("Starting migration: add thinking to conversations")

    async with db.engine.begin() as conn:
        # Check if column already exists
        result = await conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'conversations' AND column_name = 'thinking'
        """))
        exists = result.fetchone() is not None

        if exists:
            logger.info("Column thinking already exists, skipping migration")
            return

        # Add the column (nullable, no default needed)
        logger.info("Adding thinking column...")
        await conn.execute(text("""
            ALTER TABLE conversations
            ADD COLUMN thinking TEXT
        """))

        logger.info("Migration complete: thinking column added to conversations")


async def rollback():
    """Remove thinking column (if needed)."""
    db = AsyncDatabase()

    logger.info("Rolling back: removing thinking from conversations")

    async with db.engine.begin() as conn:
        await conn.execute(text("""
            ALTER TABLE conversations
            DROP COLUMN IF EXISTS thinking
        """))

        logger.info("Rollback complete: thinking column removed")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Add thinking column to conversations")
    parser.add_argument("--rollback", action="store_true", help="Rollback the migration")
    args = parser.parse_args()

    if args.rollback:
        asyncio.run(rollback())
    else:
        asyncio.run(migrate())
