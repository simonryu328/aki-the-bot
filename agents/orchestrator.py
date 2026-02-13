"""
Agent Orchestrator - Routes messages to the companion agent.

Simplified: No phases, no onboarding state. Just a deepening relationship.
"""

from typing import Optional, List

from memory.memory_manager_async import memory_manager
from agents.soul_agent import soul_agent
from core import get_logger

logger = get_logger(__name__)


class AgentOrchestrator:
    """
    Coordinates message flow to the companion agent.

    Flow:
    1. Get or create user
    2. Gather context (profile, history)
    3. Let the companion respond
    4. Store the conversation
    """

    def __init__(self):
        """Initialize orchestrator."""
        self.memory = memory_manager
        self.agent = soul_agent
        logger.info("Agent orchestrator initialized")

    async def process_message(
        self,
        telegram_id: int,
        message: str,
        name: Optional[str] = None,
        username: Optional[str] = None,
    ) -> tuple[List[str], Optional[str]]:
        """
        Process incoming message and return response messages and emoji.

        Args:
            telegram_id: Telegram user ID
            message: User's message text
            name: User's display name (optional)
            username: User's Telegram username (optional)

        Returns:
            Tuple of (response messages, emoji reaction or None)
        """
        # 1. Get or create user
        user = await self.memory.get_or_create_user(
            telegram_id=telegram_id,
            name=name,
            username=username,
        )
        user_id = user.id

        logger.info(
            "Processing message",
            user_id=user_id,
            telegram_id=telegram_id,
            message_preview=message[:50] if len(message) > 50 else message,
        )

        # 2. Store user message first
        await self.memory.add_conversation(
            user_id=user_id,
            role="user",
            message=message,
        )

        # 3. Gather context - fetch conversations once with limit=20
        # This will be reused in multiple places to avoid redundant queries
        history = await self.memory.db.get_recent_conversations(user_id, limit=20)
        
        # Get profile and events (user already fetched above, reuse it)
        profile = await self.memory.db.get_user_profile(user_id)
        events = await self.memory.db.get_upcoming_events(user_id, days=7)
        
        # Build context from already-fetched data
        from schemas import UserContextSchema
        context = UserContextSchema(
            user_info=user,
            profile=profile,
            recent_conversations=history[:10],  # Context uses first 10
            upcoming_events=events,
        )

        # 4. Check daily token budget
        from config.settings import settings
        if settings.USER_DAILY_TOKEN_BUDGET > 0:
            usage_today = await self.memory.db.get_user_token_usage_today(user_id)
            if usage_today >= settings.USER_DAILY_TOKEN_BUDGET:
                logger.warning(
                    "Token budget exceeded",
                    user_id=user_id,
                    usage_today=usage_today,
                    budget=settings.USER_DAILY_TOKEN_BUDGET,
                )
                return [
                    "You've given me so much to think about today! 🧠✨ Let's pause here so I can process everything. I'll be refreshed and ready to talk more tomorrow!"
                ], "😴"

        # 5. Get companion response - pass pre-fetched user and full history
        result = await self.agent.respond(
            user_id=user_id,
            message=message,
            context=context,
            conversation_history=history,  # Pass full 20 messages
            user=user,  # Pass pre-fetched user to avoid refetching
        )

        # 6. Store assistant response (full response, not split)
        await self.memory.add_conversation(
            user_id=user_id,
            role="assistant",
            message=result.response,
            thinking=result.thinking,
        )

        # 7. Record token usage (background, non-blocking)
        if result.usage and result.usage.total_tokens > 0:
            import asyncio
            asyncio.create_task(
                self.memory.record_token_usage(
                    user_id=user_id,
                    model=result.usage.model,
                    input_tokens=result.usage.input_tokens,
                    output_tokens=result.usage.output_tokens,
                    total_tokens=result.usage.total_tokens,
                    call_type="conversation",
                )
            )

        return result.messages, result.emoji


# Singleton instance
orchestrator = AgentOrchestrator()
