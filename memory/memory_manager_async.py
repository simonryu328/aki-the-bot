"""
Async Memory Manager - Unified interface for all memory operations.
Production-grade implementation combining database (structured data) and vector store (semantic search).
"""

from typing import Dict, List, Optional, Any
from datetime import datetime

import pytz

from config.settings import settings
from memory.database_async import db
from memory.vector_store import vector_store
from core import get_logger, MemoryException, UserNotFoundError
from schemas import (
    UserSchema,
    UserCreateSchema,
    ProfileFactSchema,
    ConversationSchema,
    TimelineEventSchema,
    DiaryEntrySchema,
    ScheduledMessageSchema,
    UserContextSchema,
)

logger = get_logger(__name__)


class AsyncMemoryManager:
    """
    Unified async memory interface for the AI Companion.

    Features:
    - Type-safe operations with Pydantic schemas
    - Graceful degradation when vector store unavailable
    - Comprehensive error handling and logging
    - Async/await for high performance

    Manages both:
    - Structured data (PostgreSQL via async SQLAlchemy)
    - Semantic search (Pinecone vector store)
    """

    def __init__(self):
        """Initialize memory manager with database and optional vector store."""
        self.db = db
        self.vector_store = vector_store
        self.vector_store_available = vector_store is not None

        if self.vector_store_available:
            logger.info("Memory manager initialized with vector store")
        else:
            logger.warning("Memory manager initialized without vector store")

    # ==================== User Management ====================

    async def get_or_create_user(
        self, telegram_id: int, name: Optional[str] = None, username: Optional[str] = None
    ) -> UserSchema:
        """
        Get or create user, returns UserSchema.

        Args:
            telegram_id: Telegram user ID
            name: User's display name
            username: User's Telegram username

        Returns:
            UserSchema with user data

        Raises:
            MemoryException: If operation fails
        """
        try:
            user = await self.db.get_or_create_user(telegram_id, name, username)
            logger.debug("User retrieved/created", user_id=user.id, telegram_id=telegram_id)
            return user
        except Exception as e:
            logger.error("Failed to get/create user", telegram_id=telegram_id, error=str(e))
            raise MemoryException(f"Failed to get/create user: {e}")

    async def get_user_by_id(self, user_id: int) -> Optional[UserSchema]:
        """
        Get user by internal ID.

        Args:
            user_id: Internal user ID

        Returns:
            UserSchema if found, None otherwise
        """
        return await self.db.get_user_by_id(user_id)

    # ==================== Context Retrieval ====================

    async def get_user_context(self, user_id: int) -> UserContextSchema:
        """
        Get complete user context for AI interaction.
        This is the main method used by conversational agents.

        Args:
            user_id: User ID

        Returns:
            UserContextSchema with all relevant context

        Raises:
            UserNotFoundError: If user doesn't exist
            MemoryException: If context retrieval fails
        """
        try:
            user = await self.db.get_user_by_id(user_id)
            if not user:
                logger.warning("User not found", user_id=user_id)
                raise UserNotFoundError(user_id)

            # Fetch all context data in parallel
            profile = await self.db.get_user_profile(user_id)
            conversations = await self.db.get_recent_conversations(user_id, limit=10)
            events = await self.db.get_upcoming_events(user_id, days=7)

            context = UserContextSchema(
                user_info=user,
                profile=profile,
                recent_conversations=conversations,
                upcoming_events=events,
            )

            logger.debug(
                "Retrieved user context",
                user_id=user_id,
                conversation_count=len(conversations),
                event_count=len(events),
            )
            return context

        except UserNotFoundError:
            raise
        except Exception as e:
            logger.error("Failed to get user context", user_id=user_id, error=str(e))
            raise MemoryException(f"Failed to get user context: {e}")

    async def search_relevant_memories(
        self, user_id: int, query: str, k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant memories using semantic similarity.

        Args:
            user_id: User ID
            query: Search query
            k: Number of results

        Returns:
            List of relevant memory dicts
        """
        if not self.vector_store_available:
            logger.debug("Vector store not available, returning empty results")
            return []

        try:
            memories = self.vector_store.search_memories(user_id, query, k=k)
            logger.debug("Searched memories", user_id=user_id, query_length=len(query), results=len(memories))
            return memories
        except Exception as e:
            logger.error("Failed to search memories", user_id=user_id, error=str(e))
            return []  # Return empty list on error rather than failing

    # ==================== Conversation Storage ====================

    async def add_conversation(
        self, user_id: int, role: str, message: str, store_in_vector: bool = True, thinking: Optional[str] = None
    ) -> ConversationSchema:
        """
        Add a conversation message.
        Stores in both database and vector store.

        Args:
            user_id: User ID
            role: "user" or "assistant"
            message: Message content
            store_in_vector: Whether to also store in vector store for semantic search

        Returns:
            ConversationSchema with stored conversation

        Raises:
            MemoryException: If storage fails
        """
        try:
            # Store in database
            conversation = await self.db.add_conversation(user_id, role, message, thinking=thinking)

            # Store in vector store for semantic search
            if store_in_vector and self.vector_store_available:
                try:
                    self.vector_store.add_memory(
                        user_id=user_id,
                        text=f"{role}: {message}",
                        metadata={
                            "message_type": "single_message",
                            "role": role,
                        },
                    )
                except Exception as e:
                    logger.warning("Failed to store in vector store", user_id=user_id, error=str(e))
                    # Don't fail the whole operation if vector store fails

            logger.debug("Added conversation", user_id=user_id, role=role, message_length=len(message))
            return conversation

        except Exception as e:
            logger.error("Failed to add conversation", user_id=user_id, error=str(e))
            raise MemoryException(f"Failed to add conversation: {e}")

    def add_conversation_chunk(
        self, user_id: int, messages: List[Dict[str, str]], importance: int = 5
    ) -> Optional[str]:
        """
        Add a multi-turn conversation chunk to vector store.
        Useful for storing context-rich conversation segments.

        Args:
            user_id: User ID
            messages: List of message dicts with 'role' and 'content'
            importance: Importance score (0-10)

        Returns:
            Memory ID if successful, None otherwise
        """
        if not self.vector_store_available:
            logger.debug("Vector store not available, skipping conversation chunk")
            return None

        try:
            memory_id = self.vector_store.add_conversation_chunk(user_id, messages, importance)
            logger.debug("Added conversation chunk", user_id=user_id, message_count=len(messages))
            return memory_id
        except Exception as e:
            logger.error("Failed to add conversation chunk", user_id=user_id, error=str(e))
            return None

    # ==================== Profile Management ====================

    async def add_profile_fact(
        self,
        user_id: int,
        category: str,
        key: str,
        value: str,
        confidence: float = 1.0,
    ) -> ProfileFactSchema:
        """
        Add or update a profile fact.

        Args:
            user_id: User ID
            category: Fact category (e.g., "basic_info", "preferences", "relationships")
            key: Fact key (e.g., "job", "location", "favorite_food")
            value: Fact value
            confidence: Confidence score (0.0 to 1.0)

        Returns:
            ProfileFactSchema with stored fact

        Raises:
            MemoryException: If storage fails
        """
        try:
            fact = await self.db.add_profile_fact(user_id, category, key, value, confidence)

            # Also store in vector store for semantic search
            if self.vector_store_available:
                try:
                    self.vector_store.add_memory(
                        user_id=user_id,
                        text=f"{key}: {value}",
                        metadata={
                            "message_type": "profile_fact",
                            "category": category,
                            "key": key,
                        },
                    )
                except Exception as e:
                    logger.warning("Failed to store fact in vector store", error=str(e))

            logger.info("Added profile fact", user_id=user_id, category=category, key=key)
            return fact

        except Exception as e:
            logger.error("Failed to add profile fact", user_id=user_id, error=str(e))
            raise MemoryException(f"Failed to add profile fact: {e}")

    async def get_user_profile(self, user_id: int) -> Dict[str, Dict[str, str]]:
        """
        Get all profile facts for a user, organized by category.

        Args:
            user_id: User ID

        Returns:
            Dict of {category: {key: value}}
        """
        return await self.db.get_user_profile(user_id)

    async def get_recent_observations(
        self, user_id: int, days: int = 7
    ) -> List[ProfileFactSchema]:
        """
        Get recent observations for a user with timestamps.

        Args:
            user_id: User ID
            days: Number of days to look back (default 7)

        Returns:
            List of ProfileFactSchema with observed_at timestamps
        """
        return await self.db.get_recent_observations(user_id, days)

    async def get_observations_with_dates(
        self, user_id: int, limit: int = 100
    ) -> List[str]:
        """
        Get observations formatted with dates for diary/summary generation.

        Args:
            user_id: User ID
            limit: Maximum observations to return

        Returns:
            List of strings like "[2026-02-05] emotions: He's been struggling..."
        """
        observations = await self.db.get_all_observations(user_id, limit)
        tz = pytz.timezone(settings.TIMEZONE)
        formatted = []
        for obs in observations:
            utc_time = obs.observed_at.replace(tzinfo=pytz.utc)
            local_time = utc_time.astimezone(tz)
            date_str = local_time.strftime("%Y-%m-%d")
            formatted.append(f"[{date_str}] {obs.category}: {obs.value}")
        return formatted

    # ==================== Timeline Events ====================

    async def add_timeline_event(
        self,
        user_id: int,
        event_type: str,
        title: str,
        description: Optional[str],
        datetime_obj: datetime,
    ) -> TimelineEventSchema:
        """
        Add a timeline event.

        Args:
            user_id: User ID
            event_type: Type of event (e.g., "meeting", "appointment", "deadline")
            title: Event title
            description: Event description
            datetime_obj: Event datetime

        Returns:
            TimelineEventSchema with stored event

        Raises:
            MemoryException: If storage fails
        """
        try:
            event = await self.db.add_timeline_event(
                user_id, event_type, title, description, datetime_obj
            )

            # Also store in vector store
            if self.vector_store_available:
                event_text = f"Event: {title}. {description or ''} Scheduled for {datetime_obj.isoformat()}"
                try:
                    self.vector_store.add_memory(
                        user_id=user_id,
                        text=event_text,
                        metadata={
                            "message_type": "timeline_event",
                            "event_type": event_type,
                            "datetime": datetime_obj.isoformat(),
                        },
                    )
                except Exception as e:
                    logger.warning("Failed to store event in vector store", error=str(e))

            logger.info("Added timeline event", user_id=user_id, title=title)
            return event

        except Exception as e:
            logger.error("Failed to add timeline event", user_id=user_id, error=str(e))
            raise MemoryException(f"Failed to add timeline event: {e}")

    async def get_upcoming_events(
        self, user_id: int, days: int = 7
    ) -> List[TimelineEventSchema]:
        """
        Get upcoming events for a user.

        Args:
            user_id: User ID
            days: Number of days to look ahead

        Returns:
            List of TimelineEventSchema
        """
        return await self.db.get_upcoming_events(user_id, days)

    # ==================== Diary Entries ====================

    async def add_diary_entry(
        self,
        user_id: int,
        entry_type: str,
        title: str,
        content: str,
        importance: int,
        image_url: Optional[str] = None,
        exchange_start: Optional[datetime] = None,
        exchange_end: Optional[datetime] = None,
    ) -> DiaryEntrySchema:
        """
        Add a diary entry (milestone moment).

        Args:
            user_id: User ID
            entry_type: Type of entry (e.g., "achievement", "milestone", "visual_memory", "compact_summary")
            title: Entry title
            content: Entry content
            importance: Importance score (0-10)
            image_url: Path to associated image
            exchange_start: For compact_summary: when conversation exchange began
            exchange_end: For compact_summary: when conversation exchange ended

        Returns:
            DiaryEntrySchema with stored entry

        Raises:
            MemoryException: If storage fails
        """
        try:
            entry = await self.db.add_diary_entry(
                user_id, entry_type, title, content, importance, image_url, exchange_start, exchange_end
            )

            # Store in vector store
            if self.vector_store_available:
                diary_text = f"Milestone: {title}. {content}"
                try:
                    self.vector_store.add_memory(
                        user_id=user_id,
                        text=diary_text,
                        metadata={
                            "message_type": "diary_entry",
                            "entry_type": entry_type,
                            "importance": importance,
                        },
                    )
                except Exception as e:
                    logger.warning("Failed to store diary entry in vector store", error=str(e))

            logger.info("Added diary entry", user_id=user_id, title=title, importance=importance)
            return entry

        except Exception as e:
            logger.error("Failed to add diary entry", user_id=user_id, error=str(e))
            raise MemoryException(f"Failed to add diary entry: {e}")

    async def get_diary_entries(
        self, user_id: int, limit: int = 50
    ) -> List[DiaryEntrySchema]:
        """
        Get recent diary entries for a user.

        Args:
            user_id: User ID
            limit: Maximum number of entries to return

        Returns:
            List of DiaryEntrySchema
        """
        return await self.db.get_diary_entries(user_id, limit)

    # ==================== Scheduled Messages ====================

    async def add_scheduled_message(
        self,
        user_id: int,
        scheduled_time: datetime,
        message_type: str,
        context: Optional[str] = None,
        message: Optional[str] = None,
    ) -> ScheduledMessageSchema:
        """
        Add a scheduled message to the intent queue.

        Args:
            user_id: User ID
            scheduled_time: When to send the message
            message_type: Type of message (e.g., "follow_up", "goal_check", "event_reminder")
            context: Context for generating the message
            message: Pre-generated message (optional)

        Returns:
            ScheduledMessageSchema with stored message

        Raises:
            MemoryException: If storage fails
        """
        try:
            scheduled_msg = await self.db.add_scheduled_message(
                user_id, scheduled_time, message_type, context, message
            )
            logger.info("Scheduled message", user_id=user_id, scheduled_time=scheduled_time.isoformat())
            return scheduled_msg

        except Exception as e:
            logger.error("Failed to add scheduled message", user_id=user_id, error=str(e))
            raise MemoryException(f"Failed to add scheduled message: {e}")

    async def get_pending_scheduled_messages(self) -> List[ScheduledMessageSchema]:
        """
        Get all pending scheduled messages that are due.

        Returns:
            List of ScheduledMessageSchema
        """
        return await self.db.get_pending_scheduled_messages()

    async def get_user_scheduled_messages(
        self, user_id: int, include_executed: bool = False
    ) -> List[ScheduledMessageSchema]:
        """
        Get all scheduled messages for a user (including future ones).

        Args:
            user_id: User ID
            include_executed: Whether to include already executed messages

        Returns:
            List of ScheduledMessageSchema
        """
        return await self.db.get_user_scheduled_messages(user_id, include_executed)

    async def clear_scheduled_messages(self, user_id: int) -> int:
        """
        Delete all pending scheduled messages for a user.

        Args:
            user_id: User ID

        Returns:
            Number of messages deleted
        """
        return await self.db.clear_scheduled_messages(user_id)

    async def mark_message_executed(self, message_id: int) -> None:
        """
        Mark a scheduled message as executed.

        Args:
            message_id: Message ID to mark as executed
        """
        await self.db.mark_message_executed(message_id)
    # ==================== Reach-Out Management ====================

    async def get_all_users(self) -> List[UserSchema]:
        """
        Get all users for reach-out checking.

        Returns:
            List of all UserSchema objects
        """
        return await self.db.get_all_users()

    async def get_last_user_message(self, user_id: int) -> Optional[ConversationSchema]:
        """
        Get the last message FROM the user (not from bot).

        Args:
            user_id: User ID

        Returns:
            ConversationSchema of last user message, or None if no messages
        """
        conversations = await self.db.get_recent_conversations(user_id, limit=100)
        for conv in conversations:
            if conv.role == "user":
                return conv
        return None

    async def update_user_reach_out_timestamp(self, user_id: int, timestamp: datetime) -> None:
        """
        Update the last_reach_out_at timestamp for a user.

        Args:
            user_id: User ID
            timestamp: Timestamp of reach-out
        """
        await self.db.update_user_reach_out_timestamp(user_id, timestamp)

    async def update_user_reach_out_config(
        self,
        user_id: int,
        enabled: Optional[bool] = None,
        min_silence_hours: Optional[int] = None,
        max_silence_days: Optional[int] = None,
    ) -> None:
        """
        Update reach-out configuration for a user.

        Args:
            user_id: User ID
            enabled: Whether reach-outs are enabled
            min_silence_hours: Minimum hours before reach-out
            max_silence_days: Maximum days to keep trying
        """
        await self.db.update_user_reach_out_config(
            user_id, enabled, min_silence_hours, max_silence_days
        )



# Singleton instance
memory_manager = AsyncMemoryManager()
