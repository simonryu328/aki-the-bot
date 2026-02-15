
import asyncio
import os
import sys
from sqlalchemy import text, create_engine

# Add project root to path
sys.path.append(os.getcwd())

from config.settings import settings

def migrate_sync(db_url):
    print(f"Migrating {db_url.split('@')[-1]}...")
    try:
        engine = create_engine(db_url)
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE token_usage ADD COLUMN IF NOT EXISTS cache_read_tokens INTEGER DEFAULT 0"))
            conn.execute(text("ALTER TABLE token_usage ADD COLUMN IF NOT EXISTS cache_creation_tokens INTEGER DEFAULT 0"))
        print("Success.")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    # Migrate Railway (from env)
    migrate_sync(settings.DATABASE_URL)
    
    # Also try common local DB just in case the dashboard is stuck on it
    local_url = "postgresql://postgres:postgres@localhost:5432/ai_companion"
    migrate_sync(local_url)
