import asyncio
import sys
import os
from unittest.mock import MagicMock, patch, AsyncMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

async def test_log_toggling():
    print("\n--- Testing Log Level Toggling in SoulAgent ---")
    
    # Mock settings and logger
    mock_settings = MagicMock()
    mock_settings.MODEL_CONVERSATION = "test-model"
    mock_settings.LOG_RAW_LLM = True
    mock_settings.TIMEZONE = "UTC"
    mock_settings.MEMORY_ENTRY_LIMIT = 5
    mock_settings.DIARY_FETCH_LIMIT = 10
    mock_settings.CONVERSATION_CONTEXT_LIMIT = 10
    mock_settings.OBSERVATION_DISPLAY_LIMIT = 5
    mock_settings.AUTO_SPLIT_THRESHOLD = 500
    
    mock_soul_logger = MagicMock()
    mock_llm_logger = MagicMock()
    
    # Setup mock LLM response
    mock_llm_response = MagicMock()
    mock_llm_response.content = "<thinking>Think</thinking><response>Hello</response>"
    mock_llm_response.total_tokens = 50

    with patch('agents.soul_agent.settings', mock_settings), \
         patch('agents.soul_agent.logger', mock_soul_logger), \
         patch('utils.llm_client.logger', mock_llm_logger), \
         patch('utils.llm_client.llm_client.chat_with_system_and_usage', return_value=mock_llm_response), \
         patch('agents.soul_agent.memory_manager') as mock_memory:
        
        # Mock memory methods as AsyncMocks
        mock_memory.get_diary_entries = AsyncMock(return_value=[])
        mock_memory.get_user_by_id = AsyncMock(return_value=None)
        mock_memory.get_observations_with_dates = AsyncMock(return_value=[])
        mock_memory._profile_cache = {}
        
        from agents.soul_agent import SoulAgent
        
        # Mocking random-dependent method to avoid seed/mock range errors
        with patch.object(SoulAgent, '_should_trigger_reaction', return_value=False):
            agent = SoulAgent()
            
            # Test Case A: LOG_RAW_LLM = True (Expect INFO in SoulAgent)
            print("Test A: LOG_RAW_LLM = True")
            mock_settings.LOG_RAW_LLM = True
            mock_soul_logger.reset_mock()
            mock_llm_logger.reset_mock()
            
            mock_context = MagicMock()
            mock_context.user_info.id = 1
            mock_context.user_info.name = "Test User"
            
            await agent.respond(user_id=1, message="hi", context=mock_context, conversation_history=[])
            
            # Check SoulAgent logs
            soul_info_calls = [call.args[0] for call in mock_soul_logger.info.call_args_list]
            print(f"SoulAgent INFO calls: {soul_info_calls}")
            assert "Raw response before parsing" in soul_info_calls
            
            # Check LLMClient logs (should NOT have LLM preview at INFO)
            llm_info_calls = [call.args[0] for call in mock_llm_logger.info.call_args_list]
            print(f"LLMClient INFO calls: {llm_info_calls}")
            assert "LLM response preview" not in llm_info_calls
            
            print("✅ Test A passed: Raw response at INFO only in SoulAgent")
            
            # Test Case B: LOG_RAW_LLM = False (Expect DEBUG in SoulAgent)
            print("\nTest B: LOG_RAW_LLM = False")
            mock_settings.LOG_RAW_LLM = False
            mock_soul_logger.reset_mock()
            
            await agent.respond(user_id=1, message="hi", context=mock_context, conversation_history=[])
            
            soul_info_calls = [call.args[0] for call in mock_soul_logger.info.call_args_list]
            print(f"SoulAgent INFO calls: {soul_info_calls}")
            assert "Raw response before parsing" not in soul_info_calls
            
            soul_debug_calls = [call.args[0] for call in mock_soul_logger.debug.call_args_list]
            assert "Raw response before parsing" in soul_debug_calls
            print("✅ Test B passed: Raw response moved to DEBUG")

if __name__ == "__main__":
    asyncio.run(test_log_toggling())
