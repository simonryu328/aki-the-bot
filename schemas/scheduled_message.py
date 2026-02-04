"""Scheduled message schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class ScheduledMessageBaseSchema(BaseModel):
    """Base scheduled message schema."""

    scheduled_time: datetime = Field(..., description="When to send the message")
    message_type: str = Field(
        ...,
        max_length=100,
        description="Message type (e.g., 'follow_up', 'goal_check', 'event_reminder')",
    )
    context: Optional[str] = Field(None, description="Context for generating the message")
    message: Optional[str] = Field(None, description="Pre-generated message (optional)")


class ScheduledMessageCreateSchema(ScheduledMessageBaseSchema):
    """Schema for creating a scheduled message."""

    user_id: int = Field(..., description="User ID")


class ScheduledMessageSchema(ScheduledMessageBaseSchema):
    """Complete scheduled message schema."""

    id: int = Field(..., description="Scheduled message ID")
    user_id: int = Field(..., description="User ID")
    executed: bool = Field(default=False, description="Whether message has been sent")
    created_at: datetime = Field(..., description="Message creation timestamp")

    model_config = ConfigDict(from_attributes=True)
