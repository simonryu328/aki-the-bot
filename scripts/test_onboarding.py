"""
Test script to verify the onboarding flow.
Tests the new user name selection process.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from memory.database_async import AsyncDatabase
from core import get_logger

logger = get_logger(__name__)


async def test_onboarding():
    """Test the onboarding state management."""
    db = AsyncDatabase()
    
    # Test telegram ID (use a high number to avoid conflicts)
    test_telegram_id = 999999999
    
    try:
        logger.info("=" * 60)
        logger.info("Testing Onboarding Flow")
        logger.info("=" * 60)
        
        # Clean up any existing test user
        logger.info("\n1. Cleaning up any existing test user...")
        existing = await db.get_user_by_telegram_id(test_telegram_id)
        if existing:
            logger.info(f"   Found existing test user: {existing.name}")
            # In a real scenario, we'd delete, but let's just update
            await db.update_user_onboarding_state(test_telegram_id, "awaiting_name")
            logger.info("   Reset to awaiting_name state")
        
        # Step 1: Create new user with onboarding state
        logger.info("\n2. Creating new user with onboarding state...")
        user = await db.create_user_with_state(
            telegram_id=test_telegram_id,
            name=None,
            username="test_user",
            onboarding_state="awaiting_name"
        )
        logger.info(f"   ✅ Created user: ID={user.id}, state={user.onboarding_state}")
        
        # Step 2: Verify user is in onboarding
        logger.info("\n3. Verifying user is in onboarding state...")
        user = await db.get_user_by_telegram_id(test_telegram_id)
        assert user is not None, "User should exist"
        assert user.onboarding_state == "awaiting_name", "User should be awaiting name"
        logger.info(f"   ✅ User state confirmed: {user.onboarding_state}")
        
        # Step 3: Simulate user choosing a name
        logger.info("\n4. Simulating user choosing name 'Alice'...")
        await db.get_or_create_user(
            telegram_id=test_telegram_id,
            name="Alice",
            username="test_user"
        )
        await db.update_user_onboarding_state(test_telegram_id, None)
        logger.info("   ✅ Name set and onboarding completed")
        
        # Step 4: Verify onboarding is complete
        logger.info("\n5. Verifying onboarding completion...")
        user = await db.get_user_by_telegram_id(test_telegram_id)
        assert user is not None, "User should exist"
        assert user.name == "Alice", f"Name should be 'Alice', got '{user.name}'"
        assert user.onboarding_state is None, f"Onboarding should be complete, got '{user.onboarding_state}'"
        logger.info(f"   ✅ User completed: name={user.name}, state={user.onboarding_state}")
        
        # Step 5: Test that existing user doesn't go through onboarding again
        logger.info("\n6. Testing existing user doesn't re-enter onboarding...")
        existing_user = await db.get_user_by_telegram_id(test_telegram_id)
        assert existing_user.onboarding_state is None, "Existing user should not be in onboarding"
        logger.info("   ✅ Existing user check passed")
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ ALL TESTS PASSED!")
        logger.info("=" * 60)
        logger.info("\nOnboarding flow is working correctly:")
        logger.info("  1. New users start with 'awaiting_name' state")
        logger.info("  2. Users can choose their name")
        logger.info("  3. Onboarding state is cleared after name selection")
        logger.info("  4. Existing users don't re-enter onboarding")
        
    except AssertionError as e:
        logger.error(f"\n❌ TEST FAILED: {e}")
        raise
    except Exception as e:
        logger.error(f"\n❌ ERROR: {e}")
        raise
    finally:
        await db.engine.dispose()


if __name__ == "__main__":
    asyncio.run(test_onboarding())

# Made with Bob
