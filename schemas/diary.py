"""Diary entry schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class DiaryEntryBaseSchema(BaseModel):
    """Base diary entry schema."""

    entry_type: str = Field(
        ...,
        max_length=100,
        description="Entry type (e.g., 'achievement', 'milestone', 'visual_memory', 'compact_summary')",
    )
    title: str = Field(..., max_length=500, description="Entry title")
    content: str = Field(..., description="Entry content")
    importance: int = Field(..., ge=0, le=10, description="Importance score (0-10)")
    image_url: Optional[str] = Field(
        None, max_length=1000, description="Associated image URL"
    )
    exchange_start: Optional[datetime] = Field(
        None, description="For compact_summary: when conversation exchange began"
    )
    exchange_end: Optional[datetime] = Field(
        None, description="For compact_summary: when conversation exchange ended"
    )


class DiaryEntryCreateSchema(DiaryEntryBaseSchema):
    """Schema for creating a diary entry."""

    user_id: int = Field(..., description="User ID")


class DiaryEntrySchema(DiaryEntryBaseSchema):
    """Complete diary entry schema."""

    id: int = Field(..., description="Diary entry ID")
    user_id: int = Field(..., description="User ID")
    timestamp: datetime = Field(..., description="Entry timestamp")

    model_config = ConfigDict(from_attributes=True)


class DailyMessageSchema(BaseModel):
    """Schema for the daily message response."""

    content: str = Field(..., description="The generated daily message")
    timestamp: datetime = Field(..., description="When the message was generated")
    is_fallback: bool = Field(False, description="Whether this is a fallback quote")
