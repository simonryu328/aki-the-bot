"""User context schemas for AI interaction."""

from typing import List, Dict

from pydantic import BaseModel, Field

from schemas.user import UserSchema
from schemas.conversation import ConversationSchema
from schemas.timeline import TimelineEventSchema


class UserContextSchema(BaseModel):
    """Complete user context for AI agent interaction."""

    user_info: UserSchema = Field(..., description="User information")
    profile: Dict[str, Dict[str, str]] = Field(
        default_factory=dict,
        description="Profile facts organized by category",
    )
    recent_conversations: List[ConversationSchema] = Field(
        default_factory=list,
        description="Recent conversation history",
    )
    upcoming_events: List[TimelineEventSchema] = Field(
        default_factory=list,
        description="Upcoming timeline events",
    )

    def to_prompt_context(self) -> str:
        """
        Convert context to a formatted string for LLM prompt.

        Returns:
            Formatted context string
        """
        sections = []

        # User info
        sections.append("## User Information")
        sections.append(f"Name: {self.user_info.name or 'Unknown'}")
        sections.append(f"Username: @{self.user_info.username or 'Unknown'}")
        sections.append(f"Last interaction: {self.user_info.last_interaction.isoformat()}")

        # Profile
        if self.profile:
            sections.append("\n## User Profile")
            for category, facts in self.profile.items():
                sections.append(f"\n### {category.replace('_', ' ').title()}")
                for key, value in facts.items():
                    sections.append(f"- {key.replace('_', ' ').title()}: {value}")

        # Upcoming events
        if self.upcoming_events:
            sections.append("\n## Upcoming Events")
            for event in self.upcoming_events:
                sections.append(f"- {event.title} ({event.datetime.isoformat()})")
                if event.description:
                    sections.append(f"  {event.description}")

        # Recent conversations
        if self.recent_conversations:
            sections.append("\n## Recent Conversation History")
            for conv in self.recent_conversations[-5:]:  # Last 5 messages
                sections.append(f"{conv.role}: {conv.message}")

        return "\n".join(sections)
