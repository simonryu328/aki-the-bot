"""
LLM Client using LiteLLM for multi-provider support.

Supports: OpenAI, Anthropic, Cohere, and 100+ other providers.
Switch providers by changing the model string.

Examples:
    - "gpt-4o" (OpenAI)
    - "claude-3-5-sonnet-20241022" (Anthropic)
    - "command-r-plus" (Cohere)
"""

from typing import List, Dict, Optional, Any
import litellm
from tenacity import retry, stop_after_attempt, wait_exponential

from core import get_logger
from config.settings import settings

logger = get_logger(__name__)

# Configure LiteLLM
litellm.set_verbose = False  # Set True for debugging


class LLMClient:
    """
    Unified LLM client supporting multiple providers via LiteLLM.

    Usage:
        client = LLMClient()
        response = await client.chat("gpt-4o", messages=[...])

        # Switch to Anthropic:
        response = await client.chat("claude-3-5-sonnet-20241022", messages=[...])
    """

    # Default models per use case
    DEFAULT_CHAT_MODEL = "gpt-4o"
    DEFAULT_FAST_MODEL = "gpt-4o-mini"

    def __init__(self):
        """Initialize LLM client."""
        # LiteLLM automatically picks up API keys from environment:
        # - OPENAI_API_KEY
        # - ANTHROPIC_API_KEY
        # - COHERE_API_KEY
        # etc.
        logger.info("LLM client initialized")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> str:
        """
        Generate a chat completion.

        Args:
            model: Model identifier (e.g., "gpt-4o", "claude-3-5-sonnet-20241022")
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response
            **kwargs: Additional provider-specific parameters

        Returns:
            Generated response text

        Raises:
            Exception: If all retry attempts fail
        """
        logger.debug(
            "LLM request",
            model=model,
            message_count=len(messages),
            temperature=temperature,
        )

        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )

            content = response.choices[0].message.content
            finish_reason = response.choices[0].finish_reason

            logger.debug(
                "LLM response",
                model=model,
                tokens_used=response.usage.total_tokens if response.usage else None,
                response_length=len(content),
                finish_reason=finish_reason,
            )
            
            # Log full raw response for debugging
            logger.info(
                "Raw LLM response (full)",
                model=model,
                finish_reason=finish_reason,
                raw_response=content,
            )
            
            # Warn if response was cut off
            if finish_reason == "length":
                logger.warning(
                    "Response truncated by max_tokens limit",
                    model=model,
                    max_tokens=max_tokens,
                    completion_tokens=response.usage.completion_tokens if response.usage else None,
                )

            return content

        except Exception as e:
            logger.error("LLM request failed", model=model, error=str(e))
            raise

    async def chat_with_system(
        self,
        model: str,
        system_prompt: str,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> str:
        """
        Convenience method for chat with system prompt.

        Args:
            model: Model identifier
            system_prompt: System instructions
            user_message: Current user message
            conversation_history: Optional previous messages
            **kwargs: Additional parameters

        Returns:
            Generated response text
        """
        messages = [{"role": "system", "content": system_prompt}]

        if conversation_history:
            messages.extend(conversation_history)

        messages.append({"role": "user", "content": user_message})

        return await self.chat(model=model, messages=messages, **kwargs)


# Singleton instance
llm_client = LLMClient()
