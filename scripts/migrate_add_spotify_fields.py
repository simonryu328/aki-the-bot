"""
Migration script to add Spotify-related fields to the users table.

Adds:
- spotify_access_token (Text)
- spotify_refresh_token (Text)
- spotify_token_expires_at (DateTime)
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
    """Add Spotify-related fields to users table."""
    db = AsyncDatabase()
    
    try:
        async with db.get_session() as session:
            # 1. Add spotify_access_token
            result = await session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='users' AND column_name='spotify_access_token'
            """))
            
            if not result.fetchone():
                logger.info("Adding spotify_access_token field...")
                await session.execute(text("ALTER TABLE users ADD COLUMN spotify_access_token TEXT"))
            else:
                logger.info("spotify_access_token already exists")

            # 2. Add spotify_refresh_token
            result = await session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='users' AND column_name='spotify_refresh_token'
            """))
            
            if not result.fetchone():
                logger.info("Adding spotify_refresh_token field...")
                await session.execute(text("ALTER TABLE users ADD COLUMN spotify_refresh_token TEXT"))
            else:
                logger.info("spotify_refresh_token already exists")

            # 3. Add spotify_token_expires_at
            result = await session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='users' AND column_name='spotify_token_expires_at'
            """))
            
            if not result.fetchone():
                logger.info("Adding spotify_token_expires_at field...")
                await session.execute(text("ALTER TABLE users ADD COLUMN spotify_token_expires_at TIMESTAMP WITHOUT TIME ZONE"))
            else:
                logger.info("spotify_token_expires_at already exists")
            
            await session.commit()
            logger.info("✅ Successfully updated users table with Spotify fields")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        await db.engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate())
