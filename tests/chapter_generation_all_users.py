#!/usr/bin/env python3
"""
Generate chapters for ALL users and write output to a readable file.
Dry-run only (no DB writes).
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
from prompts.chapter import CHAPTER_PROMPT

OUTPUT_FILE = Path(__file__).parent.parent / "chapter_output.txt"


async def fetch_and_pair(session, user_id: int) -> list:
    stmt = (
        select(DiaryEntry)
        .where(
            DiaryEntry.user_id == user_id,
            DiaryEntry.entry_type.in_(['compact_summary', 'conversation_memory'])
        )
        .order_by(desc(DiaryEntry.timestamp))
        .limit(40)
    )
    result = await session.execute(stmt)
    entries = list(result.scalars().all())

    summaries = [e for e in entries if e.entry_type == 'compact_summary']
    memories = [e for e in entries if e.entry_type == 'conversation_memory']

    pairs = []
    used_ids = set()
    for summ in summaries:
        for mem in memories:
            if mem.id in used_ids:
                continue
            if summ.exchange_start and mem.exchange_start and summ.exchange_end and mem.exchange_end:
                sd = abs((summ.exchange_start - mem.exchange_start).total_seconds())
                ed = abs((summ.exchange_end - mem.exchange_end).total_seconds())
                if sd < 5.0 and ed < 5.0:
                    pairs.append((summ, mem))
                    used_ids.add(mem.id)
                    break

    pairs.sort(key=lambda p: p[0].timestamp)
    return pairs


def format_paired_entries(pairs):
    sections = []
    for i, (summ, mem) in enumerate(pairs, 1):
        date_str = summ.timestamp.strftime("%Y-%m-%d")
        sections.append(
            f"--- Exchange {i} [{date_str}] ---\n"
            f"FACTS: {summ.content.strip()}\n"
            f"MEANING: {mem.content.strip()}"
        )
    return "\n\n".join(sections)


async def main():
    lines = []

    async with db.get_session() as session:
        users = (await session.execute(select(User))).scalars().all()

    for user in users:
        lines.append(f"\n{'#'*70}")
        lines.append(f"# USER: {user.name}  (id={user.id})")
        lines.append(f"{'#'*70}\n")

        async with db.get_session() as session:
            pairs = await fetch_and_pair(session, user.id)

        if len(pairs) < 2:
            lines.append("  (Not enough paired entries to generate chapters)\n")
            continue

        lines.append(f"  Found {len(pairs)} paired entries\n")

        batch_size = 5
        batches = [pairs[i:i + batch_size] for i in range(0, len(pairs), batch_size)]

        for bi, batch in enumerate(batches):
            t0 = batch[0][0].timestamp.strftime("%Y-%m-%d %H:%M")
            t1 = batch[-1][0].timestamp.strftime("%Y-%m-%d %H:%M")
            lines.append(f"  --- Chapter {bi+1}  ({t0} -> {t1})  [{len(batch)} pairs] ---\n")

            paired_text = format_paired_entries(batch)
            prompt = CHAPTER_PROMPT.format(
                user_name=user.name or "User",
                pair_count=len(batch),
                paired_entries=paired_text,
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
                lines.append(f"  ERROR: {e}")

            lines.append("")

    text = "\n".join(lines)
    OUTPUT_FILE.write_text(text, encoding="utf-8")
    print(f"Output written to {OUTPUT_FILE}")
    print(text)


if __name__ == "__main__":
    asyncio.run(main())
