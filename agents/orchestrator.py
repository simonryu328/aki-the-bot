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

        # 3. Gather context
        context = await self.memory.get_user_context(user_id)
        history = await self.memory.db.get_recent_conversations(user_id, limit=20)

        # 4. Get companion response
        result = await self.agent.respond(
            user_id=user_id,
            message=message,
            context=context,
            conversation_history=history,
        )

        # 5. Store assistant response (full response, not split)
        await self.memory.add_conversation(
            user_id=user_id,
            role="assistant",
            message=result.response,
            thinking=result.thinking,
        )

        return result.messages, result.emoji


# Singleton instance
orchestrator = AgentOrchestrator()
