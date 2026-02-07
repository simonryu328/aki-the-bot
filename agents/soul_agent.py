"""
Soul Agent - The core conversational agent.

Accepts a swappable persona to define personality and behavior.
Inspired by soul.md: listens for what's beneath the words,
recognizes weight, and holds the story.
"""

from typing import List, Dict, Optional
from collections import defaultdict
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
    OBSERVATION_PROMPT,
    REFLECTION_PROMPT,
    COMPACT_PROMPT,
)
from prompts.condensation import CONDENSATION_PROMPT
from prompts.system_frame import SYSTEM_FRAME
from prompts.personas import FRIEND_PERSONA

logger = get_logger(__name__)


@dataclass
class SoulResponse:
    """Response from the companion agent."""
    response: str  # Full response (for storage)
    messages: List[str] = None  # Split messages (for sending)
    thinking: Optional[str] = None
    observations: Optional[List[str]] = None

    def __post_init__(self):
        if self.messages is None:
            self.messages = [self.response]


class SoulAgent:
    """
    A companion who witnesses someone's story.

    Not an assistant. Not a chatbot. A presence that listens,
    understands, and remembers what matters.
    """

    # Store last thinking, prompts, and context per user for debugging
    _last_thinking: Dict[int, str] = {}
    _last_system_prompt: Dict[int, str] = {}
    _last_observation_prompt: Dict[int, str] = {}
    _last_compact_prompt: Dict[int, str] = {}
    _last_profile_context: Dict[int, str] = {}
    _message_count: Dict[int, int] = {}
    _compact_message_count: Dict[int, int] = {}
    OBSERVATION_INTERVAL = 10  # Run observation agent every N exchanges
    COMPACT_INTERVAL = 10  # Run compact summarization every N exchanges

    def __init__(self, model: str = settings.MODEL_CONVERSATION, persona: str = FRIEND_PERSONA):
        """Initialize companion agent.

        Args:
            model: LLM model to use.
            persona: The personality prompt to slot into the system frame.
        """
        self.model = model
        self.persona = persona
        self.memory = memory_manager

    async def respond(
        self,
        user_id: int,
        message: str,
        context: UserContextSchema,
        conversation_history: List[ConversationSchema],
    ) -> SoulResponse:
        """
        Respond to a message as a companion.

        Args:
            user_id: User ID
            message: What they said
            context: Their profile and context
            conversation_history: Recent conversation

        Returns:
            SoulResponse with response, thinking, and any observations
        """
        # Build context strings
        profile_context = self._build_profile_context(context)
        SoulAgent._last_profile_context[user_id] = profile_context
        history_text = self._format_history(conversation_history)

        # Build observations context
        observations_with_dates = await memory_manager.get_observations_with_dates(user_id, limit=20)
        observations_text = "\n".join(f"- {obs}" for obs in observations_with_dates) if observations_with_dates else "(Still getting to know them)"

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

        # Assemble system prompt from frame + persona
        system_prompt = SYSTEM_FRAME.format(
            persona=self.persona,
            current_time=current_time,
            time_context=time_context,
            profile_context=profile_context,
            observations=observations_text,
            conversation_history=history_text,
        )
        SoulAgent._last_system_prompt[user_id] = system_prompt

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
        SoulAgent._last_thinking[user_id] = thinking or "(no thinking captured)"

        logger.debug(
            "Companion response generated",
            user_id=user_id,
            has_thinking=bool(thinking),
            response_length=len(response),
            message_count=len(messages),
        )

        result = SoulResponse(
            response=response,
            messages=messages,
            thinking=thinking,
        )

        # Background: Check if anything significant should be remembered
        # Only run every N exchanges to avoid excessive LLM calls
        import asyncio
        # DISABLED: Observation agent trigger
        # SoulAgent._message_count[user_id] = SoulAgent._message_count.get(user_id, 0) + 1
        # if SoulAgent._message_count[user_id] >= self.OBSERVATION_INTERVAL:
        #     SoulAgent._message_count[user_id] = 0
        #     asyncio.create_task(
        #         self._maybe_store_observations(
        #             user_id=user_id,
        #             profile_context=profile_context,
        #             user_message=message,
        #             assistant_response=response,
        #             thinking=thinking or "",
        #         )
        #     )

        # Background: Create compact summary of exchanges
        SoulAgent._compact_message_count[user_id] = SoulAgent._compact_message_count.get(user_id, 0) + 1
        if SoulAgent._compact_message_count[user_id] >= self.COMPACT_INTERVAL:
            SoulAgent._compact_message_count[user_id] = 0
            asyncio.create_task(
                self._create_compact_summary(
                    user_id=user_id,
                    profile_context=profile_context,
                )
            )

        return result

    def _build_profile_context(self, context: UserContextSchema) -> str:
        """Build profile context from static facts and condensed narratives."""
        parts = []

        # Name
        if context.user_info.name:
            parts.append(f"Their name is {context.user_info.name}.")

        if not context.profile:
            return "(You're just getting to know them. This is early in the story.)"

        # Static biographical facts
        if "static" in context.profile:
            for value in context.profile["static"].values():
                parts.append(f"- {value}")

        # Check for condensed narratives
        if "condensed" in context.profile:
            parts.append("")
            parts.append("YOUR UNDERSTANDING OF THEM:")
            for category, narrative in context.profile["condensed"].items():
                parts.append(f"[{category}] {narrative}")
        else:
            # Fall back to raw observations (pre-condensation)
            for category, facts in context.profile.items():
                if category in ("system", "static", "condensed"):
                    continue
                if facts:
                    for value in facts.values():
                        parts.append(f"- {value}")

        if not parts:
            return "(You're just getting to know them. This is early in the story.)"

        return "\n".join(parts)

    def _format_history(self, conversations: List[ConversationSchema]) -> str:
        """Format conversation history with timestamps converted to local time."""
        if not conversations:
            return "(This is the beginning of your conversation.)"

        tz = pytz.timezone(settings.TIMEZONE)
        lines = []
        for conv in conversations:
            role = "Them" if conv.role == "user" else "You"
            if conv.timestamp:
                utc_time = conv.timestamp.replace(tzinfo=pytz.utc)
                local_time = utc_time.astimezone(tz)
                ts = local_time.strftime("%Y-%m-%d %H:%M")
            else:
                ts = ""
            lines.append(f"[{ts}] {role}: {conv.message}")

        return "\n".join(lines)

    def _parse_response(self, raw: str) -> tuple[Optional[str], str, List[str]]:
        """Parse thinking, response, and multiple messages from raw LLM output.
        
        Supports two formats:
        1. XML: <response><message>text</message><message>text</message></response>
        2. Fallback: Plain text or ||| separator
        """
        thinking = None
        response = raw

        # Extract thinking
        thinking_match = re.search(r'<thinking>(.*?)</thinking>', raw, re.DOTALL)
        if thinking_match:
            thinking = thinking_match.group(1).strip()
            # Remove thinking from response
            response = re.sub(r'<thinking>.*?</thinking>', '', raw, flags=re.DOTALL).strip()

        # Try to extract structured <response> with <message> tags
        response_match = re.search(r'<response>(.*?)</response>', response, re.DOTALL)
        if response_match:
            response_content = response_match.group(1)
            # Extract individual <message> tags
            message_matches = re.findall(r'<message>(.*?)</message>', response_content, re.DOTALL)
            if message_matches:
                messages = [msg.strip() for msg in message_matches if msg.strip()]
            else:
                # <response> tag exists but no <message> tags - treat content as single message
                messages = [response_content.strip()]
        else:
            # Fallback: check for ||| separator or treat as single message
            if '|||' in response:
                messages = [msg.strip() for msg in response.split('|||') if msg.strip()]
            else:
                # Remove any stray <response> or <message> tags and use as-is
                clean_response = re.sub(r'</?(?:response|message)>', '', response).strip()
                messages = [clean_response] if clean_response else [response.strip()]

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

            # Get pending follow-ups so LLM knows what's already scheduled
            pending = await self.memory.get_user_scheduled_messages(user_id)
            if pending:
                pending_lines = []
                for msg in pending:
                    scheduled = msg.scheduled_time.strftime("%Y-%m-%d %H:%M")
                    pending_lines.append(f"- {scheduled}: {msg.context}")
                pending_followups = "\n".join(pending_lines)
            else:
                pending_followups = "(none)"

            # Get recent conversation for context (last 20 messages = ~10 exchanges)
            recent_convos = await self.memory.db.get_recent_conversations(user_id, limit=20)
            if recent_convos:
                convo_lines = []
                for conv in recent_convos:
                    role = "Them" if conv.role == "user" else "You"
                    if conv.timestamp:
                        utc_time = conv.timestamp.replace(tzinfo=pytz.utc)
                        local_time = utc_time.astimezone(tz)
                        ts = local_time.strftime("%Y-%m-%d %H:%M")
                    else:
                        ts = ""
                    convo_lines.append(f"[{ts}] {role}: {conv.message}")
                recent_conversation = "\n".join(convo_lines)
            else:
                recent_conversation = "(No prior conversation)"

            prompt = OBSERVATION_PROMPT.format(
                current_time=current_time,
                profile_context=profile_context,
                pending_followups=pending_followups,
                recent_conversation=recent_conversation,
                user_message=user_message,
                assistant_response=assistant_response,
                thinking=thinking,
            )
            SoulAgent._last_observation_prompt[user_id] = prompt

            result = await llm_client.chat(
                model=settings.MODEL_OBSERVATION,
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

            # Trigger condensation if enough raw observations and not yet condensed
            try:
                obs_count = await self.memory.db.get_observation_count(user_id)
                if obs_count >= 50:
                    profile = await self.memory.get_user_profile(user_id)
                    if "condensed" not in profile:
                        user = await self.memory.get_user_by_id(user_id)
                        user_name = user.name if user and user.name else "them"
                        logger.info("Triggering auto-condensation", user_id=user_id, obs_count=obs_count)
                        await self.compact_observations(user_id, user_name)
            except Exception as e:
                logger.error("Failed to check/run condensation", user_id=user_id, error=str(e))

        except Exception as e:
            logger.error("Failed to process observations", user_id=user_id, error=str(e))
    async def _create_compact_summary(
        self,
        user_id: int,
        profile_context: str,
    ) -> None:
        """Create a compact summary of recent message exchanges."""
        logger.info("Running compact summarization", user_id=user_id)
        try:
            tz = pytz.timezone(settings.TIMEZONE)
            
            # Get user name
            user = await self.memory.get_user_by_id(user_id)
            user_name = user.name if user and user.name else "them"
            
            # Get recent conversation (last 20 messages = ~10 exchanges)
            recent_convos = await self.memory.db.get_recent_conversations(user_id, limit=20)
            if not recent_convos:
                logger.debug("No recent conversations to summarize", user_id=user_id)
                return
            
            # Extract start and end times from conversation objects
            first_conv = recent_convos[0]
            last_conv = recent_convos[-1]
            
            if first_conv.timestamp:
                utc_start = first_conv.timestamp.replace(tzinfo=pytz.utc)
                start_time = utc_start.astimezone(tz).strftime("%Y-%m-%d %H:%M")
            else:
                start_time = "unknown"
            
            if last_conv.timestamp:
                utc_end = last_conv.timestamp.replace(tzinfo=pytz.utc)
                end_time = utc_end.astimezone(tz).strftime("%Y-%m-%d %H:%M")
            else:
                end_time = "unknown"
            
            # Format conversations with timestamps
            convo_lines = []
            for conv in recent_convos:
                role = "Them" if conv.role == "user" else "You"
                if conv.timestamp:
                    utc_time = conv.timestamp.replace(tzinfo=pytz.utc)
                    local_time = utc_time.astimezone(tz)
                    ts = local_time.strftime("%Y-%m-%d %H:%M")
                else:
                    ts = ""
                convo_lines.append(f"[{ts}] {role}: {conv.message}")
            recent_conversation = "\n".join(convo_lines)
            
            # Build prompt with explicit start/end times
            prompt = COMPACT_PROMPT.format(
                user_name=user_name,
                profile_context=profile_context,
                start_time=start_time,
                end_time=end_time,
                recent_conversation=recent_conversation,
            )
            SoulAgent._last_compact_prompt[user_id] = prompt
            
            # Generate summary
            result = await llm_client.chat(
                model=settings.MODEL_SUMMARY,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300,
            )
            
            logger.info("Compact summary generated", user_id=user_id, summary_length=len(result))
            
            # Store summary as a diary entry with type "compact_summary"
            if result and "SUMMARY:" in result:
                # Extract the summary content
                summary_content = result.split("SUMMARY:", 1)[1].strip()
                
                # Convert start/end times back to datetime objects for storage
                exchange_start_dt = None
                exchange_end_dt = None
                if first_conv.timestamp:
                    exchange_start_dt = first_conv.timestamp  # Store as UTC
                if last_conv.timestamp:
                    exchange_end_dt = last_conv.timestamp  # Store as UTC
                
                # Store in diary entries with exchange timestamps
                await self.memory.add_diary_entry(
                    user_id=user_id,
                    entry_type="compact_summary",
                    title="Conversation Summary",
                    content=summary_content,
                    importance=5,  # Medium importance
                    exchange_start=exchange_start_dt,
                    exchange_end=exchange_end_dt,
                )
                
                logger.info("Stored compact summary", user_id=user_id,
                           exchange_start=start_time, exchange_end=end_time)
            
        except Exception as e:
            logger.error("Failed to create compact summary", user_id=user_id, error=str(e))


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

    async def compact_observations(self, user_id: int, user_name: str) -> dict:
        """Condense raw observations into persona-driven narratives per category.

        Args:
            user_id: User ID
            user_name: User's name for the condensation prompt

        Returns:
            Dict of {category: condensed_narrative}
        """
        try:
            # Fetch all observations
            all_obs = await self.memory.db.get_all_observations(user_id, limit=1000)
            if not all_obs:
                return {}

            # Group by category
            grouped = defaultdict(list)
            for obs in all_obs:
                grouped[obs.category].append(obs)

            # Extract static facts for context
            static_lines = []
            if "static" in grouped:
                for obs in grouped["static"]:
                    if ":" in obs.value:
                        key, value = obs.value.split(":", 1)
                        static_lines.append(f"{key.strip().capitalize()}: {value.strip()}")
                    else:
                        static_lines.append(obs.value)

            static_context = "\n".join(static_lines) if static_lines else "(Still learning about them)"

            # Persona voice for condensation
            persona_name = "their companion"
            persona_description = (
                "Someone who is genuinely here, genuinely curious, genuinely present. "
                "You write like a caring friend keeping a journal — natural, warm, observant."
            )

            # Condense each dynamic category
            tz = pytz.timezone(settings.TIMEZONE)
            condensed = {}
            categories_to_condense = [
                c for c in grouped.keys()
                if c not in ("static", "condensed", "system")
            ]

            for category in categories_to_condense:
                observations = grouped[category]

                # Format observations with timestamps
                timestamped = []
                for obs in observations:
                    utc_time = obs.observed_at.replace(tzinfo=pytz.utc)
                    local_time = utc_time.astimezone(tz)
                    date_str = local_time.strftime("%Y-%m-%d")
                    timestamped.append(f"[{date_str}] {obs.value}")

                prompt = CONDENSATION_PROMPT.format(
                    persona_name=persona_name,
                    persona_description=persona_description,
                    user_name=user_name,
                    static_context=static_context,
                    category=category,
                    timestamped_observations="\n".join(timestamped),
                )

                result = await llm_client.chat(
                    model=settings.MODEL_SUMMARY,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5,
                    max_tokens=300,
                )

                condensed[category] = result.strip()

                # Store as condensed profile fact (overwrites previous)
                await self.memory.add_profile_fact(
                    user_id=user_id,
                    category="condensed",
                    key=category,
                    value=result.strip(),
                    confidence=1.0,
                )

                logger.info(
                    "Condensed observations",
                    user_id=user_id,
                    category=category,
                    raw_count=len(observations),
                    condensed_length=len(result.strip()),
                )

            return condensed

        except Exception as e:
            logger.error("Failed to compact observations", user_id=user_id, error=str(e))
            return {}

    @classmethod
    def get_last_thinking(cls, user_id: int) -> Optional[str]:
        """Get the last thinking for a user (for debugging)."""
        return cls._last_thinking.get(user_id)

    @classmethod
    def get_last_system_prompt(cls, user_id: int) -> Optional[str]:
        """Get the last companion system prompt for a user (for debugging)."""
        return cls._last_system_prompt.get(user_id)

    @classmethod
    def get_last_observation_prompt(cls, user_id: int) -> Optional[str]:
        """Get the last observation prompt for a user (for debugging)."""
        return cls._last_observation_prompt.get(user_id)

    @classmethod
    def get_last_profile_context(cls, user_id: int) -> Optional[str]:
        """Get the last profile context for a user (for debugging)."""
        return cls._last_profile_context.get(user_id)


# Singleton instance
soul_agent = SoulAgent()
