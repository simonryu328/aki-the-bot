"""
Test script for the surface prompt.
Allows testing with different combinations of summaries and memories.
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Any, cast

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.database_async import db
from sqlalchemy import select, and_, or_
from memory.models import DiaryEntry, User
from config.settings import settings
from utils.llm_client import LLMClient
from prompts.surface import SURFACE_PROMPT


async def get_users_with_data() -> List[tuple]:
    """Get all users who have summaries or memories."""
    async with db.get_session() as session:
        result = await session.execute(
            select(User.telegram_id, User.name)
            .join(DiaryEntry, User.id == DiaryEntry.user_id)
            .where(
                or_(
                    DiaryEntry.entry_type == 'compact_summary',
                    DiaryEntry.entry_type == 'conversation_memory'
                )
            )
            .distinct()
        )
        return result.all()


async def get_user_summaries(user_id: int, limit: int = 5) -> List[DiaryEntry]:
    """Get recent compact summaries for a user."""
    async with db.get_session() as session:
        result = await session.execute(
            select(DiaryEntry)
            .where(
                and_(
                    DiaryEntry.user_id == user_id,
                    DiaryEntry.entry_type == 'compact_summary'
                )
            )
            .order_by(DiaryEntry.timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


async def get_user_memories(user_id: int, limit: int = 5) -> List[DiaryEntry]:
    """Get recent conversation memories for a user."""
    async with db.get_session() as session:
        result = await session.execute(
            select(DiaryEntry)
            .where(
                and_(
                    DiaryEntry.user_id == user_id,
                    DiaryEntry.entry_type == 'conversation_memory'
                )
            )
            .order_by(DiaryEntry.timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


def format_summaries(summaries: List[DiaryEntry]) -> str:
    """Format summaries for the prompt."""
    if not summaries:
        return ""
    
    lines = ["CONVERSATION SUMMARIES:"]
    for i, summary in enumerate(summaries, 1):
        time_info = ""
        if summary.exchange_start is not None and summary.exchange_end is not None:
            start = summary.exchange_start.strftime("%Y-%m-%d %H:%M")
            end = summary.exchange_end.strftime("%H:%M")
            time_info = f" ({start} → {end})"
        
        title = cast(str, summary.title)
        content = cast(str, summary.content)
        lines.append(f"\n{i}. {title}{time_info}")
        lines.append(content)
    
    return "\n".join(lines)


def format_memories(memories: List[DiaryEntry]) -> str:
    """Format conversation memories for the prompt."""
    if not memories:
        return ""
    
    lines = ["CONVERSATION MEMORIES:"]
    for i, memory in enumerate(memories, 1):
        timestamp = memory.timestamp.strftime("%Y-%m-%d %H:%M")
        title = cast(str, memory.title)
        content = cast(str, memory.content)
        lines.append(f"\n{i}. [{timestamp}] {title}")
        lines.append(content)
    
    return "\n".join(lines)


async def main():
    """Main test function."""
    
    print("=" * 80)
    print("SURFACE PROMPT TEST")
    print("=" * 80)
    
    # Step 1: Get all users with data
    print("\n📊 Fetching users with summaries or memories...")
    users = await get_users_with_data()
    
    if not users:
        print("❌ No users with data found!")
        return
    
    print(f"✅ Found {len(users)} user(s):")
    for i, (telegram_id, name) in enumerate(users, 1):
        print(f"   {i}. {name} (ID: {telegram_id})")
    
    # Step 2: Let user choose
    if len(users) == 1:
        chosen_telegram_id, chosen_name = users[0]
        print(f"\n→ Only one user, selecting: {chosen_name}")
    else:
        choice = input(f"\nChoose user (1-{len(users)}): ").strip()
        try:
            idx = int(choice) - 1
            chosen_telegram_id, chosen_name = users[idx]
        except (ValueError, IndexError):
            print("❌ Invalid choice!")
            return
    
    # Step 3: Get user from database
    async with db.get_session() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == chosen_telegram_id)
        )
        user = user_result.scalar_one()
    
    # Step 4: Get available data
    user_id = cast(int, user.id)
    summaries = await get_user_summaries(user_id, limit=10)
    memories = await get_user_memories(user_id, limit=10)
    
    print(f"\n📚 Available data for {chosen_name}:")
    print(f"   - {len(summaries)} compact summaries")
    print(f"   - {len(memories)} conversation memories")
    
    if not summaries and not memories:
        print("\n❌ No data available for this user!")
        return
    
    # Step 5: Choose data combination
    print("\n" + "=" * 80)
    print("CHOOSE DATA TO INCLUDE")
    print("=" * 80)
    print("\nOptions:")
    print("1. Only summaries (most recent 5)")
    print("2. Only memories (most recent 5)")
    print("3. Both summaries and memories (5 each)")
    print("4. Custom: Choose specific counts")
    
    option = input("\nChoose option (1-4): ").strip()
    
    selected_summaries = []
    selected_memories = []
    
    if option == "1":
        selected_summaries = summaries[:5]
    elif option == "2":
        selected_memories = memories[:5]
    elif option == "3":
        selected_summaries = summaries[:5]
        selected_memories = memories[:5]
    elif option == "4":
        if summaries:
            try:
                num_summaries = int(input(f"Number of summaries (0-{len(summaries)}): ").strip())
                selected_summaries = summaries[:num_summaries]
            except ValueError:
                print("Invalid number, using 0")
        
        if memories:
            try:
                num_memories = int(input(f"Number of memories (0-{len(memories)}): ").strip())
                selected_memories = memories[:num_memories]
            except ValueError:
                print("Invalid number, using 0")
    else:
        print("❌ Invalid option!")
        return
    
    if not selected_summaries and not selected_memories:
        print("\n❌ No data selected!")
        return
    
    # Step 6: Format the data
    print("\n" + "=" * 80)
    print("PREPARING PROMPT")
    print("=" * 80)
    
    parts = []
    if selected_summaries:
        parts.append(format_summaries(selected_summaries))
    if selected_memories:
        parts.append(format_memories(selected_memories))
    
    summaries_and_memories = "\n\n".join(parts)
    
    print(f"\n📝 Using:")
    print(f"   - {len(selected_summaries)} summaries")
    print(f"   - {len(selected_memories)} memories")
    print(f"   - Total characters: {len(summaries_and_memories)}")
    
    # Step 7: Show the formatted data
    print("\n" + "=" * 80)
    print("FORMATTED DATA")
    print("=" * 80)
    print(summaries_and_memories)
    
    # Step 8: Choose model
    print("\n" + "=" * 80)
    print("CHOOSE MODEL")
    print("=" * 80)
    print("\nOptions:")
    print("1. Claude (default: claude-sonnet-4-5-20250929)")
    print("2. OpenAI GPT-4o")
    print("3. OpenAI o1")
    
    model_choice = input("\nChoose model (1-3, default=1): ").strip() or "1"
    
    if model_choice == "1":
        model = settings.MODEL_CONVERSATION
        model_name = "Claude Sonnet"
    elif model_choice == "2":
        model = "gpt-4o"
        model_name = "GPT-4o"
    elif model_choice == "3":
        model = "o1"
        model_name = "OpenAI o1"
    else:
        print("Invalid choice, using Claude")
        model = settings.MODEL_CONVERSATION
        model_name = "Claude Sonnet"
    
    # Step 9: Generate surface insight
    print("\n" + "=" * 80)
    print("GENERATING SURFACE INSIGHT")
    print("=" * 80)
    print(f"\n🤔 Asking Aki to sit with this data using {model_name}...")
    
    llm = LLMClient()
    
    prompt = SURFACE_PROMPT.format(
        summaries_and_memories=summaries_and_memories
    )
    
    result = await llm.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        max_tokens=1000
    )
    
    # Step 10: Display result
    print("\n" + "=" * 80)
    print("SURFACE INSIGHT")
    print("=" * 80)
    print(f"\n{result}\n")
    
    # Step 11: Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"User: {chosen_name}")
    print(f"Model: {model_name} ({model})")
    print(f"Summaries used: {len(selected_summaries)}")
    print(f"Memories used: {len(selected_memories)}")
    print(f"Input length: {len(summaries_and_memories)} characters")
    print(f"Output length: {len(result)} characters")


if __name__ == "__main__":
    asyncio.run(main())

# Made with Bob
