import pytest
import re
from typing import Optional, List
from unittest.mock import MagicMock
from agents.soul_agent import SoulAgent

@pytest.fixture
def agent():
    return SoulAgent()

def test_parse_response_with_sticker(agent):
    raw_response = """
    <thinking>I should send a warm greeting with a sticker.</thinking>
    <emoji>😊</emoji>
    <sticker>warm_welcome</sticker>
    <response>Hello there! I'm so glad to see you.</response>
    """
    
    thinking, full_response, messages, emoji, sticker = agent._parse_response(raw_response)
    
    assert thinking == "I should send a warm greeting with a sticker."
    assert emoji == "😊"
    assert sticker == "warm_welcome"
    assert "Hello there!" in full_response
    assert len(messages) == 1

def test_parse_response_mixed_format(agent):
    raw_response = """
    <thinking>Monologue here...</thinking>
    Some text before the tag.
    <sticker>hug_sticker</sticker>
    <response>First message[BREAK]Second message</response>
    """
    
    thinking, full_response, messages, emoji, sticker = agent._parse_response(raw_response)
    
    assert sticker == "hug_sticker"
    assert len(messages) == 2
    assert messages[0] == "First message"
    assert messages[1] == "Second message"

def test_parse_response_no_sticker(agent):
    raw_response = "<response>Just text</response>"
    thinking, full_response, messages, emoji, sticker = agent._parse_response(raw_response)
    
    assert sticker is None
    assert messages == ["Just text"]
