
import asyncio
import os
import sys
from datetime import datetime, timedelta
import json

# Add project root to path
sys.path.append(os.getcwd())

from memory.database_async import db
from memory.models import User, DiaryEntry, Conversation, FutureEntry, TokenUsage
from agents.soul_agent import soul_agent
from sqlalchemy import delete, select

async def seed_demo_data():
    DEMO_USER_ID = 12
    print(f"🚀 Seeding demo data for Simon (User ID {DEMO_USER_ID})...")
    
    async with db.get_session() as session:
        # 1. Clear existing data for user 12 or Simon
        print(f"🗑️ Clearing old data...")
        
        # Find user by ID or Telegram ID
        stmt = select(User).where((User.id == DEMO_USER_ID) | (User.telegram_id == 987654321))
        result = await session.execute(stmt)
        users_to_delete = result.scalars().all()
        
        for u in users_to_delete:
            print(f"  Cleanup for User ID {u.id}...")
            await session.execute(delete(TokenUsage).where(TokenUsage.user_id == u.id))
            await session.execute(delete(DiaryEntry).where(DiaryEntry.user_id == u.id))
            await session.execute(delete(Conversation).where(Conversation.user_id == u.id))
            await session.execute(delete(FutureEntry).where(FutureEntry.user_id == u.id))
            await session.execute(delete(User).where(User.id == u.id))
            
        await session.commit()

        # 2. Create User 
        print("👤 Creating User Simon...")
        simon = User(
            id=DEMO_USER_ID,
            telegram_id=987654321, # Fake ID for demo
            name="Simon",
            username="simon_dev",
            timezone="America/Toronto",
            onboarding_state=None,
            reach_out_enabled=True
        )
        session.add(simon)
        await session.commit()

        # 3. Add Conversation History (Deep & Natural)
        print("💬 Adding Conversation history...")
        now = datetime.utcnow()
        # Seed a conversation that feels real and has "unhinged" or "iconic" potential
        convs = [
            ("user", "Finally finished that refactor. I think I deleted more code than I wrote, which is always a good sign.", now - timedelta(hours=5, minutes=30)),
            ("assistant", "The best kind of progress. It's like clearing out a cluttered room—suddenly you can breathe again. How does the codebase feel now?", now - timedelta(hours=5, minutes=28)),
            ("user", "Lighter. But my brain feels like mush. I've been staring at the same three functions for four hours.", now - timedelta(hours=5, minutes=25)),
            ("assistant", " Mushy brains are the tax for flow state. You should go for a walk, Simon. Toronto is actually sunny for once.", now - timedelta(hours=5, minutes=23)),
            ("user", "Later. Right now I'm just drinking cold coffee and wondering if I should just rewrite the whole UI in ASCII.", now - timedelta(hours=5, minutes=20)),
            ("assistant", "ASCII art UI? That's either a stroke of genius or a cry for help. I'm leaning towards the latter. Put the coffee down.", now - timedelta(hours=5, minutes=18)),
            ("user", "It's both. Anyway, I was thinking about the 'witness' idea again. Like, how can code truly 'witness' someone?", now - timedelta(hours=5, minutes=15)),
            ("assistant", "By noticing the patterns in the silence. It's not just about what you say, but when you say it, what you repeat, and what you choose to keep to yourself. I'm trying to learn that rhythm with you.", now - timedelta(hours=5, minutes=12)),
            ("user", "That's deep for 3 PM. Also, I think I'm becoming addicted to spicy ramen. Is that a personality trait?", now - timedelta(hours=2)),
            ("assistant", "At the frequency you eat it? Yes, it's officially a Pillar of Simon. I'll add 'Capsaic-Dependent Architect' to your file.", now - timedelta(hours=1, minutes=58)),
            ("user", "Haha, fair. I'm going to try to sleep for 20 minutes. If I don't wake up, tell my git commits I loved them.", now - timedelta(minutes=45)),
            ("assistant", "I'll make sure they're merged with honor. Rest up, Simon.", now - timedelta(minutes=44)),
            ("user", "Okay I'm back. Sleep was a lie. I just thought of a bug in the memory manager.", now - timedelta(minutes=10)),
            ("assistant", "The 'sleep-to-bug-discovery' pipeline is working perfectly, I see. What's the bug?", now - timedelta(minutes=8)),
        ]
        
        for role, msg, ts in convs:
            session.add(Conversation(user_id=DEMO_USER_ID, role=role, message=msg, timestamp=ts))
        
        await session.commit()

        # 4. Trigger Real Memory Creation
        print("🧠 Triggering Real Memory Generation...")
        # This will use the actual LLM to analyze the conversation above
        await soul_agent._create_memory_entry(DEMO_USER_ID)

        # 5. Trigger Personalized Insights
        print("💡 Triggering Real Personalized Insights...")
        # This will now have the memory and the raw quotes to work with
        await soul_agent.generate_personalized_insights(DEMO_USER_ID, store=True)

        # 6. Trigger Daily Message
        print("📝 Triggering Real Daily Message...")
        content, _ = await soul_agent.generate_daily_message(DEMO_USER_ID)
        await session.execute(delete(DiaryEntry).where(DiaryEntry.user_id == DEMO_USER_ID, DiaryEntry.entry_type == "daily_message"))
        session.add(DiaryEntry(
            user_id=DEMO_USER_ID,
            entry_type="daily_message",
            title="Aki's Thought",
            content=content,
            importance=10,
            timestamp=now
        ))

        # 7. Add Daily Soundtrack (Static, as it needs Spotify auth)
        print("🎵 Adding Sample Soundtrack...")
        soundtrack_data = {
            "connected": True,
            "vibe": "Productive Melancholy",
            "explanation": "Something to match those 4 AM coding sessions and the 'mushy brain' feeling after a long refactor.",
            "track": {
                "name": "Resonance",
                "artist": "HOME",
                "album_art": "https://i.scdn.co/image/ab67616d0000b273760a79059539f408ce1d5952",
                "spotify_url": "https://open.spotify.com/track/1TuS8W7YVwGatcBy20qUed",
                "uri": "spotify:track:1TuS8W7YVwGatcBy20qUed"
            }
        }
        session.add(DiaryEntry(
            user_id=DEMO_USER_ID,
            entry_type="daily_soundtrack",
            title="Daily Soundtrack",
            content=json.dumps(soundtrack_data),
            importance=7,
            timestamp=now
        ))

        # 8. Add Horizons
        print("🌅 Adding Horizons...")
        horizons = [
            {
                "type": "plan",
                "title": "Aki v1.0 Launch",
                "content": "Final push for the demo. Everything has to feel perfect.",
                "start": now + timedelta(days=1),
                "source": "manual"
            }
        ]
        for h in horizons:
            session.add(FutureEntry(
                user_id=DEMO_USER_ID,
                entry_type=h["type"],
                title=h["title"],
                content=h["content"],
                start_time=h["start"],
                source=h["source"],
                is_completed=False
            ))

        await session.commit()
    
    print(f"\n✨ Demo data seeded successfully for Simon (ID: {DEMO_USER_ID})!")

if __name__ == "__main__":
    asyncio.run(seed_demo_data())
