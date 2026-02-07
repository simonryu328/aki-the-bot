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
from memory.models import User, ProfileFact, Conversation, ScheduledMessage, TimelineEvent
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

        # ---- Profile & Observations ----
        facts_result = await session.execute(
            select(ProfileFact)
            .where(ProfileFact.user_id == user_id)
            .order_by(ProfileFact.category, ProfileFact.observed_at.desc())
        )
        facts = facts_result.scalars().all()

        grouped = defaultdict(list)
        for f in facts:
            grouped[f.category].append(f)

        lines = []
        lines.append(f"USER: {user.name or '-'} (ID: {user.id})")
        lines.append(f"Telegram ID: {user.telegram_id}")
        lines.append(f"Created: {fmt(user.created_at)}")
        lines.append(f"Last Active: {fmt(user.last_interaction)}")
        lines.append("")

        # Condensed narratives
        if "condensed" in grouped:
            lines.append("=" * 60)
            lines.append("CONDENSED NARRATIVES")
            lines.append("=" * 60)
            for f in grouped["condensed"]:
                lines.append(f"\n[{f.key}]")
                lines.append(f.value)
                lines.append(f"(condensed: {fmt(f.updated_at)})")
            lines.append("")

        # Static facts
        if "static" in grouped:
            lines.append("=" * 60)
            lines.append("STATIC FACTS")
            lines.append("=" * 60)
            for f in grouped["static"]:
                lines.append(f"- {f.value}")
            lines.append("")

        # Raw observations
        raw_categories = [c for c in sorted(grouped.keys()) if c not in ("condensed", "static", "system")]
        raw_count = sum(len(grouped[c]) for c in raw_categories)
        lines.append("=" * 60)
        lines.append(f"RAW OBSERVATIONS ({raw_count} total)")
        lines.append("=" * 60)
        for category in raw_categories:
            lines.append(f"\n[{category}] ({len(grouped[category])} observations)")
            for f in grouped[category]:
                lines.append(f"  [{fmt(f.observed_at)}] {f.value}")
        lines.append("")

        profile_path = user_dir / "profile.txt"
        profile_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"  Wrote {profile_path} ({len(facts)} facts)")

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
            ts = fmt_short(c.timestamp)
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
