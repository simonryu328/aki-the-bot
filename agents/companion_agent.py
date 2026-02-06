"""
Companion Agent - A witness to someone's story.

Inspired by soul.md: Not a chatbot, not an assistant. A companion who
listens for what's beneath the words, recognizes weight, and holds the story.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import re
import hashlib
import pytz
import dateparser

from utils.llm_client import llm_client
from config.settings import settings
from memory.memory_manager_async import memory_manager
from schemas import ConversationSchema, UserContextSchema
from core import get_logger
from prompts import (
    COMPANION_SYSTEM_PROMPT,
    OBSERVATION_PROMPT,
    REFLECTION_PROMPT,
    PROFILE_SUMMARY_PROMPT,
)

logger = get_logger(__name__)


@dataclass
class CompanionResponse:
    """Response from the companion agent."""
    response: str  # Full response (for storage)
    messages: List[str] = None  # Split messages (for sending)
    thinking: Optional[str] = None
    observations: Optional[List[str]] = None

    def __post_init__(self):
        if self.messages is None:
            self.messages = [self.response]


class CompanionAgent:
    """
    A companion who witnesses someone's story.

    Not an assistant. Not a chatbot. A presence that listens,
    understands, and remembers what matters.
    """

    # Store last thinking per user for debugging
    _last_thinking: Dict[int, str] = {}

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        """Initialize companion agent.

        Using Claude for better structured output compliance (thinking tags).
        Set ANTHROPIC_API_KEY in environment.
        """
        self.model = model
        self.memory = memory_manager

    async def respond(
        self,
        user_id: int,
        message: str,
        context: UserContextSchema,
        conversation_history: List[ConversationSchema],
    ) -> CompanionResponse:
        """
        Respond to a message as a companion.

        Args:
            user_id: User ID
            message: What they said
            context: Their profile and context
            conversation_history: Recent conversation

        Returns:
            CompanionResponse with response, thinking, and any observations
        """
        # Build context strings
        profile_context = self._build_profile_context(context)
        history_text = self._format_history(conversation_history)

        # Build time context
        now = datetime.now(pytz.timezone(settings.TIMEZONE))
        current_time = now.strftime("%A, %B %d at %I:%M %p")
        hour = now.hour
        if 5 <= hour < 12:
            time_context = "It's morning."
        elif 12 <= hour < 17:
            time_context = "It's afternoon."
        elif 17 <= hour < 21:
            time_context = "It's evening."
        else:
            time_context = "It's late night."

        # Generate response with reflection
        system_prompt = COMPANION_SYSTEM_PROMPT.format(
            current_time=current_time,
            time_context=time_context,
            profile_context=profile_context,
            conversation_history=history_text,
        )

        raw_response = await llm_client.chat_with_system(
            model=self.model,
            system_prompt=system_prompt,
            user_message=message,
            temperature=0.7,
            max_tokens=500,
        )

        # Parse thinking, response, and messages
        thinking, response, messages = self._parse_response(raw_response)

        # Store thinking for debug
        CompanionAgent._last_thinking[user_id] = thinking or "(no thinking captured)"

        logger.debug(
            "Companion response generated",
            user_id=user_id,
            has_thinking=bool(thinking),
            response_length=len(response),
            message_count=len(messages),
        )

        result = CompanionResponse(
            response=response,
            messages=messages,
            thinking=thinking,
        )

        # Background: Check if anything significant should be remembered
        # (Fire and forget - don't block the response)
        import asyncio
        asyncio.create_task(
            self._maybe_store_observations(
                user_id=user_id,
                profile_context=profile_context,
                user_message=message,
                assistant_response=response,
                thinking=thinking or "",
            )
        )

        return result

    def _build_profile_context(self, context: UserContextSchema) -> str:
        """Build a narrative profile context, not a data dump."""
        parts = []

        # Name
        if context.user_info.name:
            parts.append(f"Their name is {context.user_info.name}.")

        # Profile facts as narrative
        if context.profile:
            for category, facts in context.profile.items():
                if category == "system":
                    continue  # Skip system facts
                if facts:
                    for value in facts.values():
                        # Add observation directly (keys are now hashes)
                        parts.append(f"- {value}")

        if not parts:
            return "(You're just getting to know them. This is early in the story.)"

        return "\n".join(parts)

    def _format_history(self, conversations: List[ConversationSchema]) -> str:
        """Format conversation history."""
        if not conversations:
            return "(This is the beginning of your conversation.)"

        lines = []
        for conv in conversations[-20:]:  # Last 20 messages
            role = "Them" if conv.role == "user" else "You"
            lines.append(f"{role}: {conv.message}")

        return "\n".join(lines)

    def _parse_response(self, raw: str) -> tuple[Optional[str], str, List[str]]:
        """Parse thinking, response, and multiple messages from raw LLM output."""
        thinking = None
        response = raw

        # Extract thinking
        thinking_match = re.search(r'<thinking>(.*?)</thinking>', raw, re.DOTALL)
        if thinking_match:
            thinking = thinking_match.group(1).strip()
            # Remove thinking from response
            response = re.sub(r'<thinking>.*?</thinking>', '', raw, flags=re.DOTALL).strip()

        # Split into multiple messages if ||| separator is used
        if '|||' in response:
            messages = [msg.strip() for msg in response.split('|||') if msg.strip()]
        else:
            messages = [response]

        # Full response for storage (join with newlines)
        full_response = '\n'.join(messages)

        return thinking, full_response, messages

    def _parse_when_to_datetime(self, when: str) -> datetime:
        """Convert a 'when' string to a naive datetime object (for database storage).

        Tries in order:
        1. ISO 8601 format (YYYY-MM-DDTHH:MM)
        2. Natural language via dateparser
        3. Legacy hardcoded options (tomorrow_morning, etc.)
        4. Default to 24 hours from now
        """
        tz = pytz.timezone(settings.TIMEZONE)
        now = datetime.now(tz)
        when_stripped = when.strip()
        when_lower = when_stripped.lower()

        # 1. Try ISO 8601 format first (e.g., 2026-02-05T10:00)
        try:
            # Try with time
            if 'T' in when_stripped:
                parsed = datetime.fromisoformat(when_stripped)
                # If no timezone, assume local timezone
                if parsed.tzinfo is None:
                    parsed = tz.localize(parsed)
                logger.debug("Parsed ISO timestamp", when=when_stripped, result=parsed.isoformat())
                return parsed.replace(tzinfo=None)
        except ValueError:
            pass

        # 2. Try dateparser for natural language (e.g., "tomorrow at 10am", "in 3 hours")
        try:
            parsed = dateparser.parse(
                when_stripped,
                settings={
                    'TIMEZONE': settings.TIMEZONE,
                    'RETURN_AS_TIMEZONE_AWARE': True,
                    'PREFER_DATES_FROM': 'future',
                }
            )
            if parsed:
                logger.debug("Parsed natural language time", when=when_stripped, result=parsed.isoformat())
                return parsed.replace(tzinfo=None)
        except Exception as e:
            logger.debug("dateparser failed", when=when_stripped, error=str(e))

        # 3. Legacy hardcoded options (for backwards compatibility)
        if when_lower == "tomorrow_morning":
            target = now.replace(hour=9, minute=0, second=0, microsecond=0)
            if now.hour >= 9:
                target = target + timedelta(days=1)
        elif when_lower == "tomorrow_evening":
            target = now.replace(hour=19, minute=0, second=0, microsecond=0)
            if now.hour >= 19:
                target = target + timedelta(days=1)
        elif when_lower == "in_24h":
            target = now + timedelta(hours=24)
        elif when_lower == "in_few_days":
            target = now + timedelta(days=3)
        elif when_lower == "next_week":
            target = now + timedelta(days=7)
        else:
            # 4. Default to 24 hours from now
            logger.warning("Could not parse time, defaulting to 24h", when=when_stripped)
            target = now + timedelta(hours=24)

        return target.replace(tzinfo=None)

    async def _maybe_store_observations(
        self,
        user_id: int,
        profile_context: str,
        user_message: str,
        assistant_response: str,
        thinking: str,
    ) -> None:
        """Check if anything significant should be stored or followed up on."""
        logger.info("Running observation agent", user_id=user_id, user_message=user_message[:50])
        try:
            # Get current time for the observation prompt
            tz = pytz.timezone(settings.TIMEZONE)
            now = datetime.now(tz)
            current_time = now.strftime("%Y-%m-%d %H:%M (%A)")

            prompt = OBSERVATION_PROMPT.format(
                current_time=current_time,
                profile_context=profile_context,
                user_message=user_message,
                assistant_response=assistant_response,
                thinking=thinking,
            )

            result = await llm_client.chat(
                model="gpt-4o-mini",  # Cheaper model for observation
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
            )

            # Log the raw observation result for debugging
            logger.info("Observation agent raw result", user_id=user_id, result=result[:200])

            if "NOTHING_SIGNIFICANT" in result:
                logger.info("No significant observations from this exchange", user_id=user_id)
                return

            # Parse observations and follow-ups
            for line in result.strip().split("\n"):
                line = line.strip()

                if line.startswith("OBSERVATION:"):
                    try:
                        content = line.replace("OBSERVATION:", "").strip()
                        parts = content.split("|", 1)
                        if len(parts) == 2:
                            category = parts[0].strip()
                            observation = parts[1].strip()

                            # Use hash as key to avoid truncation issues
                            obs_hash = hashlib.md5(observation.encode()).hexdigest()[:8]
                            await self.memory.add_profile_fact(
                                user_id=user_id,
                                category=category,
                                key=obs_hash,
                                value=observation,
                                confidence=0.8,
                            )
                            logger.info(
                                "Stored observation",
                                user_id=user_id,
                                category=category,
                                observation=observation[:50],
                            )
                    except Exception as e:
                        logger.warning("Failed to parse observation line", line=line, error=str(e))

                elif line.startswith("FOLLOW_UP:"):
                    try:
                        content = line.replace("FOLLOW_UP:", "").strip()
                        parts = content.split("|")
                        if len(parts) >= 3:
                            when = parts[0].strip()
                            topic = parts[1].strip()
                            context = parts[2].strip()

                            scheduled_time = self._parse_when_to_datetime(when)

                            # Store as scheduled message with raw observation format
                            raw_line = f"FOLLOW_UP: {when} | {topic} | {context}"
                            await self.memory.add_scheduled_message(
                                user_id=user_id,
                                scheduled_time=scheduled_time,
                                message_type="follow_up",
                                context=f"{topic}: {context}",
                                message=raw_line,  # Store raw observation output
                            )
                            logger.info(
                                "Scheduled follow-up",
                                user_id=user_id,
                                topic=topic,
                                scheduled_time=scheduled_time.isoformat(),
                            )
                    except Exception as e:
                        logger.warning("Failed to parse follow-up line", line=line, error=str(e))

        except Exception as e:
            logger.error("Failed to process observations", user_id=user_id, error=str(e))

    async def generate_reflection(
        self,
        user_id: int,
        user_name: str,
        recent_observations: List[str],
        recent_conversations: str = "",
    ) -> Optional[str]:
        """
        Generate a reflection message for the user.

        Args:
            user_id: User ID
            user_name: User's name
            recent_observations: List of recent observations with timestamps
            recent_conversations: Formatted recent conversation history

        Returns:
            The reflection message, or None if generation fails
        """
        try:
            # Format observations
            observations_text = "\n".join(f"- {obs}" for obs in recent_observations)
            if not observations_text:
                observations_text = "(Nothing specific noted yet)"

            prompt = REFLECTION_PROMPT.format(
                name=user_name,
                recent_conversations=recent_conversations,
                recent_observations=observations_text,
            )

            reflection = await llm_client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You're texting a friend. Keep it short and real. No therapy-speak."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.8,
                max_tokens=300,  # Keep it short
            )

            # Strip quotes if LLM wrapped the response in them
            reflection = reflection.strip().strip('"').strip("'")
            logger.info("Generated reflection", user_id=user_id, length=len(reflection))
            return reflection

        except Exception as e:
            logger.error("Failed to generate reflection", user_id=user_id, error=str(e))
            return None

    async def generate_profile_summary(
        self,
        user_id: int,
        user_name: str,
        observations_with_dates: List[str],
        recent_reflections: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Generate a profile summary from observations and reflections.

        Args:
            user_id: User ID
            user_name: User's name
            observations_with_dates: List of observations with their dates
            recent_reflections: Recent reflections (if any)

        Returns:
            The profile summary text, or None if generation fails
        """
        try:
            # Format observations
            observations_text = "\n".join(f"- {obs}" for obs in observations_with_dates)
            if not observations_text:
                return None  # Can't summarize nothing

            # Format reflections section
            if recent_reflections:
                reflections_section = "RECENT REFLECTIONS:\n" + "\n---\n".join(recent_reflections)
            else:
                reflections_section = ""

            prompt = PROFILE_SUMMARY_PROMPT.format(
                name=user_name,
                observations_with_dates=observations_text,
                diary_section=reflections_section,
            )

            summary = await llm_client.chat(
                model="gpt-4o-mini",  # Cheaper model for summary
                messages=[
                    {"role": "system", "content": "You are summarizing what you know about someone you care about."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=600,
            )

            logger.info("Generated profile summary", user_id=user_id, length=len(summary))
            return summary.strip()

        except Exception as e:
            logger.error("Failed to generate profile summary", user_id=user_id, error=str(e))
            return None

    @classmethod
    def get_last_thinking(cls, user_id: int) -> Optional[str]:
        """Get the last thinking for a user (for debugging)."""
        return cls._last_thinking.get(user_id)


# Singleton instance
companion_agent = CompanionAgent()
