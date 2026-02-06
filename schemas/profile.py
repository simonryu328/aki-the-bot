"""Profile fact schemas."""

from datetime import datetime
from typing import Dict

from pydantic import BaseModel, Field, ConfigDict, field_validator


class ProfileFactBaseSchema(BaseModel):
    """Base profile fact schema."""

    category: str = Field(
        ...,
        max_length=100,
        description="Fact category (e.g., 'basic_info', 'preferences', 'relationships')",
    )
    key: str = Field(..., max_length=255, description="Fact key (e.g., 'job', 'favorite_food')")
    value: str = Field(..., description="Fact value")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score (0.0 to 1.0)"
    )

    @field_validator("category", "key")
    @classmethod
    def validate_no_whitespace(cls, v: str) -> str:
        """Ensure no leading/trailing whitespace."""
        return v.strip()


class ProfileFactCreateSchema(ProfileFactBaseSchema):
    """Schema for creating a profile fact."""

    user_id: int = Field(..., description="User ID this fact belongs to")


class ProfileFactSchema(ProfileFactBaseSchema):
    """Complete profile fact schema."""

    id: int = Field(..., description="Profile fact ID")
    user_id: int = Field(..., description="User ID")
    observed_at: datetime = Field(..., description="When this was first observed")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class ProfileSchema(BaseModel):
    """Organized profile with facts grouped by category."""

    facts: Dict[str, Dict[str, str]] = Field(
        default_factory=dict,
        description="Profile facts organized as {category: {key: value}}",
    )
