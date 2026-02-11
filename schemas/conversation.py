"""Conversation schemas."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


class ConversationBaseSchema(BaseModel):
    """Base conversation schema."""

    role: Literal["user", "assistant"] = Field(..., description="Message role")
    message: str = Field(..., min_length=1, description="Message content")


class ConversationCreateSchema(ConversationBaseSchema):
    """Schema for creating a conversation entry."""

    user_id: int = Field(..., description="User ID")


class ConversationSchema(ConversationBaseSchema):
    """Complete conversation schema."""

    id: int = Field(..., description="Conversation entry ID")
    user_id: int = Field(..., description="User ID")
    thinking: Optional[str] = Field(default=None, description="LLM thinking/reasoning")
    timestamp: datetime = Field(..., description="Message timestamp")

    model_config = ConfigDict(from_attributes=True)
