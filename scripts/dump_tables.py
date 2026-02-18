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

async def main():
    """Dump all table linkes to a file."""
    configure_logging(log_level="INFO")
    
    try:
        async with db.get_session() as session:
            result = await session.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
                ORDER BY table_name;
            """))
            tables = [row[0] for row in result.fetchall()]
            
            with open("db_schema_snapshot.txt", "w") as f:
                f.write(f"Found {len(tables)} tables:\n")
                for t in tables:
                    f.write(f"{t}\n")
            
            logger.info(f"Dumped {len(tables)} tables to db_schema_snapshot.txt")

    except Exception as e:
        logger.error("Dump failed", error=str(e), exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
