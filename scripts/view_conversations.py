"""
View full conversations for a user.

Usage:
    uv run python scripts/view_conversations.py <user_id> [--limit N] [--offset N]

Examples:
    uv run python scripts/view_conversations.py 2
    uv run python scripts/view_conversations.py 2 --limit 10
    uv run python scripts/view_conversations.py 1 --limit 20 --offset 5
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


async def view_conversations(user_id: int, limit: int = 30, offset: int = 0):
    from sqlalchemy import select, desc, func
    from memory.database_async import AsyncDatabase
    from memory.models import Conversation

    db = AsyncDatabase()

    async with db.get_session() as session:
        # Get total count
        count_result = await session.execute(
            select(func.count()).select_from(Conversation).where(Conversation.user_id == user_id)
        )
        total = count_result.scalar()

        # Get messages
        result = await session.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(desc(Conversation.id))
            .offset(offset)
            .limit(limit)
        )
        convs = list(reversed(result.scalars().all()))

        print(f"\n{'='*60}")
        print(f"User {user_id} - Showing {len(convs)} of {total} messages (offset: {offset})")
        print(f"{'='*60}\n")

        for i, c in enumerate(convs):
            role_label = "👤 USER" if c.role == "user" else "🤖 BOT"
            print(f"[{offset + i + 1}] {role_label}")
            print("-" * 40)
            print(c.message)
            print()


def main():
    parser = argparse.ArgumentParser(description="View conversations for a user")
    parser.add_argument("user_id", type=int, help="User ID to view")
    parser.add_argument("--limit", "-l", type=int, default=30, help="Number of messages (default: 30)")
    parser.add_argument("--offset", "-o", type=int, default=0, help="Skip first N messages (default: 0)")

    args = parser.parse_args()

    asyncio.run(view_conversations(args.user_id, args.limit, args.offset))


if __name__ == "__main__":
    main()
