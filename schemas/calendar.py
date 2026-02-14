"""Calendar event schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class CalendarEventCreate(BaseModel):
    """Schema for creating a calendar event."""

    title: str = Field(..., max_length=500, description="Event title")
    description: Optional[str] = Field(None, description="Event description")
    event_start: datetime = Field(..., description="Event start time")
    event_end: Optional[datetime] = Field(None, description="Event end time")
    is_all_day: bool = Field(default=False, description="Whether this is an all-day event")


class CalendarEventSchema(CalendarEventCreate):
    """Complete calendar event schema."""

    id: int = Field(..., description="Event ID")
    user_id: int = Field(..., description="User ID")
    source: str = Field(..., description="Event source (manual, bot, google)")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = ConfigDict(from_attributes=True)
