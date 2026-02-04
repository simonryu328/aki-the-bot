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

    # Environment
    ENVIRONMENT: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Application environment",
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
