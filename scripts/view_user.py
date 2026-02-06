#!/usr/bin/env python3
"""
Comprehensive user viewer for monitoring beta testers.

Usage:
    uv run python scripts/view_user.py <user_id>
    uv run python scripts/view_user.py <user_id> --conversations 50
    uv run python scripts/view_user.py --list

Shows: user info, profile, observations, conversations (with thinking), scheduled messages.
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


def fmt(dt_obj):
    """Format a UTC datetime to local timezone string."""
    if dt_obj is None:
        return "N/A"
    utc_time = dt_obj.replace(tzinfo=pytz.utc)
    local_time = utc_time.astimezone(TZ)
    return local_time.strftime("%Y-%m-%d %H:%M")


def fmt_short(dt_obj):
    """Format a UTC datetime to short time string."""
    if dt_obj is None:
        return ""
    utc_time = dt_obj.replace(tzinfo=pytz.utc)
    local_time = utc_time.astimezone(TZ)
    return local_time.strftime("%H:%M")


def section(title):
    """Print a section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


async def list_users():
    """List all users with basic info."""
    db = AsyncDatabase()

    async with db.engine.begin() as conn:
        pass  # just to initialize

    async with db.get_session() as session:
        result = await session.execute(
            select(User).order_by(User.id)
        )
        users = result.scalars().all()

        if not users:
            print("No users found.")
            return

        print(f"\n{'ID':<5} {'Name':<20} {'Username':<20} {'Messages':<10} {'Last Active'}")
        print("-" * 80)

        for user in users:
            # Get message count
            count_result = await session.execute(
                select(func.count()).select_from(Conversation).where(Conversation.user_id == user.id)
            )
            msg_count = count_result.scalar()

            print(
                f"{user.id:<5} "
                f"{(user.name or '-'):<20} "
                f"{('@' + user.username if user.username else '-'):<20} "
                f"{msg_count:<10} "
                f"{fmt(user.last_interaction)}"
            )

        print()


async def view_user(user_id: int, conv_limit: int = 20, obs_days: int = 30):
    """Show comprehensive user data."""
    db = AsyncDatabase()

    async with db.get_session() as session:
        # ---- User Info ----
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            print(f"User {user_id} not found.")
            return

        section("USER INFO")
        print(f"  ID:           {user.id}")
        print(f"  Telegram ID:  {user.telegram_id}")
        print(f"  Name:         {user.name or '-'}")
        print(f"  Username:     @{user.username}" if user.username else "  Username:     -")
        print(f"  Created:      {fmt(user.created_at)}")
        print(f"  Last Active:  {fmt(user.last_interaction)}")

        # ---- Profile Facts ----
        facts_result = await session.execute(
            select(ProfileFact)
            .where(ProfileFact.user_id == user_id)
            .order_by(ProfileFact.category, ProfileFact.observed_at.desc())
        )
        facts = facts_result.scalars().all()

        section(f"PROFILE FACTS ({len(facts)} total)")
        if facts:
            grouped = defaultdict(list)
            for f in facts:
                grouped[f.category].append(f)

            for category in sorted(grouped.keys()):
                print(f"\n  [{category}]")
                for f in grouped[category]:
                    print(f"    - {f.value}")
                    print(f"      (observed: {fmt(f.observed_at)}, confidence: {f.confidence})")
        else:
            print("  (no profile facts)")

        # ---- Recent Observations Timeline ----
        cutoff = datetime.now(pytz.utc).replace(tzinfo=None) - timedelta(days=obs_days)
        obs_result = await session.execute(
            select(ProfileFact)
            .where(ProfileFact.user_id == user_id, ProfileFact.observed_at >= cutoff)
            .order_by(ProfileFact.observed_at.desc())
        )
        observations = obs_result.scalars().all()

        section(f"OBSERVATIONS (last {obs_days} days)")
        if observations:
            for obs in observations:
                print(f"  [{fmt(obs.observed_at)}] {obs.category}: {obs.value}")
        else:
            print("  (no recent observations)")

        # ---- Pending Scheduled Messages ----
        sched_result = await session.execute(
            select(ScheduledMessage)
            .where(ScheduledMessage.user_id == user_id, ScheduledMessage.executed == False)
            .order_by(ScheduledMessage.scheduled_time)
        )
        scheduled = sched_result.scalars().all()

        section(f"PENDING SCHEDULED MESSAGES ({len(scheduled)})")
        if scheduled:
            for msg in scheduled:
                print(f"  [{fmt(msg.scheduled_time)}] {msg.message_type}")
                if msg.context:
                    print(f"    Context: {msg.context}")
        else:
            print("  (none)")

        # ---- Timeline Events ----
        events_result = await session.execute(
            select(TimelineEvent)
            .where(TimelineEvent.user_id == user_id)
            .order_by(TimelineEvent.datetime.desc())
            .limit(10)
        )
        events = events_result.scalars().all()

        section(f"TIMELINE EVENTS ({len(events)})")
        if events:
            for event in events:
                reminded = " [reminded]" if event.reminded else ""
                print(f"  [{fmt(event.datetime)}] {event.event_type}: {event.title}{reminded}")
                if event.description:
                    print(f"    {event.description}")
        else:
            print("  (none)")

        # ---- Conversations ----
        conv_result = await session.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(desc(Conversation.id))
            .limit(conv_limit)
        )
        convs = list(reversed(conv_result.scalars().all()))

        # Get total count
        count_result = await session.execute(
            select(func.count()).select_from(Conversation).where(Conversation.user_id == user_id)
        )
        total = count_result.scalar()

        section(f"CONVERSATIONS (showing {len(convs)} of {total})")
        if convs:
            for c in convs:
                role_label = "USER" if c.role == "user" else "BOT"
                ts = fmt_short(c.timestamp)
                print(f"\n  [{ts}] {role_label}:")
                # Indent message lines
                for line in c.message.split("\n"):
                    print(f"    {line}")

                # Show thinking for assistant messages
                if c.role == "assistant" and c.thinking:
                    print(f"    --- thinking ---")
                    for line in c.thinking.split("\n"):
                        print(f"    {line}")
                    print(f"    ----------------")
        else:
            print("  (no conversations)")

        print()


def main():
    parser = argparse.ArgumentParser(description="View comprehensive user data for monitoring")
    parser.add_argument("user_id", type=int, nargs="?", help="User ID to view")
    parser.add_argument("--list", "-L", action="store_true", help="List all users")
    parser.add_argument("--conversations", "-c", type=int, default=20, help="Number of conversations (default: 20)")
    parser.add_argument("--observations", "-o", type=int, default=30, help="Days of observations (default: 30)")

    args = parser.parse_args()

    if args.list:
        asyncio.run(list_users())
    elif args.user_id is not None:
        asyncio.run(view_user(args.user_id, args.conversations, args.observations))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
