"""
Verification script for Anthropic Prompt Caching.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.soul_agent import SoulAgent
from utils.llm_client import LLMResponse

async def test_prompt_caching():
    """
    Verify that SoulAgent sends the correct caching headers/structure.
    """
    agent = SoulAgent(model="claude-3-5-sonnet-202410222")
    
    # Mock context and history
    mock_context = MagicMock()
    mock_context.user_info.name = "Test User"
    mock_context.profile = {}
    
    # Mock LLM response with caching metadata
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 1000
    mock_usage.completion_tokens = 100
    mock_usage.total_tokens = 1100
    mock_usage.cache_creation_input_tokens = 900
    mock_usage.cache_read_input_tokens = 0
    
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "<thinking>Thinking...</thinking><response>Hello!</response>"
    mock_response.choices[0].finish_reason = "stop"
    mock_response.usage = mock_usage
    
    # Patch litellm.acompletion to verify arguments
    with patch("litellm.acompletion", return_value=mock_response) as mock_acompletion:
        print("Testing prompt caching call structure...")
        
        await agent.respond(
            user_id=1,
            message="Hi Aki",
            context=mock_context,
            conversation_history=[]
        )
        
        # Verify call arguments
        args, kwargs = mock_acompletion.call_args
        messages = kwargs["messages"]
        extra_headers = kwargs.get("extra_headers", {})
        
        print(f"Model used: {kwargs['model']}")
        print(f"Number of messages: {len(messages)}")
        print(f"Headers: {extra_headers}")
        
        # Check system prompt structure
        system_msg = messages[0]
        assert system_msg["role"] == "system"
        assert isinstance(system_msg["content"], list)
        
        has_cache = any(isinstance(part, dict) and "cache_control" in part for part in system_msg["content"])
        print(f"System prompt has cache_control: {has_cache}")
        
        assert has_cache, "System prompt should have cache_control"
        assert extra_headers.get("anthropic-beta") == "prompt-caching-2024-07-31", "Should have Anthropic beta header"
        
        print("✅ Prompt caching call structure verified!")

if __name__ == "__main__":
    asyncio.run(test_prompt_caching())
