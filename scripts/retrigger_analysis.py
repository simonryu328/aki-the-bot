
import asyncio
import os
import sys
from datetime import datetime
import json

# Add project root to path
sys.path.append(os.getcwd())

from agents.soul_agent import soul_agent
from memory.memory_manager_async import memory_manager
from memory.database_async import db
from memory.models import DiaryEntry
from sqlalchemy import delete
from core import get_logger

logger = get_logger(__name__)

async def retrigger_all_calls():
    print("🚀 Retriggering all LLM calls with Claude 3.5 Haiku...")
    
    users = await memory_manager.get_all_users()
    print(f"Found {len(users)} users.")
    
    for user in users:
        print(f"\n──────────────────────────────────────────────────")
        print(f"👤 Processing User: {user.name} (ID: {user.id})")
        
        # 1. Clear today's insights, daily messages, and soundtracks to force regeneration
        async with db.get_session() as session:
            now = datetime.utcnow()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
            stmt = delete(DiaryEntry).where(
                DiaryEntry.user_id == user.id,
                DiaryEntry.entry_type.in_(["daily_message", "daily_soundtrack", "personalized_insights"]),
                DiaryEntry.timestamp >= today_start
            )
            result = await session.execute(stmt)
            print(f"🗑️ Cleared {result.rowcount} today's entries for regeneration.")
            await session.commit()

        # 2. Retrigger Daily Message
        try:
            print("📝 Generating Daily Message...")
            content, is_fallback = await soul_agent.generate_daily_message(user.id)
            print(f"✅ Daily Message: {content[:100]}...")
        except Exception as e:
            print(f"❌ Daily Message Failed: {e}")

        # 3. Retrigger Soundtrack (if Spotify connected)
        if user.spotify_refresh_token:
            try:
                print("🎵 Generating Daily Soundtrack...")
                data = await soul_agent.generate_daily_soundtrack(user.id)
                if data.get("connected"):
                    await memory_manager.add_diary_entry(
                        user_id=user.id,
                        entry_type="daily_soundtrack",
                        title="Daily Soundtrack",
                        content=json.dumps(data),
                        importance=7
                    )
                    print(f"✅ Soundtrack generated.")
            except Exception as e:
                print(f"❌ Soundtrack Failed: {e}")
        else:
            print("⏭️ Skipping Soundtrack (Spotify not connected).")

        # 4. Retrigger Personalized Insights
        try:
            print("💡 Generating Personalized Insights...")
            await soul_agent.generate_personalized_insights(user.id, store=True)
            print(f"✅ Insights generated.")
        except Exception as e:
            print(f"❌ Insights Failed: {e}")

        # 5. Retrigger Memory / Summary (Threshold based)
        try:
            print("🧠 Checking Conversation Memory threshold...")
            await soul_agent._maybe_create_compact_summary(user.id)
            print(f"✅ Memory check complete.")
        except Exception as e:
            print(f"❌ Memory check Failed: {e}")

    print("\n✨ All LLM calls retriggered.")

if __name__ == "__main__":
    asyncio.run(retrigger_all_calls())
