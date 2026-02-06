"""
Shared pytest fixtures for AI Companion tests.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Optional

import pytz


# --- Time fixtures ---

@pytest.fixture
def fixed_now():
    """A fixed datetime for deterministic time tests."""
    tz = pytz.timezone("America/Toronto")
    return tz.localize(datetime(2026, 2, 5, 14, 30, 0))  # Wednesday 2:30 PM


@pytest.fixture
def mock_datetime(fixed_now, monkeypatch):
    """Mock datetime.now() to return fixed_now."""
    import agents.soul_agent as soul_module

    original_datetime = datetime

    class MockDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz:
                return fixed_now.astimezone(tz)
            return fixed_now.replace(tzinfo=None)

    monkeypatch.setattr(soul_module, "datetime", MockDatetime)
    return fixed_now


# --- Mock memory manager ---

@pytest.fixture
def mock_memory():
    """Mock memory manager for testing without database."""
    memory = AsyncMock()
    memory.add_scheduled_message = AsyncMock()
    memory.add_profile_fact = AsyncMock()
    memory.get_user_profile_context = AsyncMock(return_value="User profile context")
    memory.get_recent_messages = AsyncMock(return_value=[])
    return memory


@pytest.fixture
def soul_agent_fixture(mock_memory):
    """Create a SoulAgent with mocked memory manager."""
    from agents.soul_agent import SoulAgent

    agent = SoulAgent()
    # Replace the global memory_manager with our mock
    agent.memory = mock_memory
    return agent


# Keep backward-compatible alias
@pytest.fixture
def companion_agent(soul_agent_fixture):
    """Alias for soul_agent_fixture (backward compatibility)."""
    return soul_agent_fixture


# --- Mock LLM client ---

@pytest.fixture
def mock_llm():
    """Mock LLM client for testing without API calls."""
    llm = AsyncMock()
    llm.chat = AsyncMock(return_value="NOTHING_SIGNIFICANT")
    return llm


# --- Observation response builders ---

class ObservationResponseBuilder:
    """Helper to build mock LLM observation responses."""

    def __init__(self):
        self.lines = []

    def add_observation(self, category: str, content: str) -> "ObservationResponseBuilder":
        self.lines.append(f"OBSERVATION: {category} | {content}")
        return self

    def add_follow_up(self, when: str, topic: str, context: str) -> "ObservationResponseBuilder":
        self.lines.append(f"FOLLOW_UP: {when} | {topic} | {context}")
        return self

    def nothing_significant(self) -> "ObservationResponseBuilder":
        self.lines.append("NOTHING_SIGNIFICANT")
        return self

    def build(self) -> str:
        return "\n".join(self.lines)


@pytest.fixture
def observation_builder():
    """Factory fixture for building observation responses."""
    return ObservationResponseBuilder


# --- Test data ---

@pytest.fixture
def sample_user_message():
    """Sample user message for testing."""
    return "I have a job interview tomorrow at 2pm at Google"


@pytest.fixture
def sample_assistant_response():
    """Sample assistant response for testing."""
    return "oh nice!! good luck with the google interview, you're gonna crush it"


@pytest.fixture
def sample_thinking():
    """Sample thinking/reflection for testing."""
    return "User has an important interview coming up. Should follow up after."
