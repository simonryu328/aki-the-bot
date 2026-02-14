"""
Async Memory Manager - Unified interface for all memory operations.

Copyright 2026 Simon Ryu. Licensed under Apache 2.0.

This module implements structured data storage using PostgreSQL with async SQLAlchemy.
Production-grade implementation with type-safe interface and comprehensive error handling.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime

import pytz

from config.settings import settings
from memory.database_async import db
from core import get_logger, MemoryException, UserNotFoundError
from schemas import (
    UserSchema,
    DiaryEntrySchema,
    DiaryEntryCreateSchema,
    ConversationSchema,
    TokenUsageSchema,
    UserContextSchema,
)

from cachetools import TTLCache

logger = get_logger(__name__)


class AsyncMemoryManager:
    """
    Unified async memory interface for the AI Companion.

    Features:
    - Type-safe operations with Pydantic schemas
    - Comprehensive error handling and logging
    - Async/await for high performance
    - In-memory TTL caching for hot data

    Manages structured data (PostgreSQL via async SQLAlchemy).
    """

    def __init__(self):
        """Initialize memory manager with database and caches."""
        self.db = db
        
        # In-memory caches (maxsize 100 users, various TTLs)
        self._user_cache = TTLCache(maxsize=100, ttl=300)     # 5 min
        
        logger.info("Memory manager initialized with TTL caching")

    # ==================== User Management ====================

    async def get_or_create_user(
        self, telegram_id: int, name: Optional[str] = None, username: Optional[str] = None
    ) -> UserSchema:
        """
        Get or create user, returns UserSchema.
        """
        try:
            user = await self.db.get_or_create_user(telegram_id, name, username)
            
            # Evict from cache to ensure fresh data if it was just created/updated
            if user.id in self._user_cache:
                del self._user_cache[user.id]
                
            logger.debug("User retrieved/created", user_id=user.id, telegram_id=telegram_id)
            return user
        except Exception as e:
            logger.error("Failed to get/create user", telegram_id=telegram_id, error=str(e))
            raise MemoryException(f"Failed to get/create user: {e}")

    async def get_user_by_id(self, user_id: int) -> Optional[UserSchema]:
        """
        Get user by internal ID with caching.
        """
        if user_id in self._user_cache:
            return self._user_cache[user_id]
            
        user = await self.db.get_user_by_id(user_id)
        if user:
            self._user_cache[user_id] = user
        return user

    # ==================== Context Retrieval ====================

    async def get_user_context(self, user_id: int) -> UserContextSchema:
        """
        Fetch full context for an interaction.
        Parallelizes fetching of different data types.
        """
        try:
            # Multi-fetch using gather for performance
            # Only user_info, conversations, and diary_entries are remaining
            import asyncio
            user_info, conversations, diary_entries = await asyncio.gather(
                self.db.get_user_by_id(user_id),
                self.db.get_recent_conversations(user_id, limit=settings.CONVERSATION_CONTEXT_LIMIT),
                self.db.get_diary_entries(user_id, limit=settings.DIARY_FETCH_LIMIT),
            )

            if not user_info:
                raise UserNotFoundError(user_id)

            # Organize diary entries (mostly compact summaries and visual memories)
            # Profile facts are now gone, we rely on memories/summaries

            context = UserContextSchema(
                user_info=user_info,
                profile={}, # Keeping empty for schema compatibility if needed, but will likely delete schema field later
                recent_conversations=conversations,
                upcoming_events=[], # Keeping empty for schema compatibility
                diary_entries=diary_entries,
            )

            logger.debug(
                "Retrieved user context",
                user_id=user_id,
                conversation_count=len(conversations),
                diary_entry_count=len(diary_entries),
            )
            return context

        except UserNotFoundError:
            raise
        except Exception as e:
            logger.error("Failed to get user context", user_id=user_id, error=str(e))
            raise MemoryException(f"Failed to get user context: {e}")

    # ==================== Conversation Storage ====================

    async def add_conversation(
        self, user_id: int, role: str, message: str, thinking: Optional[str] = None
    ) -> ConversationSchema:
        """
        Add a conversation message.

        Args:
            user_id: User ID
            role: "user" or "assistant"
            message: Message content
            thinking: Optional thinking/reasoning content

        Returns:
            ConversationSchema with stored conversation

        Raises:
            MemoryException: If storage fails
        """
        try:
            # Store in database
            conversation = await self.db.add_conversation(user_id, role, message, thinking=thinking)
            logger.debug("Added conversation", user_id=user_id, role=role, message_length=len(message))
            return conversation

        except Exception as e:
            logger.error("Failed to add conversation", user_id=user_id, error=str(e))
            raise MemoryException(f"Failed to add conversation: {e}")

    # ==================== Diary Entry Management ====================

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
            logger.info("Added diary entry", user_id=user_id, title=title, importance=importance)
            return entry

        except Exception as e:
            logger.error("Failed to add diary entry", user_id=user_id, error=str(e))
            raise MemoryException(f"Failed to add diary entry: {e}")

    async def get_diary_entries(
        self, user_id: int, limit: int = 50, entry_type: Optional[str] = None
    ) -> List[DiaryEntrySchema]:
        """
        Get recent diary entries for a user.

        Args:
            user_id: User ID
            limit: Maximum number of entries to return
            entry_type: Optional filter by entry type

        Returns:
            List of DiaryEntrySchema
        """
        return await self.db.get_diary_entries(user_id, limit, entry_type)

    # ==================== Reach-Out Management ====================

    async def get_all_users(self) -> List[UserSchema]:
        """
        Get all users for reach-out checking.

        Returns:
            List of all UserSchema objects
        """
        return await self.db.get_all_users()

    async def get_users_for_reach_out(self, min_silence_hours: int = 6) -> List[UserSchema]:
        """
        Get users eligible for reach-out, filtered in SQL.

        Args:
            min_silence_hours: Minimum hours since last reach-out

        Returns:
            List of eligible UserSchema objects
        """
        return await self.db.get_users_for_reach_out(min_silence_hours)

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

    # ==================== Token Usage Tracking ====================

    async def record_token_usage(
        self,
        user_id: int,
        model: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        call_type: str,
    ) -> None:
        """
        Record token usage for an LLM call.

        Args:
            user_id: User ID
            model: LLM model name
            input_tokens: Input/prompt token count
            output_tokens: Output/completion token count
            total_tokens: Total token count
            call_type: Type of call (conversation, compact, observation, proactive, reach_out)
        """
        await self.db.record_token_usage(
            user_id, model, input_tokens, output_tokens, total_tokens, call_type
        )

    async def get_user_token_usage_today(self, user_id: int) -> int:
        """
        Get total tokens used by a user today.

        Args:
            user_id: User ID

        Returns:
            Total tokens used today
        """
        return await self.db.get_user_token_usage_today(user_id)



# Singleton instance
memory_manager = AsyncMemoryManager()
