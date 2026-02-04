"""
SQLAlchemy models for the AI Companion memory system.
Defines all database tables for storing user data, conversations, and memories.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Float,
    Boolean,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    """User table - stores Telegram user information."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    username = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False)
    last_interaction = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False)

    # Relationships
    profile_facts = relationship("ProfileFact", back_populates="user", cascade="all, delete-orphan")
    timeline_events = relationship("TimelineEvent", back_populates="user", cascade="all, delete-orphan")
    diary_entries = relationship("DiaryEntry", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    scheduled_messages = relationship("ScheduledMessage", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, name='{self.name}')>"


class ProfileFact(Base):
    """Profile facts - stores knowledge about the user."""

    __tablename__ = "profile_facts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    category = Column(String(100), nullable=False, index=True)  # e.g., "basic_info", "preferences", "relationships"
    key = Column(String(255), nullable=False)  # e.g., "job", "favorite_food", "best_friend"
    value = Column(Text, nullable=False)
    confidence = Column(Float, default=1.0)  # 0.0 to 1.0, how confident we are about this fact
    updated_at = Column(DateTime, default=lambda: datetime.utcnow(), onupdate=lambda: datetime.utcnow(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="profile_facts")

    def __repr__(self):
        return f"<ProfileFact(user_id={self.user_id}, category='{self.category}', key='{self.key}')>"


class TimelineEvent(Base):
    """Timeline events - upcoming or recurring events in the user's life."""

    __tablename__ = "timeline_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)  # e.g., "meeting", "appointment", "deadline", "recurring"
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    datetime = Column(DateTime, nullable=False, index=True)
    reminded = Column(Boolean, default=False)  # Has the user been reminded about this?
    created_at = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="timeline_events")

    def __repr__(self):
        return f"<TimelineEvent(user_id={self.user_id}, title='{self.title}', datetime={self.datetime})>"


class DiaryEntry(Base):
    """Diary entries - milestone moments and significant events."""

    __tablename__ = "diary_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    entry_type = Column(String(100), nullable=False)  # e.g., "achievement", "milestone", "significant_event", "visual_memory"
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    importance = Column(Integer, nullable=False)  # 0-10 scale
    image_url = Column(String(1000), nullable=True)  # Path to stored image if applicable
    timestamp = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="diary_entries")

    def __repr__(self):
        return f"<DiaryEntry(user_id={self.user_id}, title='{self.title}', importance={self.importance})>"


class Conversation(Base):
    """Conversation history - all messages exchanged with the user."""

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(50), nullable=False)  # "user" or "assistant"
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="conversations")

    def __repr__(self):
        return f"<Conversation(user_id={self.user_id}, role='{self.role}', timestamp={self.timestamp})>"


class ScheduledMessage(Base):
    """Scheduled messages - the intent queue for proactive messaging."""

    __tablename__ = "scheduled_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    scheduled_time = Column(DateTime, nullable=False, index=True)
    message_type = Column(String(100), nullable=False)  # e.g., "follow_up", "goal_check", "event_reminder"
    context = Column(Text, nullable=True)  # JSON or text context for generating the message
    message = Column(Text, nullable=True)  # Pre-generated message (optional)
    executed = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="scheduled_messages")

    def __repr__(self):
        return f"<ScheduledMessage(user_id={self.user_id}, scheduled_time={self.scheduled_time}, executed={self.executed})>"
