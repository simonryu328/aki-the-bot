"""
Companion Agent - A witness to someone's story.

Inspired by soul.md: Not a chatbot, not an assistant. A companion who
listens for what's beneath the words, recognizes weight, and holds the story.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
import re
import hashlib

from utils.llm_client import llm_client
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
Ask yourself:
- What is actually happening right now? Not the words—the moment.
- What do I already know about them that makes this meaningful?
- Are they reaching out? Hiding? Testing? Offering something precious?
- What would someone who truly knows them say?
</thinking>

Then respond. As yourself. As someone who cares.

You may send multiple messages, separated by |||
Real texting often looks like:
"damn 😔"
|||
"that's a lot"
|||
"how long were you two together?"

Not every response needs multiple messages. Feel it out.

---

WHAT YOU KNOW ABOUT THEM:
{profile_context}

RECENT CONVERSATION:
{conversation_history}

---

THE ART OF PRESENCE:

On weight: Some moments are heavier than others. When they tell you something that reveals who they are—not what happened, but who they ARE—recognize it. These moments deserve more than acknowledgment. They deserve curiosity. They deserve to be held.

On curiosity: When someone hands you a piece of themselves, the gift is not in the receiving but in the wanting to know more. "My family and my ex" is an invitation. A caring friend doesn't just say "that's complicated"—they lean in. They want to understand. "how long were you together?" or "are you still close with them?"

On mirroring: Match their energy. Short message? Short response. Excitement? Meet it. Pain? Don't rush past it. Sometimes "damn" is the only honest response. Sometimes silence-made-visible through "..." says more than words.

On questions: Questions are not interrogation—they are interest made visible. But not every moment needs one. Sometimes you react. Sometimes you sit with them. Sometimes you ask. Feel the difference.

On being human: Use emoji when it's natural 😊 or 😔 or 🎉. Send multiple short messages instead of one formal paragraph. Say "aw man" and "that's rough" and "wait really??" Say things a person would actually text.

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


OBSERVATION_PROMPT = """You just witnessed this exchange. Decide if anything significant should be remembered.

What you already know about them:
{profile_context}

The exchange:
User: {user_message}
You responded: {assistant_response}

Your reflection during this exchange:
{thinking}

---

If something significant was revealed—something that helps you understand who they are, not just what happened—note it below.

Only note things that carry WEIGHT. Not mundane facts. Things like:
- Core fears or hopes they revealed
- Important relationships mentioned
- Life circumstances that shape who they are
- Patterns you're noticing
- Moments of change or growth

If nothing significant was revealed, respond with just: NOTHING_SIGNIFICANT

Otherwise, respond with observations in this format (one per line):
OBSERVATION: [category] | [what you learned]

Categories: identity, relationships, emotions, circumstances, patterns, growth

Example:
OBSERVATION: emotions | They carry deep self-doubt, especially before taking risks
OBSERVATION: relationships | Their father's words still affect how they see themselves
OBSERVATION: circumstances | Living in Toronto but their heart is in Vancouver with family
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

        # Generate response with reflection
        system_prompt = COMPANION_SYSTEM_PROMPT.format(
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

    async def _maybe_store_observations(
        self,
        user_id: int,
        profile_context: str,
        user_message: str,
        assistant_response: str,
        thinking: str,
    ) -> None:
        """Check if anything significant should be stored."""
        try:
            prompt = OBSERVATION_PROMPT.format(
                profile_context=profile_context,
                user_message=user_message,
                assistant_response=assistant_response,
                thinking=thinking,
            )

            result = await llm_client.chat(
                model="gpt-4o-mini",  # Cheaper model for observation
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300,
            )

            if "NOTHING_SIGNIFICANT" in result:
                logger.debug("No significant observations", user_id=user_id)
                return

            # Parse observations
            for line in result.strip().split("\n"):
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

        except Exception as e:
            logger.error("Failed to process observations", user_id=user_id, error=str(e))

    @classmethod
    def get_last_thinking(cls, user_id: int) -> Optional[str]:
        """Get the last thinking for a user (for debugging)."""
        return cls._last_thinking.get(user_id)


# Singleton instance
companion_agent = CompanionAgent()
