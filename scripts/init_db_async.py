"""
Initialize database tables for the AI Companion.
Async version using production-grade database module.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from memory.database_async import db
from core import configure_logging, get_logger

logger = get_logger(__name__)


async def main():
    """Create all database tables."""
    configure_logging(log_level="INFO")

    logger.info("Starting database initialization")

    try:
        await db.create_tables()
        logger.info("✓ Database initialization complete!")

    except Exception as e:
        logger.error("Database initialization failed", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
