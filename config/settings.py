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

    # Anthropic API
    ANTHROPIC_API_KEY: str = Field(
        default="",
        description="Anthropic API key",
    )

    # Gemini API
    GEMINI_API_KEY: str = Field(
        default="",
        description="Gemini API key",
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
    # gpt-4o
    # gpt-4o-mini
    # claude-haiku-4-5-20251001
    # claude-sonnet-4-5-20250929

    MODEL_CONVERSATION: str = Field(
        default="claude-haiku-4-5-20251001",
        description="Model for main conversation responses",
    )
    MODEL_PROACTIVE: str = Field(
        default="claude-haiku-4-5-20251001",
        description="Model for proactive/scheduled messages",
    )
    MODEL_MEMORY: str = Field(
        default="claude-haiku-4-5-20251001",
        description="Model for memories and summaries",
    )
    MODEL_DAILY_MESSAGE: str = Field(
        default="claude-haiku-4-5-20251001",
        description="Model for generating daily motivational messages",
    )
    MODEL_INSIGHTS: str = Field(
        default="claude-haiku-4-5-20251001",
        description="Model for generating fun personalized insights",
    )

    MEMORY_MAX_TOKENS: int = Field(
        default=500,
        description="Max tokens for conversation memory generation",
    )

    SUMMARY_MAX_TOKENS: int = Field(
        default=300,
        description="Max tokens for compact summary generation",
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
        default=12,
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
        default=2,
        description="Minimum messages before triggering a reaction",
        ge=1,
    )
    REACTION_MAX_MESSAGES: int = Field(
        default=5,
        description="Maximum messages before triggering a reaction",
        ge=1,
    )
    
    # Sticker Configuration
    STICKER_MIN_MESSAGES: int = Field(
        default=1,
        description="Minimum messages before sending a sticker",
        ge=1,
    )
    STICKER_MAX_MESSAGES: int = Field(
        default=5,
        description="Maximum messages before sending a sticker",
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
        default=2,
        description="DEPRECATED. Used to be number of recent compact summaries. "
                    "Current system uses MEMORY_ENTRY_LIMIT exclusively.",
        ge=0,
        le=10,
    )
    
    MEMORY_ENTRY_LIMIT: int = Field(
        default=4,
        description="Number of recent memory entries to include in RECENT EXCHANGES section. "
                    "Replaced the dual-core memory with a single-source memory from conversation_memory entries.",
        ge=1,
        le=10,
    )
    
    
    COMPACT_INTERVAL: int = Field(
        default=30,
        description="Number of messages (user + assistant combined) before creating a compact summary AND memory entry. "
                    "Both are triggered together when this threshold is reached. "
                    "Compact summaries condense recent conversations into timestamped summaries. "
                    "Memory entries extract significant moments and insights from the exchange. "
                    "Used in: soul_agent._maybe_create_compact_summary()",
        ge=1,
    )
    
    MEMORY_ENTRY_INTERVAL: int = Field(
        default=30,
        description="Number of messages (user + assistant combined) before creating a conversation memory entry. "
                    "Currently uses COMPACT_INTERVAL value (both triggered together). "
                    "Memory entries capture significant moments, emotional beats, and relationship insights. "
                    "Stored as diary entries with type 'conversation_memory'. "
                    "Used in: soul_agent._maybe_create_compact_summary() -> _create_memory_entry()",
        ge=1,
    )
    
    
    # ==================== Database Fetch Limits ====================
    # These settings control how many records to fetch from the database
    
    DIARY_FETCH_LIMIT: int = Field(
        default=20,
        description="Number of diary entries to fetch when looking for compact summaries. "
                    "Should be >= COMPACT_SUMMARY_LIMIT to ensure we get enough compacts. "
                    "Used in: soul_agent._build_conversation_context(), _maybe_create_compact_summary()",
        ge=5,
        le=50,
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
    
    # ==================== Message Debouncing Configuration ====================
    # Controls how long to wait for additional messages before processing
    
    DEBOUNCE_SECONDS: float = Field(
        default=0.5,
        description="Seconds to wait after last message before processing buffered messages. "
                    "Allows users to send multiple messages that get combined into one response. "
                    "Lower values = faster response but may split multi-message thoughts. "
                    "Higher values = better message grouping but slower perceived response.",
        ge=0.5,
        le=10.0,
    )
    
    # ==================== Rate Limiting Configuration ====================
    # These settings control per-user message rate limits to prevent abuse
    
    USER_RATE_LIMIT_MESSAGES: int = Field(
        default=10,
        description="Maximum number of messages a user can send per time window. "
                    "Prevents spam and runaway LLM costs. Set to 0 to disable rate limiting.",
        ge=0,
    )
    
    USER_RATE_LIMIT_WINDOW_SECONDS: int = Field(
        default=60,
        description="Time window in seconds for rate limiting. "
                    "Used with USER_RATE_LIMIT_MESSAGES to create a sliding window rate limit.",
        ge=1,
    )

    USER_DAILY_TOKEN_BUDGET: int = Field(
        default=0,
        description="Maximum tokens a user can consume per day. "
                    "Prevents runaway costs. Set to 0 to disable.",
        ge=0,
    )

    LOG_RAW_LLM: bool = Field(
        default=False,
        description="Whether to log raw LLM responses at INFO level for debugging. "
                    "When False, raw responses are logged at DEBUG level.",
    )

    # Spotify Configuration
    SPOTIFY_CLIENT_ID: str = Field(
        default="",
        description="Spotify Client ID from the Developer Dashboard",
    )
    SPOTIFY_CLIENT_SECRET: str = Field(
        default="",
        description="Spotify Client Secret from the Developer Dashboard",
    )
    SPOTIFY_REDIRECT_URI: str = Field(
        default="",
        description="Spotify Redirect URI for OAuth flow",
    )
    
    MINIAPP_URL: str = Field(
        default="",
        description="Public URL for the Telegram Mini App (e.g., https://aki-miniapp.up.railway.app)",
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
