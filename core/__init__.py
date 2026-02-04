"""
Core utilities and infrastructure for the AI Companion application.
"""

from core.exceptions import (
    AICompanionException,
    DatabaseException,
    RecordNotFoundError,
    DuplicateRecordError,
    DatabaseConnectionError,
    VectorStoreException,
    VectorStoreConnectionError,
    EmbeddingError,
    MemoryException,
    UserNotFoundError,
    InvalidMemoryDataError,
    ExternalServiceException,
    OpenAIAPIError,
    TelegramAPIError,
    ValidationException,
    InvalidInputError,
    ConfigurationError,
)
from core.logging_config import configure_logging, get_logger

__all__ = [
    "AICompanionException",
    "DatabaseException",
    "RecordNotFoundError",
    "DuplicateRecordError",
    "DatabaseConnectionError",
    "VectorStoreException",
    "VectorStoreConnectionError",
    "EmbeddingError",
    "MemoryException",
    "UserNotFoundError",
    "InvalidMemoryDataError",
    "ExternalServiceException",
    "OpenAIAPIError",
    "TelegramAPIError",
    "ValidationException",
    "InvalidInputError",
    "ConfigurationError",
    "configure_logging",
    "get_logger",
]
