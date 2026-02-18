
import asyncio
import logging
import os
import sys

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.database_async import db
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate():
    """
    Adds performance indexes to key tables to speed up the dashboard and journal.
    """
    indexes = [
        # Diary entries: critical for journal and dashboard
        "CREATE INDEX IF NOT EXISTS idx_diary_entries_user_id_type_ts ON diary_entries (user_id, entry_type, timestamp DESC)",
        
        # Token usage: needed for daily message generation / budget checking
        "CREATE INDEX IF NOT EXISTS idx_token_usage_user_id_ts ON token_usage (user_id, timestamp DESC)",
        
        # Conversations: needed for orchestrator history fetching
        "CREATE INDEX IF NOT EXISTS idx_conversations_user_id_ts ON conversations (user_id, timestamp DESC)",
        
        # Future entries: needed for horizons list
        "CREATE INDEX IF NOT EXISTS idx_future_entries_user_id_completed_ts ON future_entries (user_id, is_completed, start_time DESC)",
        
        # Profile facts: needed for soul agent context
        "CREATE INDEX IF NOT EXISTS idx_profile_facts_user_id ON profile_facts (user_id)"
    ]
    
    logger.info("Starting performance index migration...")
    
    async with db.get_session() as session:
        for cmd in indexes:
            try:
                logger.info(f"Executing: {cmd}")
                await session.execute(text(cmd))
                await session.commit()
            except Exception as e:
                logger.error(f"Failed to execute {cmd}: {e}")
                
    logger.info("Migration complete!")

if __name__ == "__main__":
    asyncio.run(migrate())
