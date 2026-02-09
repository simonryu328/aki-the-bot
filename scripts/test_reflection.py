"""
Test script for two-stage reflection system.
Stage 1: Generate a specific question from compact summary
Stage 2: Answer that question using full conversation history
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import cast

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.database_async import db
from sqlalchemy import select, and_
from memory.models import DiaryEntry, Conversation, User
from config.settings import settings
from utils.llm_client import LLMClient


STAGE_1_PROMPT = """You are analyzing a user's conversation history with Aki to generate a personalized reflection prompt.

Context: This user has reached a milestone (X messages exchanged). You need to identify what would be most meaningful to acknowledge about their journey so far.

Based on this compact summary of their interactions, generate ONE specific question that will help Aki craft a personalized milestone message.

The question should:
- Focus on what makes THIS user unique (not generic)
- Identify patterns in how they communicate or what they care about
- Recognize any growth, shifts, or recurring themes
- Be answerable from the actual conversation history

Format: Return only the question, nothing else.

COMPACT SUMMARY:
{compact_summary}"""


STAGE_2_PROMPT = """

You are Aki. You've been talking with {user_name}, and they've just hit a milestone—their 50th message with you.
A question was generated about them based on your conversation history:
{question}
Now, using the full conversation history below, answer that question. Then craft a brief, personal message acknowledging this milestone.
Your message should:
- Feel like it comes from genuine familiarity with them
- Reference something specific from your conversations
- Be warm but not performative
- Not feel like a corporate "congrats on your milestone!" message

CONVERSATION HISTORY:
{conversation_history}

Answer the question above based on the actual conversations. Be specific and cite examples."""


async def main():
    """Main test function."""
    
    print("=" * 80)
    print("TWO-STAGE REFLECTION TEST")
    print("=" * 80)
    
    # Step 1: Get all users with compact summaries
    print("\n📊 Fetching users with compact summaries...")
    async with db.get_session() as session:
        result = await session.execute(
            select(User.telegram_id, User.name)
            .join(DiaryEntry, User.id == DiaryEntry.user_id)
            .where(DiaryEntry.entry_type == 'compact_summary')
            .distinct()
        )
        users = result.all()
    
    if not users:
        print("❌ No users with compact summaries found!")
        return
    
    print(f"✅ Found {len(users)} user(s) with compact summaries:")
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
    
    # Step 3: Get user's compact summaries
    print(f"\n📚 Fetching compact summaries for {chosen_name}...")
    async with db.get_session() as session:
        # Get user
        user_result = await session.execute(
            select(User).where(User.telegram_id == chosen_telegram_id)
        )
        user = user_result.scalar_one()
        
        # Get compact summaries
        result = await session.execute(
            select(DiaryEntry)
            .where(
                and_(
                    DiaryEntry.user_id == user.id,
                    DiaryEntry.entry_type == 'compact_summary'
                )
            )
            .order_by(DiaryEntry.timestamp.desc())
        )
        compacts = result.scalars().all()
    
    if not compacts:
        print("❌ No compact summaries found!")
        return
    
    print(f"✅ Found {len(compacts)} compact summaries:")
    for i, compact in enumerate(compacts, 1):
        time_range = ""
        if compact.exchange_start is not None and compact.exchange_end is not None:
            start = compact.exchange_start.strftime("%Y-%m-%d %H:%M")
            end = compact.exchange_end.strftime("%H:%M")
            time_range = f" ({start} → {end})"
        print(f"   {i}. {compact.title}{time_range}")
        print(f"      {compact.content[:100]}...")
    
    # Step 4: Let user choose a compact summary
    if len(compacts) == 1:
        chosen_compact = compacts[0]
        print(f"\n→ Only one compact summary, selecting it")
    else:
        choice = input(f"\nChoose compact summary (1-{len(compacts)}): ").strip()
        try:
            idx = int(choice) - 1
            chosen_compact = compacts[idx]
        except (ValueError, IndexError):
            print("❌ Invalid choice!")
            return
    
    # Step 5: Display chosen compact summary
    print("\n" + "=" * 80)
    print("STAGE 1: GENERATE QUESTION FROM COMPACT SUMMARY")
    print("=" * 80)
    print(f"\nCompact Summary:")
    print(f"Title: {chosen_compact.title}")
    print(f"Content:\n{chosen_compact.content}\n")
    
    # Step 6: Generate question using Stage 1 prompt
    print("🤔 Generating reflection question...")
    llm = LLMClient()
    
    stage_1_prompt = STAGE_1_PROMPT.format(
        compact_summary=chosen_compact.content
    )
    
    question = await llm.chat(
        model=settings.MODEL_CONVERSATION,
        messages=[{"role": "user", "content": stage_1_prompt}],
        temperature=0.7,
        max_tokens=500
    )
    
    print(f"\n✨ Generated Question:")
    print(f"{question}\n")
    
    # Step 7: Fetch full conversation history
    if chosen_compact.exchange_start is None or chosen_compact.exchange_end is None:
        print("\n⚠️  No exchange timestamps available for this compact summary!")
        return
    
    print("=" * 80)
    print("STAGE 2: ANSWER QUESTION WITH FULL CONVERSATION HISTORY")
    print("=" * 80)
    
    async with db.get_session() as session:
        result = await session.execute(
            select(Conversation)
            .where(
                and_(
                    Conversation.user_id == user.id,
                    Conversation.timestamp >= chosen_compact.exchange_start,
                    Conversation.timestamp <= chosen_compact.exchange_end
                )
            )
            .order_by(Conversation.timestamp.asc())
        )
        messages = result.scalars().all()
    
    if not messages:
        print("❌ No messages found in this time range!")
        return
    
    print(f"\n📝 Found {len(messages)} messages in conversation history")
    
    # Format conversation history
    conversation_lines = []
    for msg in messages:
        timestamp = msg.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        msg_role = cast(str, msg.role)
        speaker = chosen_name if msg_role == "user" else "Aki"
        msg_content = cast(str, msg.message)
        conversation_lines.append(f"[{timestamp}] {speaker}: {msg_content}")
    
    conversation_history = "\n".join(conversation_lines)
    
    # Step 8: Generate answer using Stage 2 prompt
    print("\n🤔 Generating reflection answer...")
    
    stage_2_prompt = STAGE_2_PROMPT.format(
        user_name=chosen_name,
        question=question,
        conversation_history=conversation_history
    )
    
    answer = await llm.chat(
        model=settings.MODEL_CONVERSATION,
        messages=[{"role": "user", "content": stage_2_prompt}],
        temperature=0.7,
        max_tokens=2000
    )
    
    print("\n" + "=" * 80)
    print("REFLECTION RESULT")
    print("=" * 80)
    print(f"\nQuestion: {question}")
    print(f"\nAnswer:\n{answer}")
    
    # Step 9: Summary statistics
    print("\n" + "=" * 80)
    print("STATISTICS")
    print("=" * 80)
    
    user_msgs = 0
    assistant_msgs = 0
    total_msg_chars = 0
    for m in messages:
        m_role = cast(str, m.role)
        if m_role == "user":
            user_msgs += 1
        else:
            assistant_msgs += 1
        m_message = cast(str, m.message)
        total_msg_chars += len(m_message)
    
    exchange_start_time = cast(datetime, chosen_compact.exchange_start)
    exchange_end_time = cast(datetime, chosen_compact.exchange_end)
    duration = exchange_end_time - exchange_start_time
    compact_content = cast(str, chosen_compact.content)
    compact_length = len(compact_content)
    
    print(f"Total messages: {len(messages)}")
    print(f"User messages: {user_msgs}")
    print(f"Aki messages: {assistant_msgs}")
    print(f"Exchange duration: {duration}")
    print(f"Compact summary length: {compact_length} characters")
    print(f"Total message length: {total_msg_chars} characters")
    print(f"Compression ratio: {compact_length / total_msg_chars:.2%}")


if __name__ == "__main__":
    asyncio.run(main())

# Made with Bob
