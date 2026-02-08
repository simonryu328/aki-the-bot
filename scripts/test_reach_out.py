#!/usr/bin/env python3
"""
Test reach-out message generation without sending.

Usage:
    uv run python scripts/test_reach_out.py <user_id> [hours_since_last_message]
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
import pytz

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from prompts import REACH_OUT_PROMPT
from utils.llm_client import llm_client
from memory.memory_manager_async import memory_manager


async def test_reach_out(user_id: int, hours_since: int = 24):
    """Generate a reach-out message for testing."""
    print(f"\n{'='*60}")
    print(f"  TESTING REACH-OUT MESSAGE FOR USER {user_id}")
    print(f"{'='*60}\n")
    
    try:
        # Get user info
        user = await memory_manager.db.get_user_by_id(user_id)
        if not user:
            print(f"❌ User {user_id} not found")
            return
        
        print(f"User: {user.name} (@{user.username or 'N/A'})")
        print(f"Telegram ID: {user.telegram_id}")
        print(f"Simulating: {hours_since} hours since last message\n")
        
        user_name = user.name or "friend"
        
        # Get timezone
        tz = pytz.timezone(settings.TIMEZONE)
        now = datetime.now(tz)
        current_time = now.strftime("%A, %B %d, %Y at %I:%M %p")

        # Get recent compact summaries
        diary_entries = await memory_manager.get_diary_entries(user_id, limit=settings.DIARY_FETCH_LIMIT)
        compact_summaries = []
        last_compact_end = None
        
        for entry in diary_entries:
            if entry.entry_type == "compact_summary":
                # Format with timestamp
                if entry.exchange_start and entry.exchange_end:
                    start_time = entry.exchange_start.replace(tzinfo=pytz.utc).astimezone(tz)
                    end_time = entry.exchange_end.replace(tzinfo=pytz.utc).astimezone(tz)
                    compact_summaries.append(
                        f"[START: {start_time.strftime('%Y-%m-%d %H:%M')}] "
                        f"[END: {end_time.strftime('%Y-%m-%d %H:%M')}]\n{entry.content}"
                    )
                    # Track the most recent compact's end time
                    if last_compact_end is None or entry.exchange_end > last_compact_end:
                        last_compact_end = entry.exchange_end
        
        # Limit to configured number of compacts
        compact_summaries = compact_summaries[:settings.COMPACT_SUMMARY_LIMIT]
        
        # Build RECENT EXCHANGES section
        if compact_summaries:
            recent_exchanges = "RECENT EXCHANGES:\n" + "\n\n".join(compact_summaries)
        else:
            recent_exchanges = ""

        # Get current conversations (only messages AFTER last compact)
        if last_compact_end:
            # Query conversations after the last compact's end time
            conversations = await memory_manager.db.get_conversations_after(
                user_id=user_id,
                after=last_compact_end,
                limit=20
            )
        else:
            # No compacts yet, get recent conversations
            conversations = await memory_manager.db.get_recent_conversations(user_id, limit=20)

        # Build CURRENT CONVERSATION section
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
            current_conversation = "CURRENT CONVERSATION:\n" + "\n".join(history_lines)
        else:
            current_conversation = "CURRENT CONVERSATION:\n(No recent messages)"
        
        # Format time since
        if hours_since < 24:
            time_since = f"{hours_since} hours"
        else:
            days = hours_since // 24
            time_since = f"{days} day{'s' if days > 1 else ''}"
        
        # Get persona
        from agents.soul_agent import soul_agent
        persona = soul_agent.persona
        
        # Generate the message
        print("Generating reach-out message...\n")
        prompt = REACH_OUT_PROMPT.format(
            current_time=current_time,
            time_since=time_since,
            persona=persona,
            user_name=user_name,
            recent_exchanges=recent_exchanges,
            current_conversation=current_conversation,
        )
        
        print(f"{'='*60}")
        print("  FULL PROMPT")
        print(f"{'='*60}\n")
        print(prompt)
        print(f"\n{'='*60}\n")
        
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
        print(f"\n{'='*60}")
        print(f"Message length: {len(message)} characters")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_reach_out.py <user_id> [hours_since_last_message]")
        sys.exit(1)
    
    user_id = int(sys.argv[1])
    hours_since = int(sys.argv[2]) if len(sys.argv) > 2 else 24
    asyncio.run(test_reach_out(user_id, hours_since))

# Made with Bob
