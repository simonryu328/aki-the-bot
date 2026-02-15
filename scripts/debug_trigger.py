
import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from memory.memory_manager_async import memory_manager
from config.settings import settings
from agents.soul_agent import soul_agent

async def check_user_trigger(telegram_id):
    print(f"Checking trigger status for user with Telegram ID: {telegram_id}")
    
    # 1. Resolve user
    user = await memory_manager.db.get_user_by_telegram_id(telegram_id)
    if not user:
        # Try internal ID if telegram ID lookup fails
        user = await memory_manager.get_user_by_id(telegram_id)
        if not user:
            print(f"Error: User {telegram_id} not found in database.")
            return

    user_id = user.id
    print(f"Resolved to internal user_id: {user_id} (Name: {user.name})")

    # 2. Get last compact timestamp
    diary_entries = await memory_manager.get_diary_entries(user_id, limit=50)
    last_compact = None
    for entry in diary_entries:
        if entry.entry_type == 'compact_summary':
            last_compact = entry.timestamp
            print(f"Found last compact summary at: {last_compact}")
            break
    
    if not last_compact:
        print("No previous compact summary found for this user.")

    # 3. Count messages since then
    all_convos = await memory_manager.db.get_recent_conversations(user_id, limit=100)
    
    message_count = 0
    if last_compact:
        for conv in all_convos:
            if conv.timestamp and conv.timestamp > last_compact:
                message_count += 1
    else:
        message_count = len(all_convos)

    # 4. Report
    threshold = settings.COMPACT_INTERVAL
    print(f"\n--- TRIGGER STATUS ---")
    print(f"Messages since last memory/compact: {message_count}")
    print(f"Trigger threshold: {threshold}")
    
    if message_count >= threshold:
        print("STATUS: TRIGGER READY. The next message will trigger memory generation.")
    else:
        remaining = threshold - message_count
        print(f"STATUS: TRACKING. {remaining} more messages needed to trigger.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        tid = int(sys.argv[1])
    else:
        tid = 1 # Default to 1
    asyncio.run(check_user_trigger(tid))
