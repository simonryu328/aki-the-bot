"""
Async database operations for the AI Companion memory system.
Production-grade implementation with async SQLAlchemy, proper error handling, and type safety.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import List, Optional, AsyncIterator, Dict, Any

import pytz

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine,
)
from sqlalchemy import select, desc, func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from config.settings import settings
from core import get_logger, DatabaseException, RecordNotFoundError, DuplicateRecordError
from memory.models import (
    Base,
    User,
    Conversation,
    DiaryEntry,
    TokenUsage,
)
from schemas import (
    UserSchema,
    UserCreateSchema,
    ConversationSchema,
    ConversationCreateSchema,
    DiaryEntrySchema,
    DiaryEntryCreateSchema,
    TokenUsageSchema,
)

logger = get_logger(__name__)


class AsyncDatabase:
    """
    Async database interface with production-grade features:
    - Connection pooling and retry logic
    - Type-safe operations with Pydantic
    - Proper error handling and logging
    - Transaction management
    """

    def __init__(self):
        """Initialize async database engine and session factory."""
        # Convert postgresql:// to postgresql+asyncpg://
        db_url = settings.DATABASE_URL
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

        self.engine: AsyncEngine = create_async_engine(
            db_url,
            echo=settings.LOG_LEVEL == "DEBUG",
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,  # Verify connections before use
            pool_recycle=3600,  # Recycle connections after 1 hour
        )

        self.async_session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        logger.info("Async database engine initialized", db_url=db_url.split("@")[-1])

    @asynccontextmanager
    async def get_session(self) -> AsyncIterator[AsyncSession]:
        """
        Context manager for database sessions with automatic cleanup.

        Yields:
            AsyncSession instance
        """
        async with self.async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error("Session rolled back", error=str(e))
                raise
            finally:
                await session.close()

    async def create_tables(self) -> None:
        """Create all database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")

    async def drop_tables(self) -> None:
        """Drop all database tables (use with caution)."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.warning("Database tables dropped")

    # ==================== User Operations ====================

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(SQLAlchemyError),
    )
    async def get_or_create_user(
        self, telegram_id: int, name: Optional[str] = None, username: Optional[str] = None
    ) -> UserSchema:
        """
        Get existing user or create new one.

        Args:
            telegram_id: Telegram user ID
            name: User's display name
            username: Telegram username

        Returns:
            UserSchema with user data

        Raises:
            DatabaseException: If database operation fails
        """
        try:
            async with self.get_session() as session:
                # Try to find existing user
                result = await session.execute(
                    select(User).where(User.telegram_id == telegram_id)
                )
                user = result.scalar_one_or_none()

                if user:
                    # Update last interaction and optional fields
                    user.last_interaction = datetime.utcnow()
                    if name:
                        user.name = name
                    if username:
                        user.username = username
                    session.add(user)
                    logger.debug("Retrieved existing user", user_id=user.id, telegram_id=telegram_id)
                else:
                    # Create new user
                    user = User(
                        telegram_id=telegram_id,
                        name=name,
                        username=username,
                        created_at=datetime.utcnow(),
                        last_interaction=datetime.utcnow(),
                    )
                    session.add(user)
                    await session.flush()  # Get the ID
                    logger.info("Created new user", user_id=user.id, telegram_id=telegram_id)

                return UserSchema.model_validate(user)

        except SQLAlchemyError as e:
            logger.error("Failed to get/create user", telegram_id=telegram_id, error=str(e))
            raise DatabaseException(f"Failed to get/create user: {e}")

    async def get_user_by_id(self, user_id: int) -> Optional[UserSchema]:
        """Get user by internal ID."""
        try:
            async with self.get_session() as session:
                result = await session.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()
                return UserSchema.model_validate(user) if user else None

        except SQLAlchemyError as e:
            logger.error("Failed to get user", user_id=user_id, error=str(e))
            raise DatabaseException(f"Failed to get user: {e}")

    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[UserSchema]:
        """Get user by Telegram ID."""
        try:
            async with self.get_session() as session:
                result = await session.execute(select(User).where(User.telegram_id == telegram_id))
                user = result.scalar_one_or_none()
                return UserSchema.model_validate(user) if user else None

        except SQLAlchemyError as e:
            logger.error("Failed to get user", telegram_id=telegram_id, error=str(e))
            raise DatabaseException(f"Failed to get user: {e}")

    async def update_user_onboarding_state(
        self, telegram_id: int, onboarding_state: Optional[str]
    ) -> Optional[UserSchema]:
        """
        Update user's onboarding state.

        Args:
            telegram_id: Telegram user ID
            onboarding_state: New onboarding state (None means completed)

        Returns:
            Updated UserSchema or None if user not found

        Raises:
            DatabaseException: If database operation fails
        """
        try:
            async with self.get_session() as session:
                result = await session.execute(
                    select(User).where(User.telegram_id == telegram_id)
                )
                user = result.scalar_one_or_none()

                if user:
                    user.onboarding_state = onboarding_state
                    session.add(user)
                    logger.debug(
                        "Updated user onboarding state",
                        telegram_id=telegram_id,
                        state=onboarding_state,
                    )
                    return UserSchema.model_validate(user)
                return None

        except SQLAlchemyError as e:
            logger.error(
                "Failed to update onboarding state", telegram_id=telegram_id, error=str(e)
            )
            raise DatabaseException(f"Failed to update onboarding state: {e}")

    async def create_user_with_state(
        self,
        telegram_id: int,
        name: Optional[str] = None,
        username: Optional[str] = None,
        onboarding_state: str = "awaiting_name",
    ) -> UserSchema:
        """
        Create a new user with specific onboarding state.

        Args:
            telegram_id: Telegram user ID
            name: User's display name
            username: Telegram username
            onboarding_state: Initial onboarding state

        Returns:
            UserSchema with user data

        Raises:
            DatabaseException: If database operation fails
        """
        try:
            async with self.get_session() as session:
                user = User(
                    telegram_id=telegram_id,
                    name=name,
                    username=username,
                    onboarding_state=onboarding_state,
                    created_at=datetime.utcnow(),
                    last_interaction=datetime.utcnow(),
                )
                session.add(user)
                await session.flush()  # Get the ID
                logger.info(
                    "Created new user with onboarding state",
                    user_id=user.id,
                    telegram_id=telegram_id,
                    state=onboarding_state,
                )
                return UserSchema.model_validate(user)

        except SQLAlchemyError as e:
            logger.error("Failed to create user", telegram_id=telegram_id, error=str(e))
            raise DatabaseException(f"Failed to create user: {e}")

    # ==================== Conversation Operations ====================

    async def add_conversation(
        self, user_id: int, role: str, message: str, thinking: Optional[str] = None
    ) -> ConversationSchema:
        """Add a conversation message."""
        try:
            async with self.get_session() as session:
                conversation = Conversation(
                    user_id=user_id,
                    role=role,
                    message=message,
                    thinking=thinking,
                    timestamp=datetime.utcnow(),
                )
                session.add(conversation)
                await session.flush()
                return ConversationSchema.model_validate(conversation)

        except SQLAlchemyError as e:
            logger.error("Failed to add conversation", user_id=user_id, error=str(e))
            raise DatabaseException(f"Failed to add conversation: {e}")

    async def get_recent_conversations(
        self, user_id: int, limit: int = 10
    ) -> List[ConversationSchema]:
        """Get recent conversation messages for a user."""
        try:
            async with self.get_session() as session:
                result = await session.execute(
                    select(Conversation)
                    .where(Conversation.user_id == user_id)
                    .order_by(desc(Conversation.timestamp))
                    .limit(limit)
                )
                conversations = result.scalars().all()
                # Reverse to get chronological order
                return [ConversationSchema.model_validate(c) for c in reversed(conversations)]

        except SQLAlchemyError as e:
            logger.error("Failed to get conversations", user_id=user_id, error=str(e))
            raise DatabaseException(f"Failed to get conversations: {e}")

    async def get_conversations_after(
        self, user_id: int, after: datetime, limit: int = 20
    ) -> List[ConversationSchema]:
        """Get conversation messages after a specific timestamp.
        
        Args:
            user_id: User ID
            after: Get conversations after this timestamp
            limit: Maximum number of conversations to return
            
        Returns:
            List of conversations in chronological order
        """
        try:
            async with self.get_session() as session:
                # Get most recent messages first (desc), then reverse to chronological order
                result = await session.execute(
                    select(Conversation)
                    .where(
                        Conversation.user_id == user_id,
                        Conversation.timestamp > after
                    )
                    .order_by(Conversation.timestamp.desc())
                    .limit(limit)
                )
                conversations = result.scalars().all()
                # Reverse to get chronological order (oldest to newest)
                return [ConversationSchema.model_validate(c) for c in reversed(conversations)]

        except SQLAlchemyError as e:
            logger.error("Failed to get conversations after timestamp",
                        user_id=user_id, after=after, error=str(e))
            raise DatabaseException(f"Failed to get conversations: {e}")

    # ==================== Diary Entry Operations ====================

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
        """Add a diary entry."""
        try:
            async with self.get_session() as session:
                entry = DiaryEntry(
                    user_id=user_id,
                    entry_type=entry_type,
                    title=title,
                    content=content,
                    importance=importance,
                    image_url=image_url,
                    timestamp=datetime.utcnow(),
                    exchange_start=exchange_start,
                    exchange_end=exchange_end,
                )
                session.add(entry)
                await session.flush()
                logger.debug("Added diary entry", user_id=user_id, type=entry_type, title=title)
                return DiaryEntrySchema.model_validate(entry)

        except SQLAlchemyError as e:
            logger.error("Failed to add diary entry", user_id=user_id, error=str(e))
            raise DatabaseException(f"Failed to add diary entry: {e}")

    async def update_diary_entry(
        self,
        entry_id: int,
        title: Optional[str] = None,
        content: Optional[str] = None,
    ) -> DiaryEntrySchema:
        """Update an existing diary entry."""
        try:
            async with self.get_session() as session:
                result = await session.execute(select(DiaryEntry).where(DiaryEntry.id == entry_id))
                entry = result.scalar_one_or_none()
                if not entry:
                    raise RecordNotFoundError(f"Diary entry {entry_id} not found")
                
                if title is not None:
                    entry.title = title
                if content is not None:
                    entry.content = content
                
                session.add(entry)
                await session.flush()
                logger.debug("Updated diary entry", entry_id=entry_id, title=title)
                return DiaryEntrySchema.model_validate(entry)

        except SQLAlchemyError as e:
            logger.error("Failed to update diary entry", entry_id=entry_id, error=str(e))
            raise DatabaseException(f"Failed to update diary entry: {e}")

    async def get_diary_entries(
        self, user_id: int, limit: int = 5, entry_type: Optional[str] = None
    ) -> List[DiaryEntrySchema]:
        """Get recent diary entries for a user."""
        try:
            async with self.get_session() as session:
                query = select(DiaryEntry).where(DiaryEntry.user_id == user_id)
                if entry_type:
                    query = query.where(DiaryEntry.entry_type == entry_type)
                
                query = query.order_by(desc(DiaryEntry.timestamp)).limit(limit)
                result = await session.execute(query)
                entries = result.scalars().all()
                return [DiaryEntrySchema.model_validate(e) for e in entries]

        except SQLAlchemyError as e:
            logger.error("Failed to get diary entries", user_id=user_id, error=str(e))
            raise DatabaseException(f"Failed to get diary entries: {e}")

    # ==================== Reach-Out Management ====================

    async def get_all_users(self) -> List[UserSchema]:
        """Get all users (for reach-out checker or admin scripts)."""
        try:
            async with self.get_session() as session:
                result = await session.execute(select(User))
                users = result.scalars().all()
                return [UserSchema.model_validate(u) for u in users]
        except SQLAlchemyError as e:
            logger.error("Failed to get all users", error=str(e))
            raise DatabaseException(f"Failed to get all users: {e}")

    async def get_users_for_reach_out(self, min_silence_hours: int = 6) -> List[UserSchema]:
        """
        Get users who are eligible for a reach-out message.
        Filters:
        - reach_out_enabled is True
        - onboarding_state is NULL (onboarding complete)
        - last_interaction is older than min_silence_hours
        - last_reach_out_at is NULL or older than certain threshold (cooldown)
        """
        try:
            now = datetime.utcnow()
            cutoff = now - timedelta(hours=min_silence_hours)
            
            async with self.get_session() as session:
                # Basic reach-out logic: enabled, onboarded, and silent
                result = await session.execute(
                    select(User).where(
                        User.reach_out_enabled == True,
                        User.onboarding_state == None,
                        User.last_interaction < cutoff,
                        # Also check if we haven't reached out recently (e.g., in the last 24h)
                        (User.last_reach_out_at == None) | (User.last_reach_out_at < (now - timedelta(hours=24)))
                    )
                )
                users = result.scalars().all()
                logger.debug("Found eligible users for reach-out", count=len(users))
                return [UserSchema.model_validate(u) for u in users]

        except SQLAlchemyError as e:
            logger.error("Failed to get users for reach-out", error=str(e))
            raise DatabaseException(f"Failed to get users for reach-out: {e}")

    async def update_user_reach_out_timestamp(self, user_id: int, timestamp: datetime) -> None:
        """Update the last_reach_out_at timestamp for a user."""
        try:
            # Convert to naive UTC if it's aware
            if timestamp.tzinfo:
                timestamp = timestamp.astimezone(pytz.UTC).replace(tzinfo=None)
                
            async with self.get_session() as session:
                result = await session.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()
                if user:
                    user.last_reach_out_at = timestamp
                    session.add(user)
                    logger.debug("Updated last_reach_out_at", user_id=user_id, ts=timestamp)

        except SQLAlchemyError as e:
            logger.error("Failed to update reach-out timestamp", user_id=user_id, error=str(e))
            raise DatabaseException(f"Failed to update reach-out timestamp: {e}")

    async def update_user_reach_out_config(
        self,
        user_id: int,
        enabled: Optional[bool] = None,
        min_silence_hours: Optional[int] = None,
        max_silence_days: Optional[int] = None,
    ) -> None:
        """Update a user's reach-out configuration."""
        try:
            async with self.get_session() as session:
                result = await session.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()
                if user:
                    if enabled is not None:
                        user.reach_out_enabled = enabled
                    if min_silence_hours is not None:
                        user.reach_out_min_silence_hours = min_silence_hours
                    if max_silence_days is not None:
                        user.reach_out_max_silence_days = max_silence_days
                    session.add(user)
                    logger.info("Updated reach-out config", user_id=user_id)

        except SQLAlchemyError as e:
            logger.error("Failed to update reach-out config", user_id=user_id, error=str(e))
            raise DatabaseException(f"Failed to update reach-out config: {e}")

    async def update_user_last_interaction(self, user_id: int) -> None:
        """Update last_interaction timestamp to now."""
        try:
            async with self.get_session() as session:
                result = await session.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()
                if user:
                    user.last_interaction = datetime.utcnow()
                    session.add(user)
                    logger.debug("Updated last_interaction", user_id=user_id)

        except SQLAlchemyError as e:
            logger.error("Failed to update last_interaction", user_id=user_id, error=str(e))
            raise DatabaseException(f"Failed to update last interaction: {e}")

    async def update_user_profile(
        self,
        user_id: int,
        name: Optional[str] = None,
        timezone: Optional[str] = None,
    ) -> UserSchema:
        """Update generic user profile fields."""
        try:
            async with self.get_session() as session:
                result = await session.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()
                if not user:
                    raise RecordNotFoundError(f"User {user_id} not found")
                
                if name:
                    user.name = name
                if timezone:
                    user.timezone = timezone
                
                session.add(user)
                await session.flush()
                return UserSchema.model_validate(user)

        except SQLAlchemyError as e:
            logger.error("Failed to update user profile", user_id=user_id, error=str(e))
            raise DatabaseException(f"Failed to update user profile: {e}")

    # ==================== Token Usage Operations ====================

    async def record_token_usage(
        self,
        user_id: int,
        model: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        call_type: str = "conversation",
    ) -> TokenUsageSchema:
        """Record an LLM token usage event."""
        try:
            async with self.get_session() as session:
                usage = TokenUsage(
                    user_id=user_id,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    call_type=call_type,
                    timestamp=datetime.utcnow(),
                )
                session.add(usage)
                await session.flush()
                return TokenUsageSchema.model_validate(usage)

        except SQLAlchemyError as e:
            logger.error("Failed to record usage", user_id=user_id, error=str(e))
            raise DatabaseException(f"Failed to record token usage: {e}")

    async def get_user_token_usage_today(self, user_id: int) -> int:
        """
        Get total tokens used by a user today (UTC).
        
        Args:
            user_id: User ID
            
        Returns:
            Total tokens used today as integer
        """
        try:
            cutoff = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            async with self.get_session() as session:
                stmt = select(func.sum(TokenUsage.total_tokens)).where(
                    TokenUsage.user_id == user_id,
                    TokenUsage.timestamp >= cutoff
                )
                result = await session.execute(stmt)
                res = result.scalar()
                return int(res) if res else 0
        except SQLAlchemyError as e:
            logger.error("Failed to get token usage", user_id=user_id, error=str(e))
            return 0

    async def get_user_token_usage(
        self, user_id: int, days: int = 1
    ) -> Dict[str, int]:
        """
        Get total tokens used by a user in the last N days.
        Returns a breakdown by token type.
        """
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            async with self.get_session() as session:
                # Sum inputs, outputs, and total
                stmt = select(
                    func.sum(TokenUsage.input_tokens),
                    func.sum(TokenUsage.output_tokens),
                    func.sum(TokenUsage.total_tokens)
                ).where(
                    TokenUsage.user_id == user_id,
                    TokenUsage.timestamp >= cutoff
                )
                result = await session.execute(stmt)
                res = result.one()
                return {
                    "input_tokens": res[0] or 0,
                    "output_tokens": res[1] or 0,
                    "total_tokens": res[2] or 0,
                }
        except SQLAlchemyError as e:
            logger.error("Failed to get token usage", user_id=user_id, error=str(e))
            return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}


# Singleton instance
db = AsyncDatabase()
