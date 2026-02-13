"""
LLM Client using LiteLLM for multi-provider support.

Supports: OpenAI, Anthropic, Cohere, and 100+ other providers.
Switch providers by changing the model string.

Examples:
    - "gpt-4o" (OpenAI)
    - "claude-3-5-sonnet-20241022" (Anthropic)
    - "command-r-plus" (Cohere)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import litellm
from tenacity import retry, stop_after_attempt, wait_exponential

from core import get_logger
from config.settings import settings

logger = get_logger(__name__)

# Configure LiteLLM
litellm.set_verbose = False  # Set True for debugging


@dataclass
class LLMResponse:
    """Response from an LLM call, including content and token usage."""
    content: str
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


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
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> str:
        """
        Generate a chat completion.

        Args:
            model: Model identifier
            messages: List of message dicts (now allows Any for content lists/dicts)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            **kwargs: Additional parameters

        Returns:
            Generated response text
        """
        # Check if any message part has cache_control (Anthropic specific)
        has_cache_control = False
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and "cache_control" in part:
                        has_cache_control = True
                        break
            if has_cache_control:
                break

        # Anthropic caching requires a beta header if using cache_control
        if has_cache_control and "claude" in model.lower():
            if "extra_headers" not in kwargs:
                kwargs["extra_headers"] = {}
            kwargs["extra_headers"]["anthropic-beta"] = "prompt-caching-2024-07-31"

        logger.debug(
            "LLM request",
            model=model,
            message_count=len(messages),
            temperature=temperature,
            caching=has_cache_control,
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
                cache_read=getattr(response.usage, "cache_read_input_tokens", 0),
                cache_creation=getattr(response.usage, "cache_creation_input_tokens", 0),
                response_length=len(content),
                finish_reason=finish_reason,
            )
            
            # Log truncated response for debugging at DEBUG level
            if len(content) > 200:
                truncated = f"{content[:100]}...{content[-100:]}"
            else:
                truncated = content
            
            logger.debug(
                "LLM response preview",
                model=model,
                finish_reason=finish_reason,
                response_preview=truncated,
            )
            
            return content

        except Exception as e:
            logger.error("LLM request failed", model=model, error=str(e))
            raise

    async def chat_with_usage(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Generate a chat completion and return content + usage metadata.
        """
        # Check if any message part has cache_control (Anthropic specific)
        has_cache_control = False
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and "cache_control" in part:
                        has_cache_control = True
                        break
            if has_cache_control:
                break

        # Anthropic caching requires a beta header if using cache_control
        if has_cache_control and "claude" in model.lower():
            if "extra_headers" not in kwargs:
                kwargs["extra_headers"] = {}
            kwargs["extra_headers"]["anthropic-beta"] = "prompt-caching-2024-07-31"

        logger.debug(
            "LLM request (with usage)",
            model=model,
            message_count=len(messages),
            temperature=temperature,
            caching=has_cache_control,
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
            usage = response.usage

            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0
            total_tokens = usage.total_tokens if usage else 0

            # Caching metadata
            cache_read = getattr(usage, "cache_read_input_tokens", 0)
            cache_creation = getattr(usage, "cache_creation_input_tokens", 0)

            logger.debug(
                "LLM response (with usage)",
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cache_read=cache_read,
                cache_creation=cache_creation,
                finish_reason=finish_reason,
            )

            if len(content) > 200:
                truncated = f"{content[:100]}...{content[-100:]}"
            else:
                truncated = content

            logger.debug(
                "LLM response preview",
                model=model,
                finish_reason=finish_reason,
                response_preview=truncated,
            )

            return LLMResponse(
                content=content,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            )

        except Exception as e:
            logger.error("LLM request failed", model=model, error=str(e))
            raise

    async def chat_with_system(
        self,
        model: str,
        system_prompt: str | List[Dict[str, Any]],
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> str:
        """
        Convenience method for chat with system prompt.
        Allows system_prompt to be a string or a list of content blocks (for caching).
        """
        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]

        if conversation_history:
            messages.extend(conversation_history)

        messages.append({"role": "user", "content": user_message})

        return await self.chat(model=model, messages=messages, **kwargs)

    async def chat_with_system_and_usage(
        self,
        model: str,
        system_prompt: str | List[Dict[str, Any]],
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Convenience method for chat with system prompt, returning usage metadata.
        Allows system_prompt to be a string or a list of content blocks (for caching).
        """
        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]

        if conversation_history:
            messages.extend(conversation_history)

        messages.append({"role": "user", "content": user_message})

        return await self.chat_with_usage(model=model, messages=messages, **kwargs)


# Singleton instance
llm_client = LLMClient()
