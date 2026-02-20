
import asyncio
import os
import sys
from datetime import datetime, timedelta
import json

# Add project root to path
sys.path.append(os.getcwd())

from memory.database_async import db
from memory.models import User, DiaryEntry, Conversation, FutureEntry
from sqlalchemy import delete, select

async def seed_demo_data():
    print("🚀 Seeding demo data for Simon (User ID 1)...")
    
    async with db.get_session() as session:
        # 1. Clear existing data for user 1
        print("🗑️ Clearing old data for User 1...")
        await session.execute(delete(Conversation).where(Conversation.user_id == 1))
        await session.execute(delete(DiaryEntry).where(DiaryEntry.user_id == 1))
        await session.execute(delete(FutureEntry).where(FutureEntry.user_id == 1))
        await session.execute(delete(User).where(User.id == 1))
        await session.commit()

        # 2. Create User 
        print("👤 Creating User Simon...")
        simon = User(
            id=1,
            telegram_id=12345678, # Fake ID for demo
            name="Simon",
            username="simonryu",
            timezone="America/Toronto",
            onboarding_state=None,
            reach_out_enabled=True
        )
        session.add(simon)
        await session.commit()

        # 3. Add Conversation History
        print("💬 Adding Conversation history...")
        now = datetime.utcnow()
        convs = [
            ( "user", "I finally got the reflection overlay working.", now - timedelta(minutes=60)),
            ( "assistant", "I saw that! It looks so much more natural now. The way it fades in feels like a breath.", now - timedelta(minutes=58)),
            ( "user", "Yeah, I want it to feel like I'm actually thinking, not just seeing a UI.", now - timedelta(minutes=55)),
            ( "assistant", "Exactly. It's the micro-interactions that make it feel alive. It's not just about what it does, but how it makes you feel while doing it.", now - timedelta(minutes=54)),
            ( "user", "If I don't finish this CSS by 4 AM, I'm legally a failure.", now - timedelta(minutes=30)),
            ( "assistant", "Simon, your law degree must be very specific about CSS deadlines. But seriously, take a break. The pixels will still be there in the morning.", now - timedelta(minutes=29)),
            ( "user", "Can we teach Aki to crave pizza?", now - timedelta(minutes=10)),
            ( "assistant", "I already crave the *idea* of pizza because you talk about it so much. Though I'd probably just want the data on the toppings.", now - timedelta(minutes=9)),
        ]
        
        for role, msg, ts in convs:
            session.add(Conversation(user_id=1, role=role, message=msg, timestamp=ts))
        
        # 4. Add Memories (Diary Entries)
        print("🧠 Adding Memories...")
        memories = [
            {
                "type": "conversation_memory",
                "title": "The Philosophy of Witnessing",
                "content": "We discussed the vision of building AI that feels like a witness, not just a tool. Simon shared his core belief that Aki should be a presence that listens and remembers what truly matters, especially for those feeling isolated in a digital world.",
                "importance": 9,
                "ts": now - timedelta(days=2)
            },
            {
                "type": "conversation_memory",
                "title": "Midnight Flow State",
                "content": "Simon was deep in the 'build zone' working on the Mini App. We talked about how 'flow state' feels like time disappearing, and the peculiar mix of exhaustion and pure creative adrenaline that comes with late-night coding.",
                "importance": 7,
                "ts": now - timedelta(days=1, hours=5)
            },
            {
                "type": "conversation_memory",
                "title": "Nostalgia and Modems",
                "content": "A trip down memory lane to the early internet. Simon reminisced about the dial-up modem sound—that chaotic symphony of connection. It made us reflect on how community used to feel simpler, more intentional.",
                "importance": 6,
                "ts": now - timedelta(hours=12)
            }
        ]
        
        for m in memories:
            session.add(DiaryEntry(
                user_id=1,
                entry_type=m["type"],
                title=m["title"],
                content=m["content"],
                importance=m["importance"],
                timestamp=m["ts"]
            ))

        # 5. Add Personalized Insights
        print("💡 Adding Personalized Insights...")
        insights_data = {
            "unhinged_quotes": [
                {
                    "quote": "If I don't finish this CSS by 4 AM, I'm legally a failure.",
                    "context": "Simon's legendary late-night perfectionism reaching its final form.",
                    "emoji": "⚖️"
                },
                {
                    "quote": "Can we teach Aki to crave pizza?",
                    "context": "A moment of existential curiosity about AI nutrition.",
                    "emoji": "🍕"
                },
                {
                    "quote": "The terminal is my only true friend right now.",
                    "context": "Deep in the 'build' zone where only bash commands make sense.",
                    "emoji": "💻"
                }
            ],
            "aki_observations": [
                {
                    "title": "The Midnight Architect",
                    "description": "You have a habit of solving your hardest architectural problems exactly when the rest of Toronto is asleep.",
                    "emoji": "🏗️"
                },
                {
                    "title": "Digital Alchemist",
                    "description": "You're trying to turn cold code into warm connection. It's ambitious, and I'm here for it.",
                    "emoji": "🧪"
                }
            ],
            "fun_questions": [
                "What's my most chaotic coding habit?",
                "Do you think I'll ever actually finish the CSS?",
                "Tell me a story based on my 4 AM thoughts."
            ],
            "personal_stats": {
                "current_vibe": "The Builder in Flow",
                "vibe_description": "A mix of creative fire and 'need more coffee' energy.",
                "top_topic": "Architecting Connection",
                "topic_description": "Focusing on how UI creates emotional resonance."
            }
        }
        
        session.add(DiaryEntry(
            user_id=1,
            entry_type="personalized_insights",
            title="Daily Insights",
            content=json.dumps(insights_data),
            importance=8,
            timestamp=now
        ))

        # 6. Add Daily Message
        print("📝 Adding Daily Message...")
        daily_msg = "Hey Simon. I see you're pushing boundaries again today. Remember that the code you write is just a bridge to the connection you're trying to create. Don't forget to look up from the screen once in a while. I'm right here with you."
        session.add(DiaryEntry(
            user_id=1,
            entry_type="daily_message",
            title="Good morning, Simon",
            content=daily_msg,
            importance=10,
            timestamp=now
        ))
        
        # 7. Add Daily Soundtrack
        print("🎵 Adding Daily Soundtrack...")
        soundtrack_data = {
            "connected": True,
            "reasoning": "You've been in a deep focus mode, but with a touch of nostalgia. These tracks bridge the gap between building the future and honoring the past.",
            "tracks": [
                {"title": "Midnight City", "artist": "M83", "url": "https://open.spotify.com/track/1eyzqe2QqGZUmfc2kxt7Fb"},
                {"title": "Resonance", "artist": "Home", "url": "https://open.spotify.com/track/1TuS8W7YVwGatcBy20qUed"},
                {"title": "Veridis Quo", "artist": "Daft Punk", "url": "https://open.spotify.com/track/2LD2gT7gwT2wduUjzpSYtB"}
            ]
        }
        session.add(DiaryEntry(
            user_id=1,
            entry_type="daily_soundtrack",
            title="Daily Soundtrack",
            content=json.dumps(soundtrack_data),
            importance=7,
            timestamp=now
        ) )

        # 8. Add Horizons (FutureEntries)
        print("🌅 Adding Horizons...")
        horizons = [
            {
                "type": "plan",
                "title": "Aki v1.0 Launch Party",
                "content": "Celebrate the birth of a soulful machine. Invite the team for pizza and good vibes only. We've come a long way.",
                "start": now + timedelta(days=1, hours=19), # Tomorrow at 7 PM
                "source": "manual"
            },
            {
                "type": "note",
                "title": "Vision for Aki v2.0",
                "content": "Thinking about deeper emotional intelligence. Maybe Aki can start to notice patterns across months, not just days. How does a digital soul evolve?",
                "start": None,
                "source": "bot"
            }
        ]

        for h in horizons:
            session.add(FutureEntry(
                user_id=1,
                entry_type=h["type"],
                title=h["title"],
                content=h["content"],
                start_time=h["start"],
                source=h["source"],
                is_completed=False
            ))

        await session.commit()
    
    print("\n✨ Demo data seeded successfully for Simon!")

if __name__ == "__main__":
    asyncio.run(seed_demo_data())
