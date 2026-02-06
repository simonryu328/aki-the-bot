"""
Integration tests for observation agent LLM output.

These tests verify that the LLM correctly outputs ISO 8601 format
for follow-up times as specified in the prompt.

Run with: uv run pytest tests/integration/test_observation_agent.py -v
"""

import pytest
import re
from datetime import datetime, timedelta

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


def extract_follow_ups(response: str) -> list[dict]:
    """Extract FOLLOW_UP lines from observation agent response."""
    follow_ups = []
    for line in response.strip().split("\n"):
        line = line.strip()
        if line.startswith("FOLLOW_UP:"):
            content = line.replace("FOLLOW_UP:", "").strip()
            parts = content.split("|")
            if len(parts) >= 3:
                follow_ups.append({
                    "when": parts[0].strip(),
                    "topic": parts[1].strip(),
                    "context": parts[2].strip(),
                })
    return follow_ups


def is_iso_format(when_str: str) -> bool:
    """Check if a string is in ISO 8601 format (YYYY-MM-DDTHH:MM)."""
    try:
        datetime.fromisoformat(when_str)
        return True
    except ValueError:
        return False


def is_valid_iso_datetime(when_str: str) -> bool:
    """Check if string is valid ISO format with date and time."""
    pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$"
    return bool(re.match(pattern, when_str))


class TestObservationAgentISOOutput:
    """Test that observation agent outputs ISO 8601 format for times."""

    @pytest.fixture
    def llm_client(self):
        """Get the real LLM client."""
        from utils.llm_client import llm_client
        return llm_client

    @pytest.fixture
    def observation_prompt(self):
        """Get the observation prompt template."""
        from prompts import OBSERVATION_PROMPT
        return OBSERVATION_PROMPT

    @pytest.mark.asyncio
    async def test_explicit_time_request_returns_iso(self, llm_client, observation_prompt):
        """When user requests 'text me at 8:40am', LLM should return ISO datetime."""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")

        prompt = observation_prompt.format(
            current_time=current_time,
            profile_context="No prior context.",
            user_message="hey can you text me at 8:40am tomorrow?",
            assistant_response="sure thing! I'll message you at 8:40am tomorrow",
            thinking="User explicitly asked for a reminder at a specific time.",
        )

        result = await llm_client.chat(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )

        print(f"\n--- LLM Response ---\n{result}\n---")

        follow_ups = extract_follow_ups(result)

        assert len(follow_ups) >= 1, f"Expected at least 1 FOLLOW_UP, got: {result}"

        for fu in follow_ups:
            assert is_valid_iso_datetime(fu["when"]), (
                f"Expected ISO format (YYYY-MM-DDTHH:MM), got: '{fu['when']}'\n"
                f"Full response:\n{result}"
            )

    @pytest.mark.asyncio
    async def test_tonight_returns_iso(self, llm_client, observation_prompt):
        """When user says 'tonight at 8pm', LLM should return ISO datetime."""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")

        prompt = observation_prompt.format(
            current_time=current_time,
            profile_context="No prior context.",
            user_message="remind me to call mom tonight at 8pm",
            assistant_response="I'll remind you tonight at 8!",
            thinking="User wants a reminder tonight.",
        )

        result = await llm_client.chat(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )

        print(f"\n--- LLM Response ---\n{result}\n---")

        follow_ups = extract_follow_ups(result)

        assert len(follow_ups) >= 1, f"Expected at least 1 FOLLOW_UP, got: {result}"

        for fu in follow_ups:
            assert is_valid_iso_datetime(fu["when"]), (
                f"Expected ISO format, got: '{fu['when']}'"
            )
            # Verify it's evening time (after 6pm)
            parsed = datetime.fromisoformat(fu["when"])
            assert parsed.hour >= 18, f"Expected evening hour, got {parsed.hour}"

    @pytest.mark.asyncio
    async def test_tomorrow_evening_returns_iso(self, llm_client, observation_prompt):
        """When user mentions 'tomorrow evening', LLM should return ISO datetime."""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")

        prompt = observation_prompt.format(
            current_time=current_time,
            profile_context="No prior context.",
            user_message="I have a date tomorrow evening, kinda nervous",
            assistant_response="ooh exciting! hope it goes well",
            thinking="User has a date tomorrow, should follow up.",
        )

        result = await llm_client.chat(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )

        print(f"\n--- LLM Response ---\n{result}\n---")

        follow_ups = extract_follow_ups(result)

        if len(follow_ups) > 0:  # Date follow-up is optional
            for fu in follow_ups:
                assert is_valid_iso_datetime(fu["when"]), (
                    f"Expected ISO format, got: '{fu['when']}'"
                )

    @pytest.mark.asyncio
    async def test_in_10_minutes_returns_correct_iso(self, llm_client, observation_prompt):
        """When user says 'in 10 minutes', LLM should add 10 min to current time."""
        now = datetime.now()
        current_time = now.strftime("%Y-%m-%d %H:%M (%A)")

        prompt = observation_prompt.format(
            current_time=current_time,
            profile_context="No prior context.",
            user_message="can you text me in 10 minutes and say how are you?",
            assistant_response="sure! I'll text you in 10 minutes",
            thinking="User wants a reminder in 10 minutes.",
        )

        result = await llm_client.chat(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )

        print(f"\n--- LLM Response ---\n{result}\n---")
        print(f"Current time was: {current_time}")

        follow_ups = extract_follow_ups(result)

        assert len(follow_ups) >= 1, f"Expected at least 1 FOLLOW_UP, got: {result}"

        for fu in follow_ups:
            assert is_valid_iso_datetime(fu["when"]), (
                f"Expected ISO format, got: '{fu['when']}'"
            )
            # Verify it's approximately 10 minutes from now (within 15 min window)
            parsed = datetime.fromisoformat(fu["when"])
            expected_min = now + timedelta(minutes=5)
            expected_max = now + timedelta(minutes=20)
            assert expected_min <= parsed <= expected_max, (
                f"Expected time ~10 min from {now.strftime('%H:%M')}, "
                f"got {parsed.strftime('%H:%M')} ({fu['when']})"
            )

    @pytest.mark.asyncio
    async def test_in_few_hours_returns_iso(self, llm_client, observation_prompt):
        """When context implies 'in a few hours', LLM should calculate ISO datetime."""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")

        prompt = observation_prompt.format(
            current_time=current_time,
            profile_context="No prior context.",
            user_message="at the doctor now, will let you know how it goes",
            assistant_response="hope everything goes well! let me know",
            thinking="User is at doctor, should check in after.",
        )

        result = await llm_client.chat(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )

        print(f"\n--- LLM Response ---\n{result}\n---")

        follow_ups = extract_follow_ups(result)

        if len(follow_ups) > 0:
            for fu in follow_ups:
                assert is_valid_iso_datetime(fu["when"]), (
                    f"Expected ISO format, got: '{fu['when']}'"
                )


class TestISOFormatParsing:
    """Test that ISO format is correctly parsed by the agent."""

    @pytest.fixture
    def agent(self, companion_agent):
        return companion_agent

    def test_parse_iso_from_llm_output(self, agent):
        """ISO format from LLM should parse correctly."""
        # Simulate what LLM should now output
        test_cases = [
            "2026-02-05T20:00",  # tonight at 8pm
            "2026-02-06T19:00",  # tomorrow evening
            "2026-02-06T08:40",  # tomorrow at 8:40am
            "2026-02-05T16:30",  # in 2 hours from 14:30
        ]

        for iso_str in test_cases:
            result = agent._parse_when_to_datetime(iso_str)
            expected = datetime.fromisoformat(iso_str)

            assert result == expected, f"Failed for {iso_str}: got {result}"
            assert result.tzinfo is None, "Should return naive datetime"
