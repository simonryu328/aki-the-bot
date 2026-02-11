"""
Custom exception hierarchy for the AI Companion application.
Provides structured error handling with proper context.
"""

from typing import Optional, Dict, Any


class AICompanionException(Exception):
    """Base exception for all AI Companion errors."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize exception with message and optional context.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            context: Additional context information
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.context = context or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/API responses."""
        return {
            "error": self.error_code,
            "message": self.message,
            "context": self.context,
        }


# ==================== Database Exceptions ====================


class DatabaseException(AICompanionException):
    """Base exception for database-related errors."""

    pass


class RecordNotFoundError(DatabaseException):
    """Raised when a database record is not found."""

    def __init__(self, model: str, identifier: Any):
        super().__init__(
            message=f"{model} not found",
            error_code="RECORD_NOT_FOUND",
            context={"model": model, "identifier": identifier},
        )


class DuplicateRecordError(DatabaseException):
    """Raised when attempting to create a duplicate record."""

    def __init__(self, model: str, field: str, value: Any):
        super().__init__(
            message=f"{model} with {field}={value} already exists",
            error_code="DUPLICATE_RECORD",
            context={"model": model, "field": field, "value": value},
        )


class DatabaseConnectionError(DatabaseException):
    """Raised when database connection fails."""

    def __init__(self, details: Optional[str] = None):
        super().__init__(
            message="Failed to connect to database",
            error_code="DATABASE_CONNECTION_ERROR",
            context={"details": details} if details else {},
        )


# ==================== Memory Exceptions ====================


class MemoryException(AICompanionException):
    """Base exception for memory-related errors."""

    pass


class UserNotFoundError(MemoryException):
    """Raised when user is not found."""

    def __init__(self, user_id: int):
        super().__init__(
            message=f"User {user_id} not found",
            error_code="USER_NOT_FOUND",
            context={"user_id": user_id},
        )


class InvalidMemoryDataError(MemoryException):
    """Raised when memory data is invalid."""

    def __init__(self, field: str, reason: str):
        super().__init__(
            message=f"Invalid memory data: {field} - {reason}",
            error_code="INVALID_MEMORY_DATA",
            context={"field": field, "reason": reason},
        )


# ==================== API/External Service Exceptions ====================


class ExternalServiceException(AICompanionException):
    """Base exception for external service errors."""

    pass


class OpenAIAPIError(ExternalServiceException):
    """Raised when OpenAI API call fails."""

    def __init__(self, status_code: Optional[int] = None, details: Optional[str] = None):
        super().__init__(
            message="OpenAI API request failed",
            error_code="OPENAI_API_ERROR",
            context={"status_code": status_code, "details": details},
        )


class TelegramAPIError(ExternalServiceException):
    """Raised when Telegram API call fails."""

    def __init__(self, status_code: Optional[int] = None, details: Optional[str] = None):
        super().__init__(
            message="Telegram API request failed",
            error_code="TELEGRAM_API_ERROR",
            context={"status_code": status_code, "details": details},
        )


# ==================== Validation Exceptions ====================


class ValidationException(AICompanionException):
    """Base exception for validation errors."""

    pass


class InvalidInputError(ValidationException):
    """Raised when input validation fails."""

    def __init__(self, field: str, reason: str):
        super().__init__(
            message=f"Invalid input: {field} - {reason}",
            error_code="INVALID_INPUT",
            context={"field": field, "reason": reason},
        )


class ConfigurationError(ValidationException):
    """Raised when configuration is invalid."""

    def __init__(self, setting: str, reason: str):
        super().__init__(
            message=f"Invalid configuration: {setting} - {reason}",
            error_code="CONFIGURATION_ERROR",
            context={"setting": setting, "reason": reason},
        )
