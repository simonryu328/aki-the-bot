"""Timeline event schemas."""

from datetime import datetime as dt
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class TimelineEventBaseSchema(BaseModel):
    """Base timeline event schema."""

    event_type: str = Field(
        ...,
        max_length=100,
        description="Event type (e.g., 'meeting', 'appointment', 'deadline')",
    )
    title: str = Field(..., max_length=500, description="Event title")
    description: Optional[str] = Field(None, description="Event description")
    datetime: dt = Field(..., description="Event date and time")


class TimelineEventCreateSchema(TimelineEventBaseSchema):
    """Schema for creating a timeline event."""

    user_id: int = Field(..., description="User ID")


class TimelineEventSchema(TimelineEventBaseSchema):
    """Complete timeline event schema."""

    id: int = Field(..., description="Event ID")
    user_id: int = Field(..., description="User ID")
    reminded: bool = Field(default=False, description="Whether user has been reminded")
    created_at: dt = Field(..., description="Event creation timestamp")

    model_config = ConfigDict(from_attributes=True)
