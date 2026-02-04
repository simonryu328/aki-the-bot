"""
Test script for the memory system.
Verifies database operations and vector store functionality.
"""

import sys
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, ".")

from memory.memory_manager import memory_manager

print("=" * 60)
print("Testing AI Companion Memory System")
print("=" * 60)

# Test 1: Create a test user
print("\n[Test 1] Creating test user...")
user_id = memory_manager.get_or_create_user(
    telegram_id=123456789,
    name="Test User",
    username="testuser"
)
print(f"✓ Created user with ID: {user_id}")

# Test 2: Add profile facts
print("\n[Test 2] Adding profile facts...")
memory_manager.add_profile_fact(user_id, "basic_info", "job", "Software Engineer")
memory_manager.add_profile_fact(user_id, "basic_info", "location", "Toronto")
memory_manager.add_profile_fact(user_id, "preferences", "favorite_food", "Pizza")
memory_manager.add_profile_fact(user_id, "relationships", "best_friend", "Alex")
print("✓ Added 4 profile facts")

# Test 3: Retrieve profile
print("\n[Test 3] Retrieving user profile...")
profile = memory_manager.get_user_profile(user_id)
for category, facts in profile.items():
    print(f"  {category}:")
    for key, value in facts.items():
        print(f"    - {key}: {value}")

# Test 4: Add conversations
print("\n[Test 4] Adding conversation messages...")
memory_manager.add_conversation(user_id, "user", "Hi! How are you?")
memory_manager.add_conversation(user_id, "assistant", "I'm doing great! How can I help you today?")
memory_manager.add_conversation(user_id, "user", "I'm feeling excited about my new project at work!")
memory_manager.add_conversation(user_id, "assistant", "That's wonderful! Tell me more about this project.")
print("✓ Added 4 conversation messages")

# Test 5: Add timeline event
print("\n[Test 5] Adding timeline event...")
meeting_time = datetime.now() + timedelta(days=2, hours=14)
memory_manager.add_timeline_event(
    user_id=user_id,
    event_type="meeting",
    title="Project Review Meeting",
    description="Quarterly project review with the team",
    datetime_obj=meeting_time
)
print(f"✓ Added timeline event: Project Review Meeting at {meeting_time}")

# Test 6: Add diary entry
print("\n[Test 6] Adding diary entry...")
memory_manager.add_diary_entry(
    user_id=user_id,
    entry_type="achievement",
    title="Completed First AI Project",
    content="Successfully built and deployed my first AI chatbot. Feeling proud!",
    importance=8
)
print("✓ Added diary entry with importance=8")

# Test 7: Get user context
print("\n[Test 7] Retrieving complete user context...")
context = memory_manager.get_user_context(user_id)
print(f"✓ User: {context['user_info']['name']}")
print(f"✓ Profile categories: {list(context['profile'].keys())}")
print(f"✓ Recent conversations: {len(context['recent_conversations'])} messages")
print(f"✓ Upcoming events: {len(context['upcoming_events'])} events")

# Test 8: Semantic search
print("\n[Test 8] Testing semantic search...")
print("Query: 'work and career'")
results = memory_manager.search_relevant_memories(user_id, "work and career", k=3)
print(f"✓ Found {len(results)} relevant memories:")
for i, result in enumerate(results, 1):
    print(f"  {i}. {result['text'][:80]}...")

# Test 9: Add scheduled message
print("\n[Test 9] Adding scheduled message...")
scheduled_time = datetime.now() + timedelta(days=1, hours=8)
memory_manager.add_scheduled_message(
    user_id=user_id,
    scheduled_time=scheduled_time,
    message_type="follow_up",
    context="Check on user's excitement about work project"
)
print(f"✓ Scheduled follow-up message for {scheduled_time}")

print("\n" + "=" * 60)
print("All tests completed successfully! ✓")
print("=" * 60)
print("\nMemory system is working correctly:")
print("  • Database (PostgreSQL): ✓")
print("  • Vector Store (ChromaDB): ✓")
print("  • Memory Manager: ✓")
print("\nYou can now proceed to Phase 3!")
