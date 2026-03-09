"""
SQLAlchemy models for the AI Companion memory system.
Defines all database tables for storing user data, conversations, and memories.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column,
    Index,
    Integer,
    BigInteger,
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
    __table_args__ = (
        Index("idx_users_reach_out", "reach_out_enabled", postgresql_where="reach_out_enabled = TRUE"),
    )

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    username = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False)
    last_interaction = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False)
    
    # Onboarding state (null = completed, 'awaiting_name' = waiting for name choice)
    onboarding_state = Column(String(50), nullable=True)
    
    # User preferences
    timezone = Column(String(100), default="America/Toronto", nullable=False)  # IANA timezone
    
    # Reach-out configuration (per user)
    reach_out_enabled = Column(Boolean, default=True, nullable=False)
    reach_out_min_silence_hours = Column(Integer, default=6, nullable=False)
    reach_out_max_silence_days = Column(Integer, default=3, nullable=False)
    last_reach_out_at = Column(DateTime, nullable=True)
    
    # Spotify Integration
    spotify_access_token = Column(Text, nullable=True)
    spotify_refresh_token = Column(Text, nullable=True)
    spotify_token_expires_at = Column(DateTime, nullable=True)

    # Relationships
    diary_entries = relationship("DiaryEntry", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, name='{self.name}')>"


class DiaryEntry(Base):
    """Diary entries - milestone moments and significant events."""

    __tablename__ = "diary_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    entry_type = Column(String(100), nullable=False)  # e.g., "achievement", "milestone", "significant_event", "visual_memory", "compact_summary"
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    importance = Column(Integer, nullable=False)  # 0-10 scale
    image_url = Column(String(1000), nullable=True)  # Path to stored image if applicable
    timestamp = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False, index=True)
    exchange_start = Column(DateTime, nullable=True, index=True)  # For compact_summary: when conversation exchange began
    exchange_end = Column(DateTime, nullable=True, index=True)  # For compact_summary: when conversation exchange ended

    # Relationships
    user = relationship("User", back_populates="diary_entries")

    def __repr__(self):
        return f"<DiaryEntry(user_id={self.user_id}, title='{self.title}', importance={self.importance})>"


class Conversation(Base):
    """Conversation history - all messages exchanged with the user."""

    __tablename__ = "conversations"
    __table_args__ = (
        Index("idx_conversations_user_timestamp", "user_id", "timestamp"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(50), nullable=False)  # "user" or "assistant"
    message = Column(Text, nullable=False)
    thinking = Column(Text, nullable=True)  # LLM reasoning for assistant messages
    timestamp = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="conversations")

    def __repr__(self):
        return f"<Conversation(user_id={self.user_id}, role='{self.role}', timestamp={self.timestamp})>"


class TokenUsage(Base):
    """Token usage tracking - records LLM token consumption per call."""

    __tablename__ = "token_usage"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    model = Column(String(255), nullable=False)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    cache_read_tokens = Column(Integer, nullable=False, default=0)
    cache_creation_tokens = Column(Integer, nullable=False, default=0)
    call_type = Column(String(100), nullable=False)  # "conversation", "compact", "observation", "proactive", "reach_out"
    timestamp = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False)

    # Relationships
    user = relationship("User")

    def __repr__(self):
        return f"<TokenUsage(user_id={self.user_id}, model='{self.model}', total={self.total_tokens}, type='{self.call_type}')>"


class FutureEntry(Base):
    """Future entries - goals, plans, and notes for the Future tab."""

    __tablename__ = "future_entries"
    __table_args__ = (
        Index("idx_future_entries_user_time", "user_id", "start_time"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    entry_type = Column(String(50), nullable=False)  # "plan" or "note"
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=True)
    start_time = Column(DateTime, nullable=True, index=True) # Optional for notes
    end_time = Column(DateTime, nullable=True)
    is_all_day = Column(Boolean, default=False, nullable=False)
    is_completed = Column(Boolean, default=False, nullable=False)
    source = Column(String(50), default="manual", nullable=False)  # "manual", "bot", "google"
    created_at = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False)

    # Relationships
    user = relationship("User", backref="future_entries")

    def __repr__(self):
        return f"<FutureEntry(user_id={self.user_id}, type='{self.entry_type}', title='{self.title}')>"
