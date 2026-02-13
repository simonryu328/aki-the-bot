#!/usr/bin/env python3
"""
Export user data to text files in users/<user_id>/ folder.

Usage:
    uv run python scripts/export_user.py <user_id>
    uv run python scripts/export_user.py --all
"""

import argparse
import asyncio
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import pytz
from sqlalchemy import select, desc, func

from memory.database_async import AsyncDatabase
from memory.models import User, Conversation, DiaryEntry
from config.settings import settings

TZ = pytz.timezone(settings.TIMEZONE)
USERS_DIR = Path(__file__).parent.parent / "users"


def fmt(dt_obj):
    if dt_obj is None:
        return "N/A"
    utc_time = dt_obj.replace(tzinfo=pytz.utc)
    local_time = utc_time.astimezone(TZ)
    return local_time.strftime("%Y-%m-%d %H:%M")


def fmt_short(dt_obj):
    if dt_obj is None:
        return ""
    utc_time = dt_obj.replace(tzinfo=pytz.utc)
    local_time = utc_time.astimezone(TZ)
    return local_time.strftime("%H:%M")


async def export_user(user_id: int):
    """Export all data for a user to text files."""
    db = AsyncDatabase()

    async with db.get_session() as session:
        # Get user
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            print(f"User {user_id} not found.")
            return

        user_name = user.name or f"user_{user_id}"
        user_dir = USERS_DIR / user_name.lower()
        user_dir.mkdir(parents=True, exist_ok=True)

        # ---- Diary Entries (Memories & Compacts) ----
        diary_result = await session.execute(
            select(DiaryEntry)
            .where(DiaryEntry.user_id == user_id)
            .order_by(DiaryEntry.timestamp.desc())
        )
        entries = diary_result.scalars().all()

        grouped = defaultdict(list)
        for e in entries:
            grouped[e.entry_type].append(e)

        lines = []
        lines.append(f"USER: {user.name or '-'} (ID: {user.id})")
        lines.append(f"Telegram ID: {user.telegram_id}")
        lines.append(f"Created: {fmt(user.created_at)}")
        lines.append(f"Last Active: {fmt(user.last_interaction)}")
        lines.append(f"Reach-Out: {'Enabled' if user.reach_out_enabled else 'Disabled'}")
        lines.append("")

        # Conversation Memories
        if grouped["conversation_memory"]:
            lines.append("=" * 60)
            lines.append("CONVERSATION MEMORIES")
            lines.append("=" * 60)
            for e in grouped["conversation_memory"]:
                lines.append(f"\n[{fmt(e.timestamp)}] {e.title}")
                lines.append(f"Importance: {e.importance}/10")
                lines.append(e.content)
            lines.append("")

        # Compact Summaries
        if grouped["compact_summary"]:
            lines.append("=" * 60)
            lines.append("COMPACT SUMMARIES")
            lines.append("=" * 60)
            for e in grouped["compact_summary"]:
                lines.append(f"\n[{fmt(e.timestamp)}] {e.title}")
                lines.append(e.content)
            lines.append("")

        # Significant Events
        significant = [e for e in entries if e.entry_type not in ("conversation_memory", "compact_summary")]
        if significant:
            lines.append("=" * 60)
            lines.append("SIGNIFICANT EVENTS")
            lines.append("=" * 60)
            for e in significant:
                lines.append(f"\n[{fmt(e.timestamp)}] {e.entry_type.upper()}: {e.title}")
                lines.append(e.content)
            lines.append("")

        diary_path = user_dir / "diary.txt"
        diary_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"  Wrote {diary_path} ({len(entries)} entries)")

        # ---- Conversations ----
        conv_result = await session.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.id)
        )
        convs = conv_result.scalars().all()

        conv_lines = []
        conv_lines.append(f"CONVERSATIONS: {user.name or '-'} ({len(convs)} messages)")
        conv_lines.append("=" * 60)

        for c in convs:
            role_label = "USER" if c.role == "user" else "BOT"
            date = fmt(c.timestamp)
            conv_lines.append(f"\n  [{date}] {role_label}:")
            for line in c.message.split("\n"):
                conv_lines.append(f"    {line}")
            if c.role == "assistant" and c.thinking:
                conv_lines.append(f"    --- thinking ---")
                for line in c.thinking.split("\n"):
                    conv_lines.append(f"    {line}")
                conv_lines.append(f"    ----------------")

        conv_path = user_dir / "conversations.txt"
        conv_path.write_text("\n".join(conv_lines), encoding="utf-8")
        print(f"  Wrote {conv_path} ({len(convs)} messages)")

        print(f"Exported user {user_id} ({user_name}) to {user_dir}/")


async def export_all():
    """Export all users."""
    db = AsyncDatabase()
    async with db.get_session() as session:
        result = await session.execute(select(User).order_by(User.id))
        users = result.scalars().all()
        for user in users:
            await export_user(user.id)


def main():
    parser = argparse.ArgumentParser(description="Export user data to text files")
    parser.add_argument("user_id", type=int, nargs="?", help="User ID to export")
    parser.add_argument("--all", "-a", action="store_true", help="Export all users")
    args = parser.parse_args()

    if args.all:
        asyncio.run(export_all())
    elif args.user_id is not None:
        asyncio.run(export_user(args.user_id))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
