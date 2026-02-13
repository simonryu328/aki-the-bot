"""User context schemas for AI interaction."""

from typing import List, Dict, Optional, Any

from pydantic import BaseModel, Field

from schemas.user import UserSchema
from schemas.conversation import ConversationSchema
from schemas.diary import DiaryEntrySchema


class UserContextSchema(BaseModel):
    """Complete user context for AI agent interaction."""

    user_info: UserSchema = Field(..., description="User information")
    recent_conversations: List[ConversationSchema] = Field(
        default_factory=list,
        description="Recent conversation history",
    )
    diary_entries: List[DiaryEntrySchema] = Field(
        default_factory=list,
        description="Relevant diary entries and conversation memories",
    )
    profile: Optional[Dict[str, Any]] = Field(default=None, description="DEPRECATED: Placeholder for backwards compatibility")

    def to_prompt_context(self) -> str:
        """
        Convert context to a formatted string for LLM prompt.
        DEPRECATED: Context is now built dynamically in SoulAgent.

        Returns:
            Formatted context string
        """
        sections = []

        # User info
        sections.append("## User Information")
        sections.append(f"Name: {self.user_info.name or 'Unknown'}")
        sections.append(f"Username: @{self.user_info.username or 'Unknown'}")
        sections.append(f"Last interaction: {self.user_info.last_interaction.isoformat()}")

        # Recent conversations
        if self.recent_conversations:
            sections.append("\n## Recent Conversation History")
            for conv in self.recent_conversations[-5:]:  # Last 5 messages
                sections.append(f"{conv.role}: {conv.message}")

        return "\n".join(sections)
