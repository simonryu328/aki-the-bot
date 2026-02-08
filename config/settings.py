"""
Configuration settings for the AI Companion application.
Uses Pydantic Settings for type-safe configuration with validation.
"""

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Pydantic validates types and provides clear error messages for misconfigurations.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Ignore extra env vars
    )

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = Field(
        ...,
        description="Telegram bot token from BotFather",
        min_length=1,
    )

    # OpenAI API
    OPENAI_API_KEY: str = Field(
        ...,
        description="OpenAI API key for LLM and embeddings",
        min_length=1,
    )

    # Pinecone Vector Database
    PINECONE_API_KEY: str = Field(
        default="",
        description="Pinecone API key (optional if vector store not used)",
    )

    # Database
    DATABASE_URL: str = Field(
        default="postgresql://postgres:password@localhost:5432/ai_companion",
        description="PostgreSQL database connection URL",
    )

    # Application
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level",
    )

    TIMEZONE: str = Field(
        default="America/Toronto",
        description="Application timezone",
    )

    # Models - one setting per purpose, all configurable from .env
    # claude-opus-4-20250514
    # claude-haiku-4-5-20251001
    # claude-sonnet-4-5-20250929

    MODEL_CONVERSATION: str = Field(
        default="claude-sonnet-4-5-20250929",
        description="Model for main conversation responses",
    )
    MODEL_OBSERVATION: str = Field(
        default="claude-haiku-4-5-20251001",
        description="Model for observation/memory extraction",
    )
    MODEL_PROACTIVE: str = Field(
        default="claude-haiku-4-5-20251001",
        description="Model for proactive/scheduled messages",
    )
    MODEL_SUMMARY: str = Field(
        default="claude-haiku-4-5-20251001",
        description="Model for profile summaries",
    )

    # Environment
    ENVIRONMENT: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Application environment",
    )

    # Reach-Out Configuration
    REACH_OUT_CHECK_INTERVAL_MINUTES: int = Field(
        default=60,
        description="How often to check for inactive users (in minutes)",
        ge=1,
    )
    DEFAULT_REACH_OUT_MIN_SILENCE_HOURS: int = Field(
        default=6,
        description="Default minimum hours of silence before reaching out",
        ge=1,
    )
    DEFAULT_REACH_OUT_MAX_SILENCE_DAYS: int = Field(
        default=3,
        description="Default maximum days to keep trying reach-outs",
        ge=1,
    )
    
    # Reaction Configuration
    REACTION_MIN_MESSAGES: int = Field(
        default=1,
        description="Minimum messages before triggering a reaction",
        ge=1,
    )
    REACTION_MAX_MESSAGES: int = Field(
        default=5,
        description="Maximum messages before triggering a reaction",
        ge=1,
    )
    
    # Conversation Context Configuration
    CONVERSATION_CONTEXT_LIMIT: int = Field(
        default=20,
        description="Number of recent messages to include in conversation context",
        ge=1,
    )
    
    # Observation and Compact Configuration
    OBSERVATION_INTERVAL: int = Field(
        default=10,
        description="Number of exchanges before triggering observation agent (currently disabled)",
        ge=1,
    )
    COMPACT_INTERVAL: int = Field(
        default=10,
        description="Number of exchanges before creating compact summary",
        ge=1,
    )
    CONDENSATION_THRESHOLD: int = Field(
        default=50,
        description="Number of observations before triggering auto-condensation",
        ge=1,
    )
    
    # Message Splitting Configuration
    AUTO_SPLIT_THRESHOLD: int = Field(
        default=300,
        description="Character length threshold for auto-splitting messages",
        ge=100,
    )
    SMART_SPLIT_MAX_LENGTH: int = Field(
        default=250,
        description="Target max length for each split message chunk",
        ge=100,
    )

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Ensure database URL is properly formatted."""
        if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
            raise ValueError("DATABASE_URL must start with postgresql:// or postgresql+asyncpg://")
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT == "development"


# Create singleton instance with validation
# This will automatically load from .env and validate all fields
settings = Settings()
