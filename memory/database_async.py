"""
Async database operations for the AI Companion memory system.
Production-grade implementation with async SQLAlchemy, proper error handling, and type safety.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import List, Optional, AsyncIterator, Dict, Any

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine,
)
from sqlalchemy import select, desc
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
    ProfileFact,
    TimelineEvent,
    DiaryEntry,
    Conversation,
    ScheduledMessage,
)
from schemas import (
    UserSchema,
    UserCreateSchema,
    ProfileFactSchema,
    ProfileFactCreateSchema,
    ConversationSchema,
    ConversationCreateSchema,
    TimelineEventSchema,
    TimelineEventCreateSchema,
    DiaryEntrySchema,
    DiaryEntryCreateSchema,
    ScheduledMessageSchema,
    ScheduledMessageCreateSchema,
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

    # ==================== Profile Facts ====================

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
            category: Fact category
            key: Fact key
            value: Fact value
            confidence: Confidence score (0.0 to 1.0)

        Returns:
            ProfileFactSchema

        Raises:
            DatabaseException: If database operation fails
        """
        try:
            async with self.get_session() as session:
                # Check if fact already exists
                result = await session.execute(
                    select(ProfileFact).where(
                        ProfileFact.user_id == user_id,
                        ProfileFact.category == category,
                        ProfileFact.key == key,
                    )
                )
                fact = result.scalar_one_or_none()

                if fact:
                    # Update existing fact
                    fact.value = value
                    fact.confidence = confidence
                    fact.updated_at = datetime.utcnow()
                else:
                    # Create new fact
                    fact = ProfileFact(
                        user_id=user_id,
                        category=category,
                        key=key,
                        value=value,
                        confidence=confidence,
                        updated_at=datetime.utcnow(),
                    )
                    session.add(fact)

                await session.flush()
                logger.debug("Added profile fact", user_id=user_id, category=category, key=key)
                return ProfileFactSchema.model_validate(fact)

        except SQLAlchemyError as e:
            logger.error("Failed to add profile fact", user_id=user_id, error=str(e))
            raise DatabaseException(f"Failed to add profile fact: {e}")

    async def get_user_profile(self, user_id: int) -> Dict[str, Dict[str, str]]:
        """
        Get all profile facts for a user, organized by category.

        Args:
            user_id: User ID

        Returns:
            Dict of {category: {key: value}}
        """
        try:
            async with self.get_session() as session:
                result = await session.execute(
                    select(ProfileFact).where(ProfileFact.user_id == user_id)
                )
                facts = result.scalars().all()

                profile: Dict[str, Dict[str, str]] = {}
                for fact in facts:
                    if fact.category not in profile:
                        profile[fact.category] = {}
                    profile[fact.category][fact.key] = fact.value

                logger.debug("Retrieved profile", user_id=user_id, fact_count=len(facts))
                return profile

        except SQLAlchemyError as e:
            logger.error("Failed to get profile", user_id=user_id, error=str(e))
            raise DatabaseException(f"Failed to get profile: {e}")

    # ==================== Conversations ====================

    async def add_conversation(
        self, user_id: int, role: str, message: str
    ) -> ConversationSchema:
        """Add a conversation message."""
        try:
            async with self.get_session() as session:
                conversation = Conversation(
                    user_id=user_id,
                    role=role,
                    message=message,
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

    # ==================== Timeline Events ====================

    async def add_timeline_event(
        self,
        user_id: int,
        event_type: str,
        title: str,
        description: Optional[str],
        datetime_obj: datetime,
    ) -> TimelineEventSchema:
        """Add a timeline event."""
        try:
            async with self.get_session() as session:
                event = TimelineEvent(
                    user_id=user_id,
                    event_type=event_type,
                    title=title,
                    description=description,
                    datetime=datetime_obj,
                    reminded=False,
                    created_at=datetime.utcnow(),
                )
                session.add(event)
                await session.flush()
                return TimelineEventSchema.model_validate(event)

        except SQLAlchemyError as e:
            logger.error("Failed to add timeline event", user_id=user_id, error=str(e))
            raise DatabaseException(f"Failed to add timeline event: {e}")

    async def get_upcoming_events(
        self, user_id: int, days: int = 7
    ) -> List[TimelineEventSchema]:
        """Get upcoming events for a user."""
        try:
            async with self.get_session() as session:
                cutoff = datetime.utcnow() + timedelta(days=days)
                result = await session.execute(
                    select(TimelineEvent)
                    .where(
                        TimelineEvent.user_id == user_id,
                        TimelineEvent.datetime <= cutoff,
                        TimelineEvent.datetime >= datetime.utcnow(),
                    )
                    .order_by(TimelineEvent.datetime)
                )
                events = result.scalars().all()
                return [TimelineEventSchema.model_validate(e) for e in events]

        except SQLAlchemyError as e:
            logger.error("Failed to get upcoming events", user_id=user_id, error=str(e))
            raise DatabaseException(f"Failed to get upcoming events: {e}")

    # ==================== Diary Entries ====================

    async def add_diary_entry(
        self,
        user_id: int,
        entry_type: str,
        title: str,
        content: str,
        importance: int,
        image_url: Optional[str] = None,
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
                )
                session.add(entry)
                await session.flush()
                return DiaryEntrySchema.model_validate(entry)

        except SQLAlchemyError as e:
            logger.error("Failed to add diary entry", user_id=user_id, error=str(e))
            raise DatabaseException(f"Failed to add diary entry: {e}")

    async def get_diary_entries(
        self, user_id: int, limit: int = 50
    ) -> List[DiaryEntrySchema]:
        """Get recent diary entries for a user."""
        try:
            async with self.get_session() as session:
                result = await session.execute(
                    select(DiaryEntry)
                    .where(DiaryEntry.user_id == user_id)
                    .order_by(desc(DiaryEntry.timestamp))
                    .limit(limit)
                )
                entries = result.scalars().all()
                return [DiaryEntrySchema.model_validate(e) for e in entries]

        except SQLAlchemyError as e:
            logger.error("Failed to get diary entries", user_id=user_id, error=str(e))
            raise DatabaseException(f"Failed to get diary entries: {e}")

    # ==================== Scheduled Messages ====================

    async def add_scheduled_message(
        self,
        user_id: int,
        scheduled_time: datetime,
        message_type: str,
        context: Optional[str] = None,
        message: Optional[str] = None,
    ) -> ScheduledMessageSchema:
        """Add a scheduled message to the intent queue."""
        try:
            async with self.get_session() as session:
                scheduled_msg = ScheduledMessage(
                    user_id=user_id,
                    scheduled_time=scheduled_time,
                    message_type=message_type,
                    context=context,
                    message=message,
                    executed=False,
                    created_at=datetime.utcnow(),
                )
                session.add(scheduled_msg)
                await session.flush()
                return ScheduledMessageSchema.model_validate(scheduled_msg)

        except SQLAlchemyError as e:
            logger.error("Failed to add scheduled message", user_id=user_id, error=str(e))
            raise DatabaseException(f"Failed to add scheduled message: {e}")

    async def get_pending_scheduled_messages(self) -> List[ScheduledMessageSchema]:
        """Get all pending scheduled messages that are due."""
        try:
            async with self.get_session() as session:
                result = await session.execute(
                    select(ScheduledMessage)
                    .where(
                        ScheduledMessage.executed == False,
                        ScheduledMessage.scheduled_time <= datetime.utcnow(),
                    )
                    .order_by(ScheduledMessage.scheduled_time)
                )
                messages = result.scalars().all()
                return [ScheduledMessageSchema.model_validate(m) for m in messages]

        except SQLAlchemyError as e:
            logger.error("Failed to get pending messages", error=str(e))
            raise DatabaseException(f"Failed to get pending messages: {e}")

    async def mark_message_executed(self, message_id: int) -> None:
        """Mark a scheduled message as executed."""
        try:
            async with self.get_session() as session:
                result = await session.execute(
                    select(ScheduledMessage).where(ScheduledMessage.id == message_id)
                )
                message = result.scalar_one_or_none()
                if message:
                    message.executed = True
                    session.add(message)
                    logger.debug("Marked message as executed", message_id=message_id)

        except SQLAlchemyError as e:
            logger.error("Failed to mark message executed", message_id=message_id, error=str(e))
            raise DatabaseException(f"Failed to mark message executed: {e}")


# Singleton instance
db = AsyncDatabase()
