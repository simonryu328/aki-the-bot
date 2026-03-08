import asyncio
import os
from sqlalchemy import text
from memory.database_async import db

async def migrate():
    print("Starting migration: Add Google OAuth fields to users table...")
    async with db.get_session() as session:
        # Check if columns already exist
        result = await session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' AND column_name='google_access_token';
        """))
        if result.fetchone():
            print("Columns already exist. Skipping.")
            return

        # Add columns
        await session.execute(text("""
            ALTER TABLE users 
            ADD COLUMN google_access_token TEXT,
            ADD COLUMN google_refresh_token TEXT,
            ADD COLUMN google_token_expires_at TIMESTAMP,
            ADD COLUMN google_scopes TEXT;
        """))
        # session.commit() is handled by get_session context manager
    print("Migration complete!")

if __name__ == "__main__":
    asyncio.run(migrate())
