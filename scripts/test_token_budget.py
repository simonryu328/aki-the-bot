"""
Verification script for per-user daily token budgets.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.orchestrator import orchestrator
from memory.memory_manager_async import memory_manager
from config.settings import settings
from core import get_logger

logger = get_logger(__name__)

async def test_token_budget():
    """
    Test that the orchestrator correctly enforces token budgets.
    """
    
    telegram_id = 987654321  # Use a different ID to avoid conflicts
    user_id = None
    
    try:
        # 1. Get user
        user = await memory_manager.get_or_create_user(telegram_id=telegram_id, name="Budget Tester")
        user_id = user.id
        
        # 2. Record some initial usage to stay below budget
        original_budget = settings.USER_DAILY_TOKEN_BUDGET
        settings.USER_DAILY_TOKEN_BUDGET = 500  # Set a small budget for testing
        
        logger.info(f"Testing with budget: {settings.USER_DAILY_TOKEN_BUDGET}")
        
        # Record 400 tokens (below budget)
        await memory_manager.record_token_usage(
            user_id=user_id,
            model="gpt-4o",
            input_tokens=200,
            output_tokens=200,
            total_tokens=400,
            call_type="test"
        )
        
        usage_now = await memory_manager.db.get_user_token_usage_today(user_id)
        logger.info(f"Usage after first record: {usage_now}")
        
        # 3. Process message (should succeed)
        # We need to wait a bit because recording usage in orchestrator is a background task
        messages, emoji = await orchestrator.process_message(telegram_id, "Hello under budget")
        logger.info(f"Response while under budget: {messages}")
        await asyncio.sleep(1) # Wait for background recording
        
        # 4. Record usage to exceed budget
        await memory_manager.record_token_usage(
            user_id=user_id,
            model="gpt-4o",
            input_tokens=100,
            output_tokens=100,
            total_tokens=200,
            call_type="test"
        )
        
        usage_now = await memory_manager.db.get_user_token_usage_today(user_id)
        logger.info(f"Usage after exceeding: {usage_now}")
        
        # 5. Process message (should fail)
        messages, emoji = await orchestrator.process_message(telegram_id, "Hello over budget")
        logger.info(f"Response while over budget: {messages}")
        
        if len(messages) == 1 and "pause here" in messages[0]:
            logger.info("✅ Budget enforcement successful!")
        else:
            logger.error(f"❌ Budget enforcement failed! Messages: {messages}")
            
        # Restore settings
        settings.USER_DAILY_TOKEN_BUDGET = original_budget
        
    finally:
        # Cleanup test data if needed (optional)
        # We'll just leave it as it's a test user
        pass

if __name__ == "__main__":
    asyncio.run(test_token_budget())
