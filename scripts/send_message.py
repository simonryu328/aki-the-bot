#!/usr/bin/env python3
"""
Send a custom message to a user.

Usage:
    uv run python scripts/send_message.py <user_id> "<message>"
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram import Bot
from config.settings import settings
from memory.memory_manager_async import memory_manager


async def send_message(user_id: int, message: str):
    """Send a custom message to a user."""
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    
    try:
        # Get user info
        user = await memory_manager.db.get_user_by_id(user_id)
        if not user:
            print(f"❌ User {user_id} not found")
            return
        
        print(f"\n{'='*60}")
        print(f"  SENDING MESSAGE TO USER {user_id}")
        print(f"{'='*60}\n")
        print(f"User: {user.name} (@{user.username or 'N/A'})")
        print(f"Telegram ID: {user.telegram_id}\n")
        print(f"Message:\n{message}\n")
        print(f"{'='*60}\n")
        
        # Send the message
        await bot.send_message(
            chat_id=user.telegram_id,
            text=message
        )
        
        # Save to conversation history
        await memory_manager.add_conversation(
            user_id=user_id,
            role="assistant",
            message=message,
        )
        
        print(f"✅ Message sent successfully!")
        print(f"✅ Saved to conversation history")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print('Usage: python scripts/send_message.py <user_id> "<message>"')
        sys.exit(1)
    
    user_id = int(sys.argv[1])
    message = sys.argv[2]
    asyncio.run(send_message(user_id, message))

# Made with Bob
