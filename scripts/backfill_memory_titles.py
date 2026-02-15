
import asyncio
import sys
import os
from typing import List

# Add parent directory to path to allow importing modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.memory_manager_async import memory_manager
from utils.llm_client import llm_client
from config.settings import settings
from core import get_logger

logger = get_logger(__name__)

TITLE_GENERATION_PROMPT = """You are Aki's memory processor. Your task is to generate a short, evocative title for a conversation memory.

Memory Entry:
{content}

---
Based on the content above, create a short title (3-6 words) that captures the essence of this memory. 
Return ONLY the title. No quotes, no prefix, no extra text.
"""

async def backfill_titles():
    """Find all conversation memories with placeholder titles and generate better ones."""
    logger.info("Starting memory title backfill...")
    
    # 1. Get all users
    users = await memory_manager.get_all_users()
    total_updated = 0
    total_scanned = 0
    
    for user in users:
        logger.info(f"Processing user: {user.name} (ID: {user.id})")
        
        # 2. Get all journal entries for this user
        # We fetch a large number to ensure we get most of them
        entries = await memory_manager.get_diary_entries(user.id, limit=500, entry_type="conversation_memory")
        
        for entry in entries:
            total_scanned += 1
            # Check if it has a placeholder title
            if entry.title == "Conversation Memory" or not entry.title:
                logger.info(f"Generating title for entry {entry.id}...")
                
                try:
                    # 3. Generate title using LLM
                    prompt = TITLE_GENERATION_PROMPT.format(content=entry.content)
                    title = await llm_client.chat(
                        model=settings.MODEL_MEMORY,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                        max_tokens=50
                    )
                    
                    title = title.strip().strip('"').strip("'")
                    
                    if title:
                        # 4. Update entry in database
                        await memory_manager.update_diary_entry(entry.id, title=title)
                        logger.info(f"Updated entry {entry.id} with title: {title}")
                        total_updated += 1
                    else:
                        logger.warning(f"LLM returned empty title for entry {entry.id}")
                        
                except Exception as e:
                    logger.error(f"Failed to generate title for entry {entry.id}: {e}")
            else:
                logger.debug(f"Entry {entry.id} already has a title: {entry.title}")

    logger.info(f"Backfill complete! Scanned {total_scanned} entries, updated {total_updated} titles.")

if __name__ == "__main__":
    asyncio.run(backfill_titles())
