#!/usr/bin/env python3
"""Backfill missing compact summaries for messages that weren't compacted due to bot restarts."""

import asyncio
import sys
from pathlib import Path
import pytz
import structlog
from typing import List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.memory_manager_async import memory_manager
from utils.llm_client import llm_client
from config.settings import settings
from prompts import COMPACT_PROMPT

logger = structlog.get_logger()


async def create_compact_for_batch(
    user_id: int,
    batch: List,
    user_name: str,
    profile_context: str,
) -> bool:
    """Create a compact summary for a specific batch of conversations.
    
    Args:
        user_id: User ID
        batch: List of conversation objects
        user_name: User's name
        profile_context: Profile context string
        
    Returns:
        True if successful, False otherwise
    """
    try:
        tz = pytz.timezone(settings.TIMEZONE)
        
        # Extract start and end times
        first_conv = batch[0]
        last_conv = batch[-1]
        
        if first_conv.timestamp:
            utc_start = first_conv.timestamp.replace(tzinfo=pytz.utc)
            start_time = utc_start.astimezone(tz).strftime("%Y-%m-%d %H:%M")
        else:
            start_time = "unknown"
        
        if last_conv.timestamp:
            utc_end = last_conv.timestamp.replace(tzinfo=pytz.utc)
            end_time = utc_end.astimezone(tz).strftime("%Y-%m-%d %H:%M")
        else:
            end_time = "unknown"
        
        # Format conversations with timestamps
        convo_lines = []
        for conv in batch:
            role = "Them" if conv.role == "user" else "You"
            if conv.timestamp:
                utc_time = conv.timestamp.replace(tzinfo=pytz.utc)
                local_time = utc_time.astimezone(tz)
                ts = local_time.strftime("%Y-%m-%d %H:%M")
            else:
                ts = ""
            convo_lines.append(f"[{ts}] {role}: {conv.message}")
        recent_conversation = "\n".join(convo_lines)
        
        # Build prompt
        prompt = COMPACT_PROMPT.format(
            user_name=user_name,
            profile_context=profile_context,
            start_time=start_time,
            end_time=end_time,
            recent_conversation=recent_conversation,
        )
        
        # Generate summary
        result = await llm_client.chat(
            model=settings.MODEL_MEMORY,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=800,
        )
        
        # Store summary
        if result and "SUMMARY:" in result:
            summary_content = result.split("SUMMARY:", 1)[1].strip()
            
            # Store in diary entries with exchange timestamps
            await memory_manager.add_diary_entry(
                user_id=user_id,
                entry_type="compact_summary",
                title="Conversation Summary",
                content=summary_content,
                importance=5,
                exchange_start=first_conv.timestamp,
                exchange_end=last_conv.timestamp,
            )
            
            return True
        
        return False
        
    except Exception as e:
        logger.error("Failed to create compact", error=str(e))
        return False


async def backfill_compacts_for_user(user_id: int, batch_size: int = 10):
    """Create compact summaries for messages since last compact.
    
    Args:
        user_id: User ID to backfill compacts for
        batch_size: Number of messages per compact (default: 10)
    """
    print(f"\n{'='*60}")
    print(f"Backfilling compacts for user {user_id}")
    print(f"{'='*60}\n")
    
    # Get last compact timestamp
    diary_entries = await memory_manager.get_diary_entries(user_id, limit=10)
    last_compact = None
    for entry in diary_entries:
        if entry.entry_type == 'compact_summary':
            last_compact = entry.timestamp
            break
    
    if not last_compact:
        print("❌ No previous compact summaries found. Cannot backfill.")
        return
    
    print(f"📅 Last compact: {last_compact}")
    
    # Get all conversations since last compact
    all_convos = await memory_manager.db.get_recent_conversations(user_id, limit=200)
    
    # Filter to messages after last compact
    messages_to_compact = []
    for conv in reversed(all_convos):  # Reverse to get chronological order
        if conv.timestamp and conv.timestamp > last_compact:
            messages_to_compact.append(conv)
    
    total_messages = len(messages_to_compact)
    print(f"📊 Found {total_messages} messages since last compact")
    
    if total_messages < batch_size:
        print(f"⚠️  Not enough messages for a full batch (need {batch_size}, have {total_messages})")
        print("   Will wait for more messages before creating compact.")
        return
    
    # Calculate how many compacts to create
    num_compacts = total_messages // batch_size
    print(f"📦 Will create {num_compacts} compact summaries ({batch_size} messages each)")
    
    # Get user context for profile info
    context = await memory_manager.get_user_context(user_id)
    user_name = context.user_info.name or "User"
    
    # Build profile context
    parts = []
    if context.user_info.name:
        parts.append(f"Their name is {context.user_info.name}.")
    
    if context.profile:
        if "static" in context.profile:
            for value in context.profile["static"].values():
                parts.append(f"- {value}")
        
        if "condensed" in context.profile:
            parts.append("")
            parts.append("YOUR UNDERSTANDING OF THEM:")
            for category, narrative in context.profile["condensed"].items():
                parts.append(f"[{category}] {narrative}")
    
    profile_context = "\n".join(parts) if parts else "(You're just getting to know them.)"
    
    # Create compacts in batches
    success_count = 0
    for i in range(num_compacts):
        start_idx = i * batch_size
        end_idx = start_idx + batch_size
        batch = messages_to_compact[start_idx:end_idx]
        
        print(f"\n📝 Creating compact {i+1}/{num_compacts}...")
        print(f"   Messages {start_idx+1}-{end_idx} of {total_messages}")
        print(f"   Time range: {batch[0].timestamp} to {batch[-1].timestamp}")
        
        # Create compact for this batch
        success = await create_compact_for_batch(
            user_id=user_id,
            batch=batch,
            user_name=user_name,
            profile_context=profile_context,
        )
        
        if success:
            print(f"   ✅ Compact {i+1} created successfully")
            success_count += 1
        else:
            print(f"   ❌ Failed to create compact {i+1}")
    
    remaining = total_messages % batch_size
    if remaining > 0:
        print(f"\n📌 {remaining} messages remaining (will be included in next compact)")
    
    print(f"\n{'='*60}")
    print(f"✅ Backfill complete! Created {success_count}/{num_compacts} compact summaries")
    print(f"{'='*60}\n")


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/backfill_compacts.py <user_id>")
        print("\nExample: python scripts/backfill_compacts.py 1")
        sys.exit(1)
    
    try:
        user_id = int(sys.argv[1])
    except ValueError:
        print("❌ Error: user_id must be an integer")
        sys.exit(1)
    
    await backfill_compacts_for_user(user_id)


if __name__ == "__main__":
    asyncio.run(main())

# Made with Bob
