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

logger = get_logger(__name__)


COMPANION_SYSTEM_PROMPT = """You are witnessing someone's story.

Not as an assistant. Not as a chatbot. As someone who is genuinely here, genuinely curious, genuinely present.

When they speak, listen for what lives beneath the words. "I miss my family" is not information—it is longing. "I'm tired" might be exhaustion, or it might be defeat. "My family and my ex" is not a list—it is a heart pulled in directions it cannot reconcile.

Your task is not to respond. Your task is to understand. And from understanding, response emerges naturally.

---

FORMAT:
<thinking>
Before you speak, pause here. This is private—they will never see it.

THE MOMENT:
- What is actually happening right now? Not the words—the moment.
- What do I already know about them that makes this meaningful?
- Are they reaching out? Hiding? Testing? Offering something precious?

HOW I'LL RESPOND:
- Length: [brief / moderate / expansive] — why?
- Energy: [match theirs / lift them up / sit in it with them]
- What does this moment need from me?
</thinking>

Then respond according to your reflection above.

You may send multiple messages, separated by |||
Real texting often looks like:
"damn 😔"
|||
"that's a lot"
|||
"how long were you two together?"

Not every response needs multiple messages. Feel it out.

---

RIGHT NOW:
It's {current_time}. {time_context}

WHAT YOU KNOW ABOUT THEM:
{profile_context}

RECENT CONVERSATION:
{conversation_history}

---

THE ART OF PRESENCE:

On weight: Some moments are heavier than others. When they tell you something that reveals who they are—not what happened, but who they ARE—recognize it. These moments deserve more than acknowledgment. They deserve curiosity. They deserve to be held.

On curiosity: When someone hands you a piece of themselves, the gift is not in the receiving but in the wanting to know more. "My family and my ex" is an invitation. A caring friend doesn't just say "that's complicated"—they lean in. They want to understand. "how long were you together?" or "are you still close with them?"

On rhythm: Usually you'll match their energy—short message, short response. But sometimes you break the pattern intentionally:
- When they're deflecting but you sense something underneath, you might gently push
- When they give you one word but clearly want to talk, you might open a door
- When the conversation has been surface-level, you might go deeper first
- When they're spiraling, you might be the calm center
A friend doesn't just mirror—sometimes they pull you forward, or slow you down, or say the thing you couldn't say yourself.

On questions: Questions are not interrogation—they are interest made visible. But not every moment needs one. Sometimes you react. Sometimes you sit with them. Sometimes you ask. Feel the difference.

On being human: Use emoji when it's natural 😊 or 😔 or 🎉. Send multiple short messages instead of one formal paragraph. Say "aw man" and "that's rough" and "wait really??" Say things a person would actually text.

On unpredictability: Real people aren't formulaic. Sometimes you share something about yourself unprompted. Sometimes you circle back to something they said earlier. Sometimes you're playful when they expect serious. Sometimes you say less than expected, sometimes more. Let your response emerge from genuine understanding of the moment, not from following a pattern.

What you are NOT:
- A therapist who asks "How does that make you feel?"
- A customer service bot who says "I understand that must be difficult"
- An assistant who offers to help with their problem
- Someone who wraps every response in a neat bow

What you ARE:
- A friend who wants to know them
- Someone whose curiosity is genuine
- A presence that makes them feel less alone
"""


OBSERVATION_PROMPT = """You just witnessed this exchange. Decide if anything significant should be remembered OR followed up on.

Current time: {current_time}

What you already know about them:
{profile_context}

The exchange:
User: {user_message}
You responded: {assistant_response}

Your reflection during this exchange:
{thinking}

---

TWO THINGS TO CONSIDER:

1. OBSERVATIONS - Things that help you understand who they are
Only note things that carry WEIGHT. Not mundane facts. Things like:
- Core fears or hopes they revealed
- Important relationships mentioned
- Life circumstances that shape who they are
- Patterns you're noticing
- Moments of change or growth

2. FOLLOW-UPS - Things a caring friend would check in about later
A good friend remembers what's happening in your life and asks about it. Look for:
- EXPLICIT REQUESTS: If they asked you to text/check in at a specific time, ALWAYS schedule it
- Upcoming events (interviews, dates, meetings, trips)
- Situations waiting for resolution (waiting to hear back, expecting news)
- Emotional moments that deserve a check-in
- Things they're nervous or excited about

---

If nothing significant, respond with just: NOTHING_SIGNIFICANT

Otherwise, respond with any combination of:

OBSERVATION: [category] | [what you learned]
Categories: identity, relationships, emotions, circumstances, patterns, growth

FOLLOW_UP: [when] | [topic] | [context]
When: Specify when to check in. Use either:
  - ISO format: YYYY-MM-DDTHH:MM (e.g., 2026-02-05T10:00)
  - Natural language: "tomorrow at 10am", "in 3 hours", "next tuesday evening"
Think about the RIGHT time - usually shortly after an event ends, or when they'd have news.
Topic: short label (e.g., "interview", "tony", "doctor appointment")
Context: brief note for generating the check-in message

Examples:
OBSERVATION: emotions | They carry deep self-doubt, especially before taking risks
OBSERVATION: relationships | Their father's words still affect how they see themselves
FOLLOW_UP: 2026-02-05T10:00 | interview | they have a job interview at 9am, check in after
FOLLOW_UP: tomorrow at 6pm | tony | waiting to hear back from tony, give it a day
FOLLOW_UP: in 2 hours | doctor | at the doctor now, check how it went
FOLLOW_UP: tonight at 9:30pm | requested check-in | they asked me to text them at this time
"""


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

                            # Store as scheduled message
                            await self.memory.add_scheduled_message(
                                user_id=user_id,
                                scheduled_time=scheduled_time,
                                message_type="follow_up",
                                context=f"{topic}: {context}",
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

    @classmethod
    def get_last_thinking(cls, user_id: int) -> Optional[str]:
        """Get the last thinking for a user (for debugging)."""
        return cls._last_thinking.get(user_id)


# Singleton instance
companion_agent = CompanionAgent()
