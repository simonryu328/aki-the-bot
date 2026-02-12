"""Token usage tracking schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class TokenUsageCreateSchema(BaseModel):
    """Schema for recording token usage."""

    user_id: int = Field(..., description="User ID")
    model: str = Field(..., description="LLM model name")
    input_tokens: int = Field(..., ge=0, description="Input/prompt tokens")
    output_tokens: int = Field(..., ge=0, description="Output/completion tokens")
    total_tokens: int = Field(..., ge=0, description="Total tokens")
    call_type: str = Field(..., description="Type of LLM call (conversation, compact, observation, proactive, reach_out)")


class TokenUsageSchema(TokenUsageCreateSchema):
    """Complete token usage schema with ID and timestamp."""

    id: int = Field(..., description="Token usage record ID")
    timestamp: datetime = Field(..., description="When the call was made")

    model_config = ConfigDict(from_attributes=True)
