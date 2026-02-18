"""
Inspect database schema to find all tables and foreign keys.
Useful for identifying legacy tables blocking deletions.
"""

import asyncio
import sys
from pathlib import Path
from sqlalchemy import text, inspect

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from memory.database_async import db
from core import configure_logging, get_logger

logger = get_logger(__name__)

async def main():
    """List all tables and their foreign keys."""
    configure_logging(log_level="INFO")
    
    logger.info("Inspecting database schema...")

    try:
        async with db.get_session() as session:
            # PostgreSQL specific query to find all tables
            result = await session.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE';
            """))
            tables = [row[0] for row in result.fetchall()]
            
            logger.info(f"Found {len(tables)} tables in database:")
            for table in tables:
                logger.info(f"  - {table}")
                
            logger.info("\nChecking for foreign keys referencing 'users' or 'diary_entries'...")
            
            # Query to find FKs
            fk_query = text("""
                SELECT
                    tc.table_name, 
                    kcu.column_name, 
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name 
                FROM 
                    information_schema.table_constraints AS tc 
                    JOIN information_schema.key_column_usage AS kcu
                      ON tc.constraint_name = kcu.constraint_name
                      AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu
                      ON ccu.constraint_name = tc.constraint_name
                      AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                AND ccu.table_name IN ('users', 'diary_entries');
            """)
            
            fks = await session.execute(fk_query)
            for row in fks:
                referencing_table = row[0]
                referencing_col = row[1]
                target_table = row[2]
                logger.info(f"  - Table '{referencing_table}.{referencing_col}' -> '{target_table}.id'")
                
            # Check for any tables found that are NOT in our known list
            # Known tables from current models.py (approximate list)
            known_tables = [
                "users", "conversations", "diary_entries", 
                "token_usage", "future_entries", "alembic_version"
            ]
            
            unknown_tables = [t for t in tables if t not in known_tables]
            if unknown_tables:
                logger.warning(f"\n⚠️  POTENTIAL LEGACY TABLES FOUND ({len(unknown_tables)}):")
                for t in unknown_tables:
                    logger.warning(f"  - {t}")
            else:
                logger.info("\n✓ No unknown tables found.")

    except Exception as e:
        logger.error("Inspection failed", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
