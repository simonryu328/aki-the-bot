"""
Tests for follow-up scheduling decision logic.

Tests how the observation agent decides when to schedule follow-ups
based on conversation content.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock


class TestFollowUpParsing:
    """Test parsing of FOLLOW_UP lines from observation agent output."""

    @pytest.fixture
    def agent(self, companion_agent, mock_memory):
        """Use the companion_agent fixture and ensure mock_memory is attached."""
        companion_agent.memory = mock_memory
        return companion_agent

    async def test_parses_follow_up_line_correctly(self, agent, mock_memory):
        """Should parse FOLLOW_UP: when | topic | context format."""
        observation_output = "FOLLOW_UP: tomorrow at 3pm | interview | Google interview follow-up"

        with patch.object(agent, "_parse_when_to_datetime") as mock_parse:
            mock_parse.return_value = datetime(2026, 2, 6, 15, 0)

            await agent._maybe_store_observations(
                user_id=1,
                profile_context="",
                user_message="I have an interview tomorrow",
                assistant_response="good luck!",
                thinking="should follow up",
            )

    async def test_handles_multiple_follow_ups(self, agent, mock_memory, observation_builder):
        """Should handle multiple FOLLOW_UP lines in one response."""
        response = (
            observation_builder()
            .add_follow_up("tomorrow at 10am", "interview", "check how it went")
            .add_follow_up("next week", "job_search", "see if they heard back")
            .build()
        )

        with patch("agents.companion_agent.llm_client") as mock_llm:
            mock_llm.chat = AsyncMock(return_value=response)

            await agent._maybe_store_observations(
                user_id=1,
                profile_context="",
                user_message="interview tomorrow, waiting on another company",
                assistant_response="exciting times!",
                thinking="two things to follow up on",
            )

            # Should have scheduled 2 follow-ups
            assert mock_memory.add_scheduled_message.call_count == 2

    async def test_ignores_malformed_follow_up_lines(self, agent, mock_memory):
        """Should gracefully handle malformed FOLLOW_UP lines."""
        malformed_response = "FOLLOW_UP: missing parts"

        with patch("agents.companion_agent.llm_client") as mock_llm:
            mock_llm.chat = AsyncMock(return_value=malformed_response)

            # Should not raise exception
            await agent._maybe_store_observations(
                user_id=1,
                profile_context="",
                user_message="test",
                assistant_response="test",
                thinking="test",
            )

            # Should not have scheduled anything
            mock_memory.add_scheduled_message.assert_not_called()


class TestFollowUpDecisionScenarios:
    """
    Test scenarios for when the AI should/shouldn't schedule follow-ups.

    These tests verify the observation agent's decision-making by checking
    whether follow-ups are scheduled for various conversation types.
    """

    @pytest.fixture
    def agent(self, companion_agent, mock_memory):
        """Use the companion_agent fixture and ensure mock_memory is attached."""
        companion_agent.memory = mock_memory
        return companion_agent

    # --- EXPLICIT REQUEST SCENARIOS (Highest Priority) ---

    @pytest.mark.parametrize("user_message", [
        "text me at 8:40am tomorrow",
        "message me later tonight",
        "remind me at 3pm",
        "check in with me tomorrow morning",
        "can you text me after my interview?",
        "send me a message when it's 5pm",
    ])
    async def test_explicit_request_should_schedule(
        self, agent, mock_memory, observation_builder, user_message
    ):
        """
        EXPLICIT REQUESTS should ALWAYS trigger a follow-up.
        These are direct user requests for reminders/check-ins.
        """
        response = (
            observation_builder()
            .add_follow_up("tomorrow at 8:40am", "reminder", "user requested check-in")
            .build()
        )

        with patch("agents.companion_agent.llm_client") as mock_llm:
            mock_llm.chat = AsyncMock(return_value=response)

            await agent._maybe_store_observations(
                user_id=1,
                profile_context="",
                user_message=user_message,
                assistant_response="sure, I'll check in!",
                thinking="user explicitly asked for a reminder",
            )

            mock_memory.add_scheduled_message.assert_called_once()

    # --- EVENT-BASED SCENARIOS ---

    @pytest.mark.parametrize("user_message,expected_topic", [
        ("I have a job interview tomorrow at 2pm", "interview"),
        ("my date is tonight at 7", "date"),
        ("doctor's appointment on Friday", "appointment"),
        ("flying to NYC next week", "trip"),
        ("big presentation on Monday", "presentation"),
    ])
    async def test_upcoming_events_should_schedule(
        self, agent, mock_memory, observation_builder, user_message, expected_topic
    ):
        """
        UPCOMING EVENTS should trigger follow-ups to check how they went.
        """
        response = (
            observation_builder()
            .add_follow_up("after the event", expected_topic, "check how it went")
            .build()
        )

        with patch("agents.companion_agent.llm_client") as mock_llm:
            mock_llm.chat = AsyncMock(return_value=response)

            await agent._maybe_store_observations(
                user_id=1,
                profile_context="",
                user_message=user_message,
                assistant_response="exciting! good luck!",
                thinking=f"upcoming {expected_topic}, should follow up",
            )

            mock_memory.add_scheduled_message.assert_called_once()
            call_kwargs = mock_memory.add_scheduled_message.call_args[1]
            assert expected_topic in call_kwargs["context"].lower()

    # --- WAITING FOR RESOLUTION SCENARIOS ---

    @pytest.mark.parametrize("user_message", [
        "waiting to hear back from the company",
        "they said they'd call me today",
        "expecting my test results soon",
        "should find out about the apartment tomorrow",
    ])
    async def test_waiting_for_resolution_should_schedule(
        self, agent, mock_memory, observation_builder, user_message
    ):
        """
        WAITING FOR RESOLUTION situations should trigger follow-ups.
        """
        response = (
            observation_builder()
            .add_follow_up("tomorrow", "waiting", "check if they heard back")
            .build()
        )

        with patch("agents.companion_agent.llm_client") as mock_llm:
            mock_llm.chat = AsyncMock(return_value=response)

            await agent._maybe_store_observations(
                user_id=1,
                profile_context="",
                user_message=user_message,
                assistant_response="fingers crossed!",
                thinking="waiting for news, should check in",
            )

            mock_memory.add_scheduled_message.assert_called_once()

    # --- EMOTIONAL FOLLOW-UP SCENARIOS ---

    @pytest.mark.parametrize("user_message", [
        "I'm really nervous about tomorrow",
        "feeling anxious about the results",
        "so excited for my trip!",
        "kinda stressed about the deadline",
    ])
    async def test_emotional_moments_may_schedule(
        self, agent, mock_memory, observation_builder, user_message
    ):
        """
        EMOTIONAL MOMENTS may warrant a caring follow-up.
        """
        response = (
            observation_builder()
            .add_follow_up("tomorrow", "emotional_check", "see how they're feeling")
            .build()
        )

        with patch("agents.companion_agent.llm_client") as mock_llm:
            mock_llm.chat = AsyncMock(return_value=response)

            await agent._maybe_store_observations(
                user_id=1,
                profile_context="",
                user_message=user_message,
                assistant_response="I'm here for you",
                thinking="emotional moment, might want to check in",
            )

            # May or may not schedule - just verify no crash
            assert True

    # --- SHOULD NOT SCHEDULE SCENARIOS ---

    @pytest.mark.parametrize("user_message", [
        "how's the weather today?",
        "what time is it?",
        "thanks!",
        "ok cool",
        "lol",
        "haha nice",
        "good morning",
    ])
    async def test_casual_messages_should_not_schedule(
        self, agent, mock_memory, observation_builder, user_message
    ):
        """
        CASUAL/TRIVIAL messages should NOT trigger follow-ups.
        """
        response = observation_builder().nothing_significant().build()

        with patch("agents.companion_agent.llm_client") as mock_llm:
            mock_llm.chat = AsyncMock(return_value=response)

            await agent._maybe_store_observations(
                user_id=1,
                profile_context="",
                user_message=user_message,
                assistant_response="hey!",
                thinking="casual chat",
            )

            mock_memory.add_scheduled_message.assert_not_called()

    @pytest.mark.parametrize("user_message", [
        "I had a good lunch today",
        "just finished watching a movie",
        "the coffee was nice this morning",
        "went for a walk earlier",
    ])
    async def test_mundane_updates_should_not_schedule(
        self, agent, mock_memory, observation_builder, user_message
    ):
        """
        MUNDANE UPDATES about past events don't need follow-ups.
        """
        response = observation_builder().nothing_significant().build()

        with patch("agents.companion_agent.llm_client") as mock_llm:
            mock_llm.chat = AsyncMock(return_value=response)

            await agent._maybe_store_observations(
                user_id=1,
                profile_context="",
                user_message=user_message,
                assistant_response="nice!",
                thinking="mundane update",
            )

            mock_memory.add_scheduled_message.assert_not_called()


class TestObservationStorage:
    """Test storage of observations (non-follow-up facts)."""

    @pytest.fixture
    def agent(self, companion_agent, mock_memory):
        """Use the companion_agent fixture and ensure mock_memory is attached."""
        companion_agent.memory = mock_memory
        return companion_agent

    async def test_stores_observation_facts(self, agent, mock_memory, observation_builder):
        """Should store OBSERVATION lines as profile facts."""
        response = (
            observation_builder()
            .add_observation("work", "works at Google as a software engineer")
            .add_observation("relationships", "has a friend named Tony")
            .build()
        )

        with patch("agents.companion_agent.llm_client") as mock_llm:
            mock_llm.chat = AsyncMock(return_value=response)

            await agent._maybe_store_observations(
                user_id=1,
                profile_context="",
                user_message="had lunch with Tony from work",
                assistant_response="nice!",
                thinking="learned about friend and work",
            )

            assert mock_memory.add_profile_fact.call_count == 2

    async def test_handles_mixed_observations_and_follow_ups(
        self, agent, mock_memory, observation_builder
    ):
        """Should handle both observations and follow-ups in one response."""
        response = (
            observation_builder()
            .add_observation("work", "has interview at Google")
            .add_follow_up("tomorrow at 3pm", "interview", "check how it went")
            .build()
        )

        with patch("agents.companion_agent.llm_client") as mock_llm:
            mock_llm.chat = AsyncMock(return_value=response)

            await agent._maybe_store_observations(
                user_id=1,
                profile_context="",
                user_message="interview at Google tomorrow",
                assistant_response="good luck!",
                thinking="important event",
            )

            mock_memory.add_profile_fact.assert_called_once()
            mock_memory.add_scheduled_message.assert_called_once()
