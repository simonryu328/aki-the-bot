"""
Database operations for the AI Companion memory system.
Provides CRUD operations and helper methods for all database tables.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from config.settings import settings
from memory.models import (
    Base,
    User,
    ProfileFact,
    TimelineEvent,
    DiaryEntry,
    Conversation,
    ScheduledMessage,
)

logger = logging.getLogger(__name__)


class Database:
    """Database manager for the AI Companion."""

    def __init__(self):
        """Initialize database connection."""
        self.engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,  # Verify connections before using
            echo=False,  # Set to True for SQL debugging
        )
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
        logger.info("Database connection initialized")

    def create_tables(self):
        """Create all tables in the database."""
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables created")

    @contextmanager
    def get_session(self):
        """
        Context manager for database sessions.
        Automatically commits or rolls back transactions.
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            session.close()

    # ==================== User Operations ====================

    def get_or_create_user(
        self, telegram_id: int, name: Optional[str] = None, username: Optional[str] = None
    ) -> int:
        """
        Get existing user or create new one.

        Args:
            telegram_id: Telegram user ID
            name: User's display name
            username: User's Telegram username

        Returns:
            User ID (int)
        """
        with self.get_session() as session:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()

            if user:
                # Update last interaction
                user.last_interaction = datetime.utcnow()
                # Update name/username if provided
                if name:
                    user.name = name
                if username:
                    user.username = username
                session.add(user)
                user_id = user.id
                logger.info(f"Retrieved existing user: {telegram_id}")
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
                session.flush()  # Get the ID
                user_id = user.id
                logger.info(f"Created new user: {telegram_id} (id={user_id})")

            return user_id

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by internal ID, returns user info as dict."""
        with self.get_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return None
            return {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "name": user.name,
                "username": user.username,
                "created_at": user.created_at,
                "last_interaction": user.last_interaction,
            }

    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Get user by Telegram ID, returns user info as dict."""
        with self.get_session() as session:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                return None
            return {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "name": user.name,
                "username": user.username,
                "created_at": user.created_at,
                "last_interaction": user.last_interaction,
            }

    # ==================== Profile Facts ====================

    def add_profile_fact(
        self,
        user_id: int,
        category: str,
        key: str,
        value: str,
        confidence: float = 1.0,
    ) -> ProfileFact:
        """
        Add or update a profile fact.

        Args:
            user_id: User ID
            category: Fact category (e.g., "basic_info", "preferences")
            key: Fact key (e.g., "job", "location")
            value: Fact value
            confidence: Confidence score (0.0 to 1.0)

        Returns:
            ProfileFact object
        """
        with self.get_session() as session:
            # Check if fact already exists
            fact = (
                session.query(ProfileFact)
                .filter(
                    ProfileFact.user_id == user_id,
                    ProfileFact.category == category,
                    ProfileFact.key == key,
                )
                .first()
            )

            if fact:
                # Update existing fact
                fact.value = value
                fact.confidence = confidence
                fact.updated_at = datetime.utcnow()
                logger.info(f"Updated profile fact: {category}.{key} for user {user_id}")
            else:
                # Create new fact
                fact = ProfileFact(
                    user_id=user_id,
                    category=category,
                    key=key,
                    value=value,
                    confidence=confidence,
                )
                session.add(fact)
                logger.info(f"Added profile fact: {category}.{key} for user {user_id}")

            return fact

    def get_user_profile(self, user_id: int) -> Dict[str, Dict[str, str]]:
        """
        Get all profile facts for a user, organized by category.

        Returns:
            Dict with structure: {category: {key: value}}
        """
        with self.get_session() as session:
            facts = (
                session.query(ProfileFact)
                .filter(ProfileFact.user_id == user_id)
                .all()
            )

            profile = {}
            for fact in facts:
                if fact.category not in profile:
                    profile[fact.category] = {}
                profile[fact.category][fact.key] = fact.value

            return profile

    # ==================== Timeline Events ====================

    def add_timeline_event(
        self,
        user_id: int,
        event_type: str,
        title: str,
        description: Optional[str],
        datetime_obj: datetime,
    ) -> TimelineEvent:
        """
        Add a timeline event.

        Args:
            user_id: User ID
            event_type: Type of event (e.g., "meeting", "appointment")
            title: Event title
            description: Event description
            datetime_obj: Event datetime

        Returns:
            TimelineEvent object
        """
        with self.get_session() as session:
            event = TimelineEvent(
                user_id=user_id,
                event_type=event_type,
                title=title,
                description=description,
                datetime=datetime_obj,
            )
            session.add(event)
            logger.info(f"Added timeline event: {title} for user {user_id}")
            return event

    def get_upcoming_events(
        self, user_id: int, days: int = 7
    ) -> List[TimelineEvent]:
        """
        Get upcoming events for a user.

        Args:
            user_id: User ID
            days: Number of days to look ahead

        Returns:
            List of TimelineEvent objects
        """
        with self.get_session() as session:
            future_date = datetime.utcnow() + timedelta(days=days)
            events = (
                session.query(TimelineEvent)
                .filter(
                    TimelineEvent.user_id == user_id,
                    TimelineEvent.datetime >= datetime.utcnow(),
                    TimelineEvent.datetime <= future_date,
                )
                .order_by(TimelineEvent.datetime)
                .all()
            )
            return events

    # ==================== Diary Entries ====================

    def add_diary_entry(
        self,
        user_id: int,
        entry_type: str,
        title: str,
        content: str,
        importance: int,
        image_url: Optional[str] = None,
    ) -> DiaryEntry:
        """
        Add a diary entry (milestone moment).

        Args:
            user_id: User ID
            entry_type: Type of entry (e.g., "achievement", "milestone")
            title: Entry title
            content: Entry content
            importance: Importance score (0-10)
            image_url: Path to associated image

        Returns:
            DiaryEntry object
        """
        with self.get_session() as session:
            entry = DiaryEntry(
                user_id=user_id,
                entry_type=entry_type,
                title=title,
                content=content,
                importance=importance,
                image_url=image_url,
            )
            session.add(entry)
            logger.info(f"Added diary entry: {title} for user {user_id}")
            return entry

    def get_diary_entries(
        self, user_id: int, limit: int = 50
    ) -> List[DiaryEntry]:
        """Get recent diary entries for a user."""
        with self.get_session() as session:
            entries = (
                session.query(DiaryEntry)
                .filter(DiaryEntry.user_id == user_id)
                .order_by(desc(DiaryEntry.timestamp))
                .limit(limit)
                .all()
            )
            return entries

    # ==================== Conversations ====================

    def add_conversation(
        self, user_id: int, role: str, message: str
    ) -> Conversation:
        """
        Add a conversation message.

        Args:
            user_id: User ID
            role: Message role ("user" or "assistant")
            message: Message content

        Returns:
            Conversation object
        """
        with self.get_session() as session:
            conv = Conversation(
                user_id=user_id,
                role=role,
                message=message,
            )
            session.add(conv)
            return conv

    def get_recent_conversations(
        self, user_id: int, limit: int = 10
    ) -> List[Conversation]:
        """Get recent conversation messages for a user."""
        with self.get_session() as session:
            conversations = (
                session.query(Conversation)
                .filter(Conversation.user_id == user_id)
                .order_by(desc(Conversation.timestamp))
                .limit(limit)
                .all()
            )
            return list(reversed(conversations))  # Return chronological order

    # ==================== Scheduled Messages ====================

    def add_scheduled_message(
        self,
        user_id: int,
        scheduled_time: datetime,
        message_type: str,
        context: Optional[str] = None,
        message: Optional[str] = None,
    ) -> ScheduledMessage:
        """
        Add a scheduled message to the intent queue.

        Args:
            user_id: User ID
            scheduled_time: When to send the message
            message_type: Type of message (e.g., "follow_up", "goal_check")
            context: Context for generating the message
            message: Pre-generated message (optional)

        Returns:
            ScheduledMessage object
        """
        with self.get_session() as session:
            scheduled = ScheduledMessage(
                user_id=user_id,
                scheduled_time=scheduled_time,
                message_type=message_type,
                context=context,
                message=message,
            )
            session.add(scheduled)
            logger.info(f"Scheduled message for user {user_id} at {scheduled_time}")
            return scheduled

    def get_pending_scheduled_messages(self) -> List[ScheduledMessage]:
        """Get all pending scheduled messages that are due."""
        with self.get_session() as session:
            messages = (
                session.query(ScheduledMessage)
                .filter(
                    ScheduledMessage.executed == False,
                    ScheduledMessage.scheduled_time <= datetime.utcnow(),
                )
                .all()
            )
            return messages

    def mark_message_executed(self, message_id: int):
        """Mark a scheduled message as executed."""
        with self.get_session() as session:
            message = (
                session.query(ScheduledMessage)
                .filter(ScheduledMessage.id == message_id)
                .first()
            )
            if message:
                message.executed = True
                logger.info(f"Marked scheduled message {message_id} as executed")


# Singleton instance
db = Database()
