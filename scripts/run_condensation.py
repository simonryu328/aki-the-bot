#!/usr/bin/env python3
"""
Manual condensation runner for testing.

Usage:
    uv run python scripts/run_condensation.py <user_id>
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


async def run_condensation(user_id: int):
    """Run condensation for a specific user."""
    from memory.memory_manager_async import memory_manager
    from agents.soul_agent import soul_agent

    # Get user info
    user = await memory_manager.get_user_by_id(user_id)
    if not user:
        print(f"User {user_id} not found.")
        return

    user_name = user.name or "them"
    print(f"Running condensation for user {user_id} ({user_name})...")

    # Get observation count
    obs_count = await memory_manager.db.get_observation_count(user_id)
    print(f"Total observations: {obs_count}")

    # Get current profile to show before state
    profile = await memory_manager.get_user_profile(user_id)
    categories = [c for c in profile.keys() if c not in ("system", "condensed")]
    print(f"Categories: {', '.join(categories)}")
    for cat in categories:
        print(f"  {cat}: {len(profile[cat])} observations")

    print("\nCondensing...")
    condensed = await soul_agent.compact_observations(user_id, user_name)

    if condensed:
        print(f"\nCondensed {len(condensed)} categories:\n")
        for category, narrative in condensed.items():
            print(f"[{category}]")
            print(f"  {narrative}")
            print()
    else:
        print("No observations to condense.")


def main():
    parser = argparse.ArgumentParser(description="Run observation condensation")
    parser.add_argument("user_id", type=int, help="User ID to condense observations for")
    args = parser.parse_args()
    asyncio.run(run_condensation(args.user_id))


if __name__ == "__main__":
    main()
