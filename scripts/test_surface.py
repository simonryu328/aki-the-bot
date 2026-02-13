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
    """Get all users who have conversation memories."""
    async with db.get_session() as session:
        result = await session.execute(
            select(User.telegram_id, User.name)
            .join(DiaryEntry, User.id == DiaryEntry.user_id)
            .where(DiaryEntry.entry_type == 'conversation_memory')
            .distinct()
        )
        return result.all()


async def get_all_user_memories(user_id: int) -> List[DiaryEntry]:
    """Get all conversation memories for a user, ordered by most recent first."""
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
        )
        return list(result.scalars().all())


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
    print("SURFACE PROMPT TEST - MEMORY ANALYSIS")
    print("=" * 80)
    
    # Step 1: Get all users with data
    print("\n📊 Fetching users with conversation memories...")
    users = await get_users_with_data()
    
    if not users:
        print("❌ No users with memory data found!")
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
    
    # Step 4: Get all available memories
    user_id = cast(int, user.id)
    all_memories = await get_all_user_memories(user_id)
    
    print(f"\n📚 Available memories for {chosen_name}: {len(all_memories)}")
    
    if not all_memories:
        print("\n❌ No memory data available for this user!")
        return
    
    # Step 5: Display all memories with selection interface
    print("\n" + "=" * 80)
    print("SELECT MEMORIES TO ANALYZE")
    print("=" * 80)
    print("\nAll available memories (most recent first):")
    print()
    
    for i, memory in enumerate(all_memories, 1):
        timestamp = memory.timestamp.strftime("%Y-%m-%d %H:%M")
        title = cast(str, memory.title)
        print(f"{i:3d}. [{timestamp}] {title}")
    
    print("\n" + "-" * 80)
    print("Selection options:")
    print("  - Enter numbers separated by commas (e.g., 1,3,5)")
    print("  - Enter a range with dash (e.g., 1-5)")
    print("  - Combine both (e.g., 1-3,7,9-11)")
    print("  - Enter 'all' to select all memories")
    print("  - Enter 'recent N' to select N most recent (e.g., 'recent 10')")
    
    selection = input("\nYour selection: ").strip().lower()
    
    selected_memories = []
    
    if selection == 'all':
        selected_memories = all_memories
    elif selection.startswith('recent '):
        try:
            n = int(selection.split()[1])
            selected_memories = all_memories[:n]
        except (ValueError, IndexError):
            print("❌ Invalid 'recent N' format!")
            return
    else:
        # Parse comma-separated selections and ranges
        try:
            indices = set()
            parts = selection.split(',')
            for part in parts:
                part = part.strip()
                if '-' in part:
                    # Range
                    start, end = part.split('-')
                    start_idx = int(start.strip())
                    end_idx = int(end.strip())
                    indices.update(range(start_idx, end_idx + 1))
                else:
                    # Single number
                    indices.add(int(part))
            
            # Convert to 0-based and get memories
            for idx in sorted(indices):
                if 1 <= idx <= len(all_memories):
                    selected_memories.append(all_memories[idx - 1])
                else:
                    print(f"⚠️  Warning: Index {idx} out of range, skipping")
        except ValueError:
            print("❌ Invalid selection format!")
            return
    
    if not selected_memories:
        print("\n❌ No memories selected!")
        return
    
    # Step 6: Format the data
    print("\n" + "=" * 80)
    print("PREPARING PROMPT")
    print("=" * 80)
    
    memories_text = format_memories(selected_memories)
    
    print(f"\n📝 Using {len(selected_memories)} memories:")
    for i, memory in enumerate(selected_memories, 1):
        timestamp = memory.timestamp.strftime("%Y-%m-%d %H:%M")
        title = cast(str, memory.title)
        print(f"   {i}. [{timestamp}] {title}")
    print(f"\nTotal characters: {len(memories_text)}")
    
    # Step 7: Show the formatted data
    print("\n" + "=" * 80)
    print("FORMATTED DATA")
    print("=" * 80)
    print(memories_text)
    
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
    
    # Step 9: Generate analysis
    print("\n" + "=" * 80)
    print("ANALYZING USER INTERESTS")
    print("=" * 80)
    print(f"\n🤔 Analyzing what the user wants to talk about using {model_name}...")
    
    llm = LLMClient()
    
    prompt = SURFACE_PROMPT.format(
        summaries_and_memories=memories_text
    )
    
    print("\n" + "=" * 80)
    print("RAW PROMPT SENT TO LLM")
    print("=" * 80)
    print(prompt)
    print("\n" + "=" * 80)
    
    result = await llm.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        max_tokens=1000
    )
    
    # Step 10: Display raw and parsed result
    print("\n" + "=" * 80)
    print("RAW LLM RESPONSE")
    print("=" * 80)
    print(f"\n{result}\n")
    
    print("=" * 80)
    print("ANALYSIS RESULT (SAME AS RAW)")
    print("=" * 80)
    print(f"\n{result}\n")
    
    # Step 11: Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"User: {chosen_name}")
    print(f"Model: {model_name} ({model})")
    print(f"Memories analyzed: {len(selected_memories)}")
    print(f"Input length: {len(memories_text)} characters")
    print(f"Output length: {len(result)} characters")


if __name__ == "__main__":
    asyncio.run(main())

# Made with Bob
