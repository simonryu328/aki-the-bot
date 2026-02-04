"""User schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class UserBaseSchema(BaseModel):
    """Base user schema with common fields."""

    telegram_id: int = Field(..., description="Telegram user ID")
    name: Optional[str] = Field(None, max_length=255, description="User's display name")
    username: Optional[str] = Field(None, max_length=255, description="Telegram username")


class UserCreateSchema(UserBaseSchema):
    """Schema for creating a new user."""

    pass


class UserUpdateSchema(BaseModel):
    """Schema for updating user information."""

    name: Optional[str] = Field(None, max_length=255)
    username: Optional[str] = Field(None, max_length=255)


class UserSchema(UserBaseSchema):
    """Complete user schema with all fields."""

    id: int = Field(..., description="Internal user ID")
    created_at: datetime = Field(..., description="User creation timestamp")
    last_interaction: datetime = Field(..., description="Last interaction timestamp")

    model_config = ConfigDict(from_attributes=True)
