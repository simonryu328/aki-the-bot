"""Future entry schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class FutureEntryCreate(BaseModel):
    """Schema for creating a future entry."""

    entry_type: str = Field(..., description="'plan' or 'note'")
    title: str = Field(..., max_length=500, description="Title")
    content: Optional[str] = Field(None, description="Content/Description")
    start_time: Optional[datetime] = Field(None, description="Start time (optional for notes)")
    end_time: Optional[datetime] = Field(None, description="End time (optional)")
    is_all_day: bool = Field(default=False, description="Whether this is an all-day event")
    is_completed: bool = Field(default=False, description="Whether the entry is completed")


class FutureEntrySchema(FutureEntryCreate):
    """Complete future entry schema."""

    id: int = Field(..., description="Entry ID")
    user_id: int = Field(..., description="User ID")
    source: str = Field(..., description="Entry source (manual, bot, google)")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = ConfigDict(from_attributes=True)
