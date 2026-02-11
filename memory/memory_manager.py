"""
Memory Manager - Unified interface for all memory operations.
Manages structured data storage (PostgreSQL).
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from memory.database import db

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Unified memory interface for the AI Companion.
    Manages structured data (PostgreSQL).
    """

    def __init__(self):
        """Initialize memory manager."""
        self.db = db

    # ==================== User Management ====================

    def get_or_create_user(
        self, telegram_id: int, name: Optional[str] = None, username: Optional[str] = None
    ) -> int:
        """
        Get or create user, returns user_id.

        Args:
            telegram_id: Telegram user ID
            name: User's display name
            username: User's Telegram username

        Returns:
            Internal user ID
        """
        return self.db.get_or_create_user(telegram_id, name, username)

    # ==================== Context Retrieval ====================

    def get_user_context(self, user_id: int) -> Dict[str, Any]:
        """
        Get complete user context for AI interaction.
        This is the main method used by conversational agents.

        Returns:
            Dict with:
                - profile: Dict of profile facts by category
                - recent_conversations: List of recent messages
                - upcoming_events: List of upcoming timeline events
                - user_info: Basic user information
        """
        user = self.db.get_user_by_id(user_id)
        if not user:
            logger.warning(f"User {user_id} not found")
            return {}

        profile = self.db.get_user_profile(user_id)
        conversations = self.db.get_recent_conversations(user_id, limit=10)
        events = self.db.get_upcoming_events(user_id, days=7)

        context = {
            "user_info": {
                "id": user["id"],
                "name": user["name"],
                "username": user["username"],
                "telegram_id": user["telegram_id"],
                "last_interaction": user["last_interaction"].isoformat() if user["last_interaction"] else None,
            },
            "profile": profile,
            "recent_conversations": [
                {
                    "role": conv.role,
                    "message": conv.message,
                    "timestamp": conv.timestamp.isoformat(),
                }
                for conv in conversations
            ],
            "upcoming_events": [
                {
                    "title": event.title,
                    "description": event.description,
                    "datetime": event.datetime.isoformat(),
                    "event_type": event.event_type,
                }
                for event in events
            ],
        }

        logger.debug(f"Retrieved context for user {user_id}")
        return context

    # ==================== Conversation Storage ====================

    def add_conversation(
        self, user_id: int, role: str, message: str
    ):
        """
        Add a conversation message.

        Args:
            user_id: User ID
            role: "user" or "assistant"
            message: Message content
        """
        # Store in database
        self.db.add_conversation(user_id, role, message)
        logger.debug(f"Stored conversation message for user {user_id}: {role}")

    # ==================== Profile Management ====================

    def add_profile_fact(
        self,
        user_id: int,
        category: str,
        key: str,
        value: str,
        confidence: float = 1.0,
    ):
        """
        Add or update a profile fact.

        Args:
            user_id: User ID
            category: Fact category (e.g., "basic_info", "preferences", "relationships")
            key: Fact key (e.g., "job", "location", "favorite_food")
            value: Fact value
            confidence: Confidence score (0.0 to 1.0)
        """
        self.db.add_profile_fact(user_id, category, key, value, confidence)
        logger.info(f"Added profile fact: {category}.{key} = {value} for user {user_id}")

    def get_user_profile(self, user_id: int) -> Dict[str, Dict[str, str]]:
        """Get all profile facts for a user, organized by category."""
        return self.db.get_user_profile(user_id)

    # ==================== Timeline Events ====================

    def add_timeline_event(
        self,
        user_id: int,
        event_type: str,
        title: str,
        description: Optional[str],
        datetime_obj: datetime,
    ):
        """
        Add a timeline event.

        Args:
            user_id: User ID
            event_type: Type of event (e.g., "meeting", "appointment", "deadline")
            title: Event title
            description: Event description
            datetime_obj: Event datetime
        """
        self.db.add_timeline_event(user_id, event_type, title, description, datetime_obj)
        logger.info(f"Added timeline event: {title} for user {user_id}")

    def get_upcoming_events(self, user_id: int, days: int = 7):
        """Get upcoming events for a user."""
        return self.db.get_upcoming_events(user_id, days)

    # ==================== Diary Entries ====================

    def add_diary_entry(
        self,
        user_id: int,
        entry_type: str,
        title: str,
        content: str,
        importance: int,
        image_url: Optional[str] = None,
    ):
        """
        Add a diary entry (milestone moment).

        Args:
            user_id: User ID
            entry_type: Type of entry (e.g., "achievement", "milestone", "visual_memory")
            title: Entry title
            content: Entry content
            importance: Importance score (0-10)
            image_url: Path to associated image
        """
        self.db.add_diary_entry(user_id, entry_type, title, content, importance, image_url)
        logger.info(f"Added diary entry: {title} (importance={importance}) for user {user_id}")

    def get_diary_entries(self, user_id: int, limit: int = 50):
        """Get recent diary entries for a user."""
        return self.db.get_diary_entries(user_id, limit)

    # ==================== Scheduled Messages ====================

    def add_scheduled_message(
        self,
        user_id: int,
        scheduled_time: datetime,
        message_type: str,
        context: Optional[str] = None,
        message: Optional[str] = None,
    ):
        """
        Add a scheduled message to the intent queue.

        Args:
            user_id: User ID
            scheduled_time: When to send the message
            message_type: Type of message (e.g., "follow_up", "goal_check", "event_reminder")
            context: Context for generating the message
            message: Pre-generated message (optional)
        """
        self.db.add_scheduled_message(
            user_id, scheduled_time, message_type, context, message
        )
        logger.info(f"Scheduled message for user {user_id} at {scheduled_time}")

    def get_pending_scheduled_messages(self):
        """Get all pending scheduled messages that are due."""
        return self.db.get_pending_scheduled_messages()

    def mark_message_executed(self, message_id: int):
        """Mark a scheduled message as executed."""
        self.db.mark_message_executed(message_id)


# Singleton instance
memory_manager = MemoryManager()
