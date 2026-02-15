
import asyncio
import os
import sys
import json

# Add project root to path
sys.path.append(os.getcwd())

from memory.memory_manager_async import memory_manager
from config.settings import settings
from agents.soul_agent import soul_agent

async def check_user_trigger(telegram_id):
    results = {}
    
    # 1. Resolve user
    user = await memory_manager.db.get_user_by_telegram_id(telegram_id)
    if not user:
        user = await memory_manager.get_user_by_id(telegram_id)
        if not user:
            results["error"] = f"User {telegram_id} not found"
            return results

    user_id = user.id
    results["user"] = {"id": user_id, "name": user.name, "telegram_id": user.telegram_id}

    # 2. Get last compact timestamp
    diary_entries = await memory_manager.get_diary_entries(user_id, limit=50)
    last_compact = None
    for entry in diary_entries:
        if entry.entry_type == 'compact_summary':
            last_compact = entry.timestamp
            break
    
    results["last_compact"] = str(last_compact) if last_compact else None

    # 3. Count messages since then
    all_convos = await memory_manager.db.get_recent_conversations(user_id, limit=100)
    
    message_count = 0
    if last_compact:
        for conv in all_convos:
            if conv.timestamp and conv.timestamp.replace(tzinfo=None) > last_compact.replace(tzinfo=None):
                message_count += 1
    else:
        message_count = len(all_convos)

    # 4. Results
    threshold = settings.COMPACT_INTERVAL
    results["message_count"] = message_count
    results["threshold"] = threshold
    results["remaining"] = threshold - message_count if message_count < threshold else 0
    results["trigger_ready"] = message_count >= threshold
    
    return results

async def main():
    tid = 1
    if len(sys.argv) > 1:
        try:
            tid = int(sys.argv[1])
        except:
            pass
            
    results = await check_user_trigger(tid)
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
