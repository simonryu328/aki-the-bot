#!/usr/bin/env python3
"""
Migration script to add observed_at column to profile_facts table.

This adds timestamp tracking for when observations were first made.
Existing rows will have observed_at set to their updated_at value.

Run with: python -m scripts.migrate_add_observed_at
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
    """Add observed_at column to profile_facts table."""
    db = AsyncDatabase()

    logger.info("Starting migration: add observed_at to profile_facts")

    async with db.engine.begin() as conn:
        # Check if column already exists
        result = await conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'profile_facts' AND column_name = 'observed_at'
        """))
        exists = result.fetchone() is not None

        if exists:
            logger.info("Column observed_at already exists, skipping migration")
            return

        # Add the column (nullable first)
        logger.info("Adding observed_at column...")
        await conn.execute(text("""
            ALTER TABLE profile_facts
            ADD COLUMN observed_at TIMESTAMP
        """))

        # Populate with existing updated_at values
        logger.info("Populating observed_at with existing updated_at values...")
        await conn.execute(text("""
            UPDATE profile_facts
            SET observed_at = updated_at
            WHERE observed_at IS NULL
        """))

        # Make it non-nullable with default
        logger.info("Setting column constraints...")
        await conn.execute(text("""
            ALTER TABLE profile_facts
            ALTER COLUMN observed_at SET NOT NULL,
            ALTER COLUMN observed_at SET DEFAULT NOW()
        """))

        logger.info("✓ Migration complete: observed_at column added to profile_facts")


async def rollback():
    """Remove observed_at column (if needed)."""
    db = AsyncDatabase()

    logger.info("Rolling back: removing observed_at from profile_facts")

    async with db.engine.begin() as conn:
        await conn.execute(text("""
            ALTER TABLE profile_facts
            DROP COLUMN IF EXISTS observed_at
        """))

        logger.info("✓ Rollback complete: observed_at column removed")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Add observed_at column to profile_facts")
    parser.add_argument("--rollback", action="store_true", help="Rollback the migration")
    args = parser.parse_args()

    if args.rollback:
        asyncio.run(rollback())
    else:
        asyncio.run(migrate())
