"""
Test script for rate limiting functionality.

Tests the RateLimiter class to ensure it correctly:
1. Allows messages within the limit
2. Blocks messages when limit is exceeded
3. Resets after the time window passes
4. Handles disabled rate limiting (limit = 0)
"""

import asyncio
import time
from datetime import datetime

# Import the RateLimiter class
import sys
sys.path.insert(0, '.')

from bot.telegram_handler import RateLimiter


def test_rate_limiter_basic():
    """Test basic rate limiting functionality."""
    print("\n=== Test 1: Basic Rate Limiting ===")
    
    # Create limiter: 5 messages per 10 seconds
    limiter = RateLimiter(max_messages=5, window_seconds=10)
    user_id = 12345
    
    print(f"Limiter: {limiter.max_messages} messages per {limiter.window_seconds}s")
    
    # Send 5 messages - all should be allowed
    for i in range(5):
        allowed, remaining = limiter.check_rate_limit(user_id)
        print(f"Message {i+1}: allowed={allowed}, remaining={remaining}")
        assert allowed, f"Message {i+1} should be allowed"
    
    # 6th message should be blocked
    allowed, remaining = limiter.check_rate_limit(user_id)
    print(f"Message 6: allowed={allowed}, remaining={remaining}")
    assert not allowed, "Message 6 should be blocked"
    assert remaining == 0, "Should have 0 remaining"
    
    print("✅ Basic rate limiting works correctly")


def test_rate_limiter_sliding_window():
    """Test sliding window behavior."""
    print("\n=== Test 2: Sliding Window ===")
    
    # Create limiter: 3 messages per 2 seconds
    limiter = RateLimiter(max_messages=3, window_seconds=2)
    user_id = 67890
    
    print(f"Limiter: {limiter.max_messages} messages per {limiter.window_seconds}s")
    
    # Send 3 messages
    for i in range(3):
        allowed, remaining = limiter.check_rate_limit(user_id)
        print(f"Message {i+1}: allowed={allowed}, remaining={remaining}")
        assert allowed, f"Message {i+1} should be allowed"
    
    # 4th message should be blocked
    allowed, remaining = limiter.check_rate_limit(user_id)
    print(f"Message 4 (immediate): allowed={allowed}, remaining={remaining}")
    assert not allowed, "Message 4 should be blocked immediately"
    
    # Wait for window to pass
    print("Waiting 2.5 seconds for window to reset...")
    time.sleep(2.5)
    
    # Now should be allowed again
    allowed, remaining = limiter.check_rate_limit(user_id)
    print(f"Message 5 (after wait): allowed={allowed}, remaining={remaining}")
    assert allowed, "Message 5 should be allowed after window reset"
    
    print("✅ Sliding window works correctly")


def test_rate_limiter_multiple_users():
    """Test that rate limits are per-user."""
    print("\n=== Test 3: Multiple Users ===")
    
    limiter = RateLimiter(max_messages=2, window_seconds=10)
    user1 = 111
    user2 = 222
    
    print(f"Limiter: {limiter.max_messages} messages per {limiter.window_seconds}s")
    
    # User 1 sends 2 messages
    for i in range(2):
        allowed, remaining = limiter.check_rate_limit(user1)
        print(f"User1 message {i+1}: allowed={allowed}, remaining={remaining}")
        assert allowed
    
    # User 1's 3rd message should be blocked
    allowed, remaining = limiter.check_rate_limit(user1)
    print(f"User1 message 3: allowed={allowed}, remaining={remaining}")
    assert not allowed, "User 1 should be rate limited"
    
    # User 2 should still be able to send
    allowed, remaining = limiter.check_rate_limit(user2)
    print(f"User2 message 1: allowed={allowed}, remaining={remaining}")
    assert allowed, "User 2 should not be affected by User 1's limit"
    
    print("✅ Per-user rate limiting works correctly")


def test_rate_limiter_disabled():
    """Test disabled rate limiting (limit = 0)."""
    print("\n=== Test 4: Disabled Rate Limiting ===")
    
    limiter = RateLimiter(max_messages=0, window_seconds=10)
    user_id = 99999
    
    print(f"Limiter: disabled (max_messages=0)")
    assert limiter.disabled, "Limiter should be disabled"
    
    # Should allow unlimited messages
    for i in range(100):
        allowed, remaining = limiter.check_rate_limit(user_id)
        assert allowed, f"Message {i+1} should be allowed (limiter disabled)"
    
    print(f"Sent 100 messages - all allowed")
    print("✅ Disabled rate limiting works correctly")


def test_rate_limiter_reset():
    """Test manual reset functionality."""
    print("\n=== Test 5: Manual Reset ===")
    
    limiter = RateLimiter(max_messages=2, window_seconds=10)
    user_id = 55555
    
    # Send 2 messages
    for i in range(2):
        allowed, remaining = limiter.check_rate_limit(user_id)
        print(f"Message {i+1}: allowed={allowed}, remaining={remaining}")
        assert allowed
    
    # 3rd should be blocked
    allowed, remaining = limiter.check_rate_limit(user_id)
    print(f"Message 3: allowed={allowed}, remaining={remaining}")
    assert not allowed
    
    # Reset the user
    limiter.reset_user(user_id)
    print("Reset user rate limit")
    
    # Should be able to send again
    allowed, remaining = limiter.check_rate_limit(user_id)
    print(f"Message 4 (after reset): allowed={allowed}, remaining={remaining}")
    assert allowed, "Should be allowed after reset"
    
    print("✅ Manual reset works correctly")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing Rate Limiter Implementation")
    print("=" * 60)
    
    try:
        test_rate_limiter_basic()
        test_rate_limiter_sliding_window()
        test_rate_limiter_multiple_users()
        test_rate_limiter_disabled()
        test_rate_limiter_reset()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

# Made with Bob
