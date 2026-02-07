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
    
    # Reach-out configuration
    reach_out_enabled: bool = Field(True, description="Whether reach-outs are enabled for this user")
    reach_out_min_silence_hours: int = Field(6, description="Minimum hours of silence before reaching out")
    reach_out_max_silence_days: int = Field(3, description="Maximum days to keep trying reach-outs")
    last_reach_out_at: Optional[datetime] = Field(None, description="When bot last reached out")

    model_config = ConfigDict(from_attributes=True)
