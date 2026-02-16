"""Quick script to reset onboarding state for testing the welcome flow."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import select
from memory.database_async import AsyncDatabase
from memory.models import User


async def main():
    db = AsyncDatabase()

    async with db.get_session() as session:
        result = await session.execute(
            select(User.id, User.telegram_id, User.name, User.onboarding_state, User.timezone)
        )
        users = result.all()

    print("\nCurrent users:")
    for u in users:
        print(f"  id={u.id}  telegram_id={u.telegram_id}  name={u.name}  onboarding={u.onboarding_state}  tz={u.timezone}")

    if not users:
        print("No users found!")
        return

    # Reset the first user
    target = users[0]
    print(f"\nResetting user '{target.name}' (telegram_id={target.telegram_id}) to awaiting_setup...")

    await db.update_user_onboarding_state(
        telegram_id=target.telegram_id,
        onboarding_state="awaiting_setup"
    )

    print("Done! Open the mini app now to see the welcome flow.")


if __name__ == "__main__":
    asyncio.run(main())
