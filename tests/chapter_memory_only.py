#!/usr/bin/env python3
"""
Generate chapters for Simon using ONLY conversation_memory entries (no compact_summary).
Comparison test against the interleaved approach.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.database_async import db
from memory.models import DiaryEntry, User
from sqlalchemy import select, desc
from config.settings import settings
from utils.llm_client import llm_client

MEMORY_ONLY_CHAPTER_PROMPT = """You are writing a biography chapter about {user_name}'s recent life.

Below are {entry_count} personal reflections from conversations with {user_name}, written from the perspective of someone who knows them well.

{memory_entries}

---
Write a cohesive narrative chapter (2-3 paragraphs) covering this period.

Guidelines:
- Identify and connect major themes across these reflections
- Write in third person about {user_name}, as a biographer would
- Focus on life changes, decisions, growth, and meaningful patterns
- Preserve emotional depth and character insights
- Include specific dates when available
- Length: 2-3 substantial paragraphs
"""

OUTPUT_FILE = Path(__file__).parent.parent / "chapter_output_memory_only.txt"


async def main():
    user_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    lines = []

    async with db.get_session() as session:
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
        
        stmt = (
            select(DiaryEntry)
            .where(
                DiaryEntry.user_id == user_id,
                DiaryEntry.entry_type == 'conversation_memory'
            )
            .order_by(DiaryEntry.timestamp)  # chronological
        )
        result = await session.execute(stmt)
        memories = list(result.scalars().all())

    user_name = user.name or "User"
    output_file = Path(__file__).parent.parent / f"chapter_output_memory_only_{user_name.lower()}.txt"
    lines.append(f"# Chapters for {user_name} (Memory-Only Approach)")
    lines.append(f"# Total memory entries: {len(memories)}\n")

    batch_size = 5
    batches = [memories[i:i + batch_size] for i in range(0, len(memories), batch_size)]

    for bi, batch in enumerate(batches):
        t0 = batch[0].timestamp.strftime("%Y-%m-%d %H:%M")
        t1 = batch[-1].timestamp.strftime("%Y-%m-%d %H:%M")
        lines.append(f"\n{'='*60}")
        lines.append(f"Chapter {bi+1}  ({t0} -> {t1})  [{len(batch)} entries]")
        lines.append(f"{'='*60}\n")

        # Format memory entries
        sections = []
        for i, mem in enumerate(batch, 1):
            date_str = mem.timestamp.strftime("%Y-%m-%d")
            sections.append(f"--- Reflection {i} [{date_str}] ---\n{mem.content.strip()}")
        memory_text = "\n\n".join(sections)

        prompt = MEMORY_ONLY_CHAPTER_PROMPT.format(
            user_name=user_name,
            entry_count=len(batch),
            memory_entries=memory_text,
        )

        try:
            response = await llm_client.chat(
                model=settings.MODEL_SUMMARY,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1000,
            )
            lines.append(response.strip())
        except Exception as e:
            lines.append(f"ERROR: {e}")
        lines.append("")

    text = "\n".join(lines)
    output_file.write_text(text, encoding="utf-8")
    print(f"Output written to {output_file}")
    print(text)


if __name__ == "__main__":
    asyncio.run(main())
