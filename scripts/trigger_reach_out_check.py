#!/usr/bin/env python3
"""
Manually trigger the reach-out scheduler check.

This runs the same logic as the automatic scheduler, checking all users
and sending reach-out messages to those who meet the criteria.

Usage:
    uv run python scripts/trigger_reach_out_check.py
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
from agents.soul_agent import soul_agent


async def generate_reach_out_message(user_id: int, hours_since_last_message: int):
    """Generate a reach-out message (copied from telegram_handler)."""
    try:
        # Get user context
        user_context = await memory_manager.get_user_context(user_id)
        
        # Build profile context
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
        if hours_since_last_message < 24:
            time_since = f"{hours_since_last_message} hours"
        else:
            days = hours_since_last_message // 24
            time_since = f"{days} day{'s' if days > 1 else ''}"
        
        # Get persona
        persona = soul_agent.persona
        
        # Generate the message
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
        
        return message.strip()
        
    except Exception as e:
        print(f"  ❌ Failed to generate message: {e}")
        return None


async def trigger_reach_out_check():
    """Manually trigger the reach-out scheduler check."""
    print(f"\n{'='*60}")
    print("  MANUAL REACH-OUT SCHEDULER TRIGGER")
    print(f"{'='*60}\n")
    
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    
    try:
        # Get all users
        all_users = await memory_manager.get_all_users()
        
        if not all_users:
            print("No users found in database.")
            return
        
        print(f"Checking {len(all_users)} users for inactivity reach-outs...\n")
        
        tz = pytz.timezone(settings.TIMEZONE)
        now = datetime.now(tz)
        sent_count = 0
        
        for user in all_users:
            try:
                print(f"Checking user {user.id} ({user.name})...")
                
                # Skip if reach-out disabled
                if not user.reach_out_enabled:
                    print(f"  ⏭️  Reach-out disabled for this user\n")
                    continue
                
                # Get user's last message
                last_user_msg = await memory_manager.get_last_user_message(user.id)
                
                if not last_user_msg:
                    print(f"  ⏭️  No messages from user yet\n")
                    continue
                
                # Calculate hours since last message
                msg_time = last_user_msg.timestamp
                if msg_time.tzinfo is None:
                    msg_time = tz.localize(msg_time)
                
                hours_since = (now - msg_time).total_seconds() / 3600
                
                # Check if within reach-out window
                min_hours = user.reach_out_min_silence_hours or settings.DEFAULT_REACH_OUT_MIN_SILENCE_HOURS
                max_days = user.reach_out_max_silence_days or settings.DEFAULT_REACH_OUT_MAX_SILENCE_DAYS
                max_hours = max_days * 24
                
                print(f"  Hours since last message: {hours_since:.1f}")
                print(f"  Reach-out window: {min_hours}-{max_hours} hours")
                
                if hours_since < min_hours:
                    print(f"  ⏭️  Too soon (need {min_hours - hours_since:.1f} more hours)\n")
                    continue
                
                if hours_since > max_hours:
                    print(f"  ⏭️  Too late (exceeded by {hours_since - max_hours:.1f} hours)\n")
                    continue
                
                # Rate limit check
                if user.last_reach_out_at:
                    last_reach_out = user.last_reach_out_at
                    if last_reach_out.tzinfo is None:
                        last_reach_out = tz.localize(last_reach_out)
                    
                    hours_since_last_reach_out = (now - last_reach_out).total_seconds() / 3600
                    
                    if hours_since_last_reach_out < min_hours:
                        print(f"  ⏭️  Rate limited (last reach-out {hours_since_last_reach_out:.1f} hours ago)\n")
                        continue
                
                # Generate and send reach-out
                print(f"  ✅ Eligible for reach-out! Generating message...")
                message_text = await generate_reach_out_message(
                    user_id=user.id,
                    hours_since_last_message=int(hours_since),
                )
                
                if message_text:
                    print(f"  📤 Sending: {message_text[:100]}...")
                    
                    # Send the message
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=message_text
                    )
                    sent_count += 1
                    
                    # Store in conversation history
                    await memory_manager.add_conversation(
                        user_id=user.id,
                        role="assistant",
                        message=message_text,
                        store_in_vector=False,
                    )
                    
                    # Update last reach-out timestamp
                    await memory_manager.update_user_reach_out_timestamp(user.id, now)
                    
                    print(f"  ✅ Sent successfully!\n")
                else:
                    print(f"  ❌ Failed to generate message\n")
                    
            except Exception as e:
                print(f"  ❌ Error processing user {user.id}: {e}\n")
                continue
        
        print(f"{'='*60}")
        print(f"  SUMMARY")
        print(f"{'='*60}")
        print(f"Total users checked: {len(all_users)}")
        print(f"Messages sent: {sent_count}")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(trigger_reach_out_check())

# Made with Bob
