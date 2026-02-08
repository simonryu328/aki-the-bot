#!/usr/bin/env python3
"""
Manually trigger and send a reach-out message to a user.

Usage:
    uv run python scripts/send_reach_out.py <user_id> [hours_since_last_message]
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
import pytz

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram import Bot
from config.settings import settings
from prompts import REACH_OUT_PROMPT
from utils.llm_client import llm_client
from memory.memory_manager_async import memory_manager


async def send_reach_out(user_id: int, hours_since: int = 24):
    """Generate and send a reach-out message."""
    print(f"\n{'='*60}")
    print(f"  SENDING REACH-OUT TO USER {user_id}")
    print(f"{'='*60}\n")
    
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    
    try:
        # Get user info
        user = await memory_manager.db.get_user_by_id(user_id)
        if not user:
            print(f"❌ User {user_id} not found")
            return
        
        print(f"User: {user.name} (@{user.username or 'N/A'})")
        print(f"Telegram ID: {user.telegram_id}")
        print(f"Simulating: {hours_since} hours since last message\n")
        
        # Get user context
        user_context = await memory_manager.get_user_context(user_id)
        
        # Build profile context
        from agents.soul_agent import soul_agent
        profile_context = soul_agent._build_profile_context(user_context)
        
        # Get recent conversations
        tz = pytz.timezone(settings.TIMEZONE)
        now = datetime.now(tz)
        current_time = now.strftime("%A, %B %d, %Y at %I:%M %p")
        
        conversations = await memory_manager.db.get_recent_conversations(user_id, limit=20)
        if conversations:
            history_lines = []
            for conv in conversations:
                role = "Them" if conv.role == "user" else "You"
                if conv.timestamp:
                    utc_time = conv.timestamp.replace(tzinfo=pytz.utc)
                    local_time = utc_time.astimezone(tz)
                    ts = local_time.strftime("%Y-%m-%d %H:%M")
                else:
                    ts = ""
                history_lines.append(f"[{ts}] {role}: {conv.message}")
            conversation_history = "\n".join(history_lines)
        else:
            conversation_history = "(No recent conversation)"
        
        # Get compact summaries
        diary_entries = await memory_manager.get_diary_entries(user_id, limit=3)
        compact_summaries = []
        for entry in diary_entries:
            if entry.entry_type == "compact_summary":
                compact_summaries.append(entry.content)
        compact_text = "\n\n".join(compact_summaries) if compact_summaries else "(No summaries yet)"
        
        # Format time since
        if hours_since < 24:
            time_since = f"{hours_since} hours"
        else:
            days = hours_since // 24
            time_since = f"{days} day{'s' if days > 1 else ''}"
        
        # Get persona
        persona = soul_agent.persona
        
        # Generate the message
        print("Generating reach-out message...\n")
        prompt = REACH_OUT_PROMPT.format(
            current_time=current_time,
            time_since=time_since,
            persona=persona,
            profile_context=profile_context,
            conversation_history=conversation_history,
            compact_summaries=compact_text,
        )
        
        message = await llm_client.chat(
            model=settings.MODEL_PROACTIVE,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=200,
        )
        
        message = message.strip()
        
        print(f"{'='*60}")
        print("  GENERATED MESSAGE")
        print(f"{'='*60}\n")
        print(message)
        print(f"\n{'='*60}\n")
        
        # Send the message
        print("Sending message to Telegram...")
        await bot.send_message(
            chat_id=user.telegram_id,
            text=message
        )
        
        print(f"✅ Message sent successfully to {user.name}!")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/send_reach_out.py <user_id> [hours_since_last_message]")
        sys.exit(1)
    
    user_id = int(sys.argv[1])
    hours_since = int(sys.argv[2]) if len(sys.argv) > 2 else 24
    asyncio.run(send_reach_out(user_id, hours_since))

# Made with Bob
