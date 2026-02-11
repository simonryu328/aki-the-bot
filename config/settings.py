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

    # Webhook Configuration (for production)
    WEBHOOK_URL: str = Field(
        default="",
        description="Public URL for Telegram webhook (e.g., https://aki-bot.up.railway.app). "
                    "When empty, bot uses polling mode.",
    )
    PORT: int = Field(
        default=8443,
        description="Port for the webhook server. Railway sets this via PORT env var.",
        ge=1,
        le=65535,
    )
    WEBHOOK_SECRET: str = Field(
        default="",
        description="Secret token for webhook verification. "
                    "Auto-generated from bot token if empty.",
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
    
    # ==================== Conversation Context Configuration ====================
    # These settings control how much conversation history is included in the AI's context
    
    CONVERSATION_CONTEXT_LIMIT: int = Field(
        default=20,
        description="Number of recent raw messages to ALWAYS include in CURRENT CONVERSATION section. "
                    "These are shown regardless of whether they overlap with compact summaries. "
                    "Used in: soul_agent._build_conversation_context(), telegram_handler reach-out",
        ge=1,
    )
    
    COMPACT_SUMMARY_LIMIT: int = Field(
        default=3,
        description="Number of compact summaries to ALWAYS include in RECENT EXCHANGES section. "
                    "Compact summaries are timestamped conversation summaries created every 10 messages. "
                    "These are shown in addition to the raw messages in CURRENT CONVERSATION. "
                    "Used in: soul_agent._build_conversation_context(), telegram_handler reach-out",
        ge=1,
        le=10,
    )
    
    # ==================== Observation and Compact Configuration ====================
    # These settings control when the AI creates summaries and observations
    
    OBSERVATION_INTERVAL: int = Field(
        default=10,
        description="Number of exchanges before triggering observation agent (currently disabled). "
                    "Observations extract facts about the user from conversations.",
        ge=1,
    )
    
    COMPACT_INTERVAL: int = Field(
        default=10,
        description="Number of messages before creating a compact summary. "
                    "Compact summaries condense recent conversations into timestamped summaries. "
                    "Used in: soul_agent._maybe_create_compact_summary()",
        ge=1,
    )
    
    CONDENSATION_THRESHOLD: int = Field(
        default=50,
        description="Number of raw observations before triggering auto-condensation. "
                    "Condensation converts raw observations into narrative form (legacy feature).",
        ge=1,
    )
    
    # ==================== Database Fetch Limits ====================
    # These settings control how many records to fetch from the database
    
    DIARY_FETCH_LIMIT: int = Field(
        default=10,
        description="Number of diary entries to fetch when looking for compact summaries. "
                    "Should be >= COMPACT_SUMMARY_LIMIT to ensure we get enough compacts. "
                    "Used in: soul_agent._build_conversation_context(), _maybe_create_compact_summary()",
        ge=5,
        le=50,
    )
    
    OBSERVATION_DISPLAY_LIMIT: int = Field(
        default=20,
        description="Number of observations to display in context. "
                    "Used in: soul_agent._build_profile_context() when showing raw observations. "
                    "Note: Observations are currently disabled in favor of compact summaries.",
        ge=10,
        le=100,
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
