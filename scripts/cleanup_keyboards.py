#!/usr/bin/env python3
"""
Cleanup script to remove legacy Telegram keyboards for all users.
Sends a message with ReplyKeyboardRemove to clear persistent custom keyboards.
"""

import asyncio
import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from telegram import Bot, ReplyKeyboardRemove
from config.settings import settings
from memory.database_async import db
from core import get_logger

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = get_logger(__name__)

CLEANUP_MESSAGE = "Finishing some system updates... 🛠️\n\nI've refreshed your menu to keep things clean and simple. You can just keep chatting like normal!"

async def cleanup_keyboards():
    """Iterate through all users and clear their persistent keyboards."""
    logger.info("=" * 60)
    logger.info("LEGACY KEYBOARD CLEANUP")
    logger.info("=" * 60)
    
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    
    try:
        # Get all users from the database
        users = await db.get_all_users()
        logger.info(f"Found {len(users)} users in database")
        
        if not users:
            logger.info("No users found to process.")
            return

        success_count = 0
        fail_count = 0
        
        for user in users:
            try:
                logger.info(f"Processing user {user.id} (Telegram ID: {user.telegram_id})...")
                
                # Send message with ReplyKeyboardRemove
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=CLEANUP_MESSAGE,
                    reply_markup=ReplyKeyboardRemove()
                )
                
                logger.info(f"   ✅ Keyboard cleared for user {user.id}")
                success_count += 1
                
                # Brief sleep to avoid hitting Telegram API limits
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"   ❌ Failed to clear keyboard for user {user.id}: {e}")
                fail_count += 1
        
        logger.info("\n" + "=" * 60)
        logger.info("CLEANUP SUMMARY")
        logger.info("-" * 60)
        logger.info(f"Total Users: {len(users)}")
        logger.info(f"Successful:  {success_count}")
        logger.info(f"Failed:      {fail_count}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Critical error during cleanup: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(cleanup_keyboards())
