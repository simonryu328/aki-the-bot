#!/usr/bin/env python3
"""Send patch notes to a specific user via Telegram."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram import Bot
from config.settings import settings

PATCH_NOTES = """hey! 👋

i got some updates for you:

🎉 I can now react to your messages with emoji (like this message!)

💬 I'll check in with you when you've been quiet for a while
   • Use /reachout_settings to customize when I reach out

📝 I now create conversation summaries automatically
   • Type /compact to see them

🧠 I'm better at remembering our conversations
   • More natural and less robotic

that's it! let me know if anything feels off 🙂

- aki"""

async def send_patch_notes(user_id: int):
    """Send patch notes to a specific user."""
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    
    try:
        await bot.send_message(
            chat_id=user_id,
            text=PATCH_NOTES
        )
        print(f"✅ Patch notes sent successfully to user {user_id}")
    except Exception as e:
        print(f"❌ Failed to send patch notes: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/send_patch_notes.py <user_id>")
        sys.exit(1)
    
    user_id = int(sys.argv[1])
    asyncio.run(send_patch_notes(user_id))

# Made with Bob
