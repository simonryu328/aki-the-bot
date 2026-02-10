#!/usr/bin/env python3
"""
Backfill missing compact summaries for users who have accumulated messages
without compacts being created (due to the bug).

This script will create compact summaries in batches of COMPACT_INTERVAL messages.

Usage:
    uv run python scripts/backfill_missing_compacts.py [--user-id USER_ID] [--dry-run]
"""

import asyncio
import sys
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.soul_agent import soul_agent
from memory.memory_manager_async import memory_manager
from config.settings import settings


async def backfill_user_compacts(user_id: int, dry_run: bool = False):
    """Backfill missing compact summaries for a user."""
    print(f"\n{'='*60}")
    print(f"  BACKFILLING COMPACTS FOR USER {user_id}")
    print(f"{'='*60}\n")
    
    # Get latest compact
    diary_entries = await memory_manager.get_diary_entries(user_id, limit=settings.DIARY_FETCH_LIMIT)
    last_compact = None
    for entry in diary_entries:
        if entry.entry_type == 'compact_summary':
            last_compact = entry
            break
    
    if not last_compact or not last_compact.exchange_end:
        print("No previous compact found or no exchange_end timestamp. Cannot backfill.")
        return
    
    print(f"Last compact end: {last_compact.exchange_end}")
    
    # Get all messages after last compact
    all_convos = await memory_manager.db.get_conversations_after(
        user_id=user_id,
        after=last_compact.exchange_end,
        limit=1000  # Get all messages
    )
    
    message_count = len(all_convos)
    print(f"Messages after last compact: {message_count}")
    
    if message_count < settings.COMPACT_INTERVAL:
        print(f"Not enough messages for a compact (need {settings.COMPACT_INTERVAL})")
        return
    
    # Calculate how many compacts we should create
    num_compacts = message_count // settings.COMPACT_INTERVAL
    print(f"Will create {num_compacts} compact summaries")
    
    if dry_run:
        print("\n[DRY RUN] Would create the following compacts:")
        for i in range(num_compacts):
            start_idx = i * settings.COMPACT_INTERVAL
            end_idx = (i + 1) * settings.COMPACT_INTERVAL
            batch = all_convos[start_idx:end_idx]
            print(f"  Compact {i+1}: {batch[0].timestamp} to {batch[-1].timestamp}")
        return
    
    # Create compacts in batches
    print("\nCreating compacts...")
    for i in range(num_compacts):
        start_idx = i * settings.COMPACT_INTERVAL
        end_idx = (i + 1) * settings.COMPACT_INTERVAL
        batch = all_convos[start_idx:end_idx]
        
        print(f"\nCompact {i+1}/{num_compacts}:")
        print(f"  Messages: {start_idx+1}-{end_idx}")
        print(f"  Timeframe: {batch[0].timestamp} to {batch[-1].timestamp}")
        
        try:
            # Create compact for this batch
            await soul_agent._create_compact_summary(user_id=user_id)
            print(f"  ✅ Created successfully")
        except Exception as e:
            print(f"  ❌ Failed: {e}")
            import traceback
            traceback.print_exc()
    
    # Check remaining messages
    remaining = message_count % settings.COMPACT_INTERVAL
    print(f"\n{remaining} messages remaining (will be compacted on next trigger)")
    
    print(f"\n{'='*60}")
    print(f"  BACKFILL COMPLETE")
    print(f"{'='*60}\n")


async def backfill_all_users(dry_run: bool = False):
    """Backfill compacts for all users who need it."""
    all_users = await memory_manager.get_all_users()
    
    print(f"\nChecking {len(all_users)} users for backfill needs...\n")
    
    users_needing_backfill = []
    
    for user in all_users:
        # Get latest compact
        diary_entries = await memory_manager.get_diary_entries(user.id, limit=settings.DIARY_FETCH_LIMIT)
        last_compact = None
        for entry in diary_entries:
            if entry.entry_type == 'compact_summary':
                last_compact = entry
                break
        
        if last_compact and last_compact.exchange_end:
            # Count messages after
            convos = await memory_manager.db.get_conversations_after(
                user_id=user.id,
                after=last_compact.exchange_end,
                limit=1000
            )
            
            if len(convos) >= settings.COMPACT_INTERVAL:
                users_needing_backfill.append((user, len(convos)))
                print(f"User {user.id} ({user.name}): {len(convos)} messages need compacting")
    
    if not users_needing_backfill:
        print("No users need backfilling!")
        return
    
    print(f"\n{len(users_needing_backfill)} users need backfilling")
    
    if not dry_run:
        confirm = input("\nProceed with backfill? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Cancelled.")
            return
    
    for user, msg_count in users_needing_backfill:
        await backfill_user_compacts(user.id, dry_run=dry_run)


def main():
    parser = argparse.ArgumentParser(description="Backfill missing compact summaries")
    parser.add_argument("--user-id", type=int, help="Specific user ID to backfill")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without doing it")
    
    args = parser.parse_args()
    
    if args.user_id:
        asyncio.run(backfill_user_compacts(args.user_id, args.dry_run))
    else:
        asyncio.run(backfill_all_users(args.dry_run))


if __name__ == "__main__":
    main()

# Made with Bob
