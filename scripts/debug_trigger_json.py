
import asyncio
import os
import sys
import json
from datetime import datetime

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
    all_summaries = []
    for entry in diary_entries:
        if entry.entry_type == 'compact_summary':
            all_summaries.append(entry)
            if not last_compact:
                last_compact = entry.timestamp
    
    results["last_compact_ts"] = str(last_compact) if last_compact else None

    # 3. Count messages since then
    all_convos = await memory_manager.db.get_recent_conversations(user_id, limit=100)
    
    message_count = 0
    if last_compact:
        for conv in all_convos:
            if conv.timestamp and conv.timestamp.replace(tzinfo=None) > last_compact.replace(tzinfo=None):
                message_count += 1
    else:
        message_count = len(all_convos)

    # 4. Check Context Optimization (The new feature)
    # Replicate the logic from soul_agent._build_conversation_context
    effective_history_len = 0
    if all_summaries:
        latest = all_summaries[0]
        end_ts = (latest.exchange_end or latest.timestamp).replace(tzinfo=None)
        
        after = [c for c in all_convos if (c.timestamp or datetime.utcnow()).replace(tzinfo=None) > end_ts]
        overlap = [c for c in all_convos if (c.timestamp or datetime.utcnow()).replace(tzinfo=None) <= end_ts][-3:]
        effective_history_len = len(after) + len(overlap)
    else:
        effective_history_len = min(len(all_convos), settings.CONVERSATION_CONTEXT_LIMIT)

    # 5. Results
    threshold = settings.COMPACT_INTERVAL
    results["backlog_count"] = message_count
    results["threshold"] = threshold
    results["trigger_ready"] = message_count >= threshold
    results["optimization"] = {
        "original_limit": settings.CONVERSATION_CONTEXT_LIMIT,
        "optimized_history_length": effective_history_len,
        "tokens_saved_estimate_pct": round((1 - (effective_history_len / settings.CONVERSATION_CONTEXT_LIMIT)) * 100, 1) if effective_history_len < settings.CONVERSATION_CONTEXT_LIMIT else 0
    }
    
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
