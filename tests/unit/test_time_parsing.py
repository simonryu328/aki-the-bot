"""
Tests for time parsing functionality in the companion agent.

Tests the _parse_when_to_datetime() method which converts natural language
and structured time strings into datetime objects.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytz


class TestTimeParsing:
    """Test suite for _parse_when_to_datetime method."""

    @pytest.fixture
    def agent(self, companion_agent):
        """Use the companion_agent fixture from conftest."""
        return companion_agent

    @pytest.fixture
    def toronto_tz(self):
        return pytz.timezone("America/Toronto")

    # --- ISO 8601 Format Tests ---

    def test_parse_iso_format_with_time(self, agent):
        """Should parse ISO 8601 datetime strings."""
        result = agent._parse_when_to_datetime("2026-02-10T14:30")

        assert result.year == 2026
        assert result.month == 2
        assert result.day == 10
        assert result.hour == 14
        assert result.minute == 30
        assert result.tzinfo is None  # Should return naive datetime

    def test_parse_iso_format_morning(self, agent):
        """Should parse morning ISO timestamps."""
        result = agent._parse_when_to_datetime("2026-03-15T09:00")

        assert result.hour == 9
        assert result.minute == 0

    # --- Natural Language Tests ---

    @pytest.mark.parametrize("input_str,expected_hour_range", [
        ("tomorrow at 10am", (9, 11)),
        ("tomorrow at 3pm", (14, 16)),
        ("tomorrow morning", (6, 12)),
        pytest.param("tomorrow evening", (17, 21), marks=pytest.mark.xfail(
            reason="dateparser doesn't handle 'tomorrow evening' - falls back to 24h"
        )),
    ])
    def test_parse_natural_language_tomorrow(self, agent, input_str, expected_hour_range):
        """Should parse 'tomorrow at X' patterns."""
        result = agent._parse_when_to_datetime(input_str)

        # Should be in the future
        assert result > datetime.now()
        # Hour should be in expected range
        assert expected_hour_range[0] <= result.hour <= expected_hour_range[1]

    @pytest.mark.parametrize("input_str", [
        "in 3 hours",
        "in 2 hours",
        "in 1 hour",
    ])
    def test_parse_relative_hours(self, agent, input_str):
        """Should parse 'in X hours' patterns."""
        before = datetime.now()
        result = agent._parse_when_to_datetime(input_str)
        after = datetime.now()

        # Should be in the future
        assert result > before
        # Should be within reasonable range (1-4 hours from now)
        assert result < after + timedelta(hours=5)

    def test_parse_next_week(self, agent):
        """Should parse 'next week' correctly."""
        result = agent._parse_when_to_datetime("next week")

        # Should be roughly 7 days from now
        now = datetime.now()
        delta = result - now
        assert 5 <= delta.days <= 9

    @pytest.mark.xfail(reason="dateparser doesn't handle 'tonight at 8pm' - falls back to 24h")
    def test_parse_tonight(self, agent):
        """Should parse 'tonight' correctly."""
        result = agent._parse_when_to_datetime("tonight at 8pm")

        assert result.hour == 20

    # --- Legacy Hardcoded Options ---

    def test_parse_legacy_tomorrow_morning(self, agent):
        """Should handle legacy 'tomorrow_morning' format."""
        result = agent._parse_when_to_datetime("tomorrow_morning")

        assert result.hour == 9
        assert result.minute == 0

    def test_parse_legacy_tomorrow_evening(self, agent):
        """Should handle legacy 'tomorrow_evening' format."""
        result = agent._parse_when_to_datetime("tomorrow_evening")

        assert result.hour == 19
        assert result.minute == 0

    def test_parse_legacy_in_24h(self, agent):
        """Should handle legacy 'in_24h' format."""
        before = datetime.now()
        result = agent._parse_when_to_datetime("in_24h")
        after = datetime.now()

        delta = result - before
        assert 23 <= delta.total_seconds() / 3600 <= 25

    def test_parse_legacy_in_few_days(self, agent):
        """Should handle legacy 'in_few_days' format."""
        before = datetime.now()
        result = agent._parse_when_to_datetime("in_few_days")

        delta = result - before
        assert delta.days == 3

    def test_parse_legacy_next_week(self, agent):
        """Should handle legacy 'next_week' format."""
        before = datetime.now()
        result = agent._parse_when_to_datetime("next_week")

        delta = result - before
        assert delta.days == 7

    # --- Edge Cases & Fallbacks ---

    def test_parse_gibberish_defaults_to_24h(self, agent):
        """Should default to 24 hours for unparseable input."""
        before = datetime.now()
        result = agent._parse_when_to_datetime("asdfghjkl123")

        delta = result - before
        assert 23 <= delta.total_seconds() / 3600 <= 25

    def test_parse_empty_string_defaults(self, agent):
        """Should handle empty string gracefully."""
        before = datetime.now()
        result = agent._parse_when_to_datetime("")

        # Should not crash, should default to something reasonable
        assert result > before

    def test_parse_whitespace_handling(self, agent):
        """Should strip whitespace from input."""
        result = agent._parse_when_to_datetime("  tomorrow at 10am  ")

        assert result > datetime.now()

    # --- Timezone Awareness ---

    def test_returns_naive_datetime(self, agent):
        """All results should be timezone-naive (for database storage)."""
        test_cases = [
            "2026-02-10T14:30",
            "tomorrow at 10am",
            "in 3 hours",
            "tomorrow_morning",
        ]

        for input_str in test_cases:
            result = agent._parse_when_to_datetime(input_str)
            assert result.tzinfo is None, f"Failed for input: {input_str}"


class TestTimeParsingScenarios:
    """Real-world scenarios for time parsing."""

    @pytest.fixture
    def agent(self, companion_agent):
        """Use the companion_agent fixture from conftest."""
        return companion_agent

    @pytest.mark.parametrize("user_request,description", [
        ("text me at 8:40am", "specific morning time"),
        ("message me at 3pm", "afternoon time"),
        ("remind me at noon", "noon"),
        ("check in at midnight", "midnight"),
        ("tomorrow after my interview around 4pm", "contextual time"),
    ])
    def test_common_user_requests(self, agent, user_request, description):
        """Test parsing of common user time requests."""
        result = agent._parse_when_to_datetime(user_request)

        # Should produce a valid future datetime
        assert isinstance(result, datetime)
        assert result.tzinfo is None
