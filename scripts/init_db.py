"""
Database initialization script.
Run this once to create all database tables.
"""

import sys
import logging

# Add parent directory to path for imports
sys.path.insert(0, ".")

from memory.database import db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Initialize the database."""
    try:
        logger.info("Starting database initialization...")

        # Create all tables
        db.create_tables()

        logger.info("✓ Database initialization complete!")
        logger.info("All tables created successfully.")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
