"""
Tests for parsing observation agent output lines.

Tests the regex/string parsing of OBSERVATION: and FOLLOW_UP: lines
from the LLM observation agent response.
"""

import pytest
import re


def parse_observation_line(line: str) -> dict | None:
    """Parse an OBSERVATION: line into category and content."""
    line = line.strip()
    if not line.startswith("OBSERVATION:"):
        return None

    content = line.replace("OBSERVATION:", "").strip()
    parts = content.split("|", 1)
    if len(parts) != 2:
        return None

    return {
        "category": parts[0].strip(),
        "content": parts[1].strip(),
    }


def parse_follow_up_line(line: str) -> dict | None:
    """Parse a FOLLOW_UP: line into when, topic, and context."""
    line = line.strip()
    if not line.startswith("FOLLOW_UP:"):
        return None

    content = line.replace("FOLLOW_UP:", "").strip()
    parts = content.split("|")
    if len(parts) < 3:
        return None

    return {
        "when": parts[0].strip(),
        "topic": parts[1].strip(),
        "context": parts[2].strip(),
    }


class TestObservationLineParsing:
    """Test parsing of OBSERVATION: lines."""

    def test_parse_valid_observation(self):
        """Should parse valid observation line."""
        line = "OBSERVATION: work | works at Google as a software engineer"
        result = parse_observation_line(line)

        assert result is not None
        assert result["category"] == "work"
        assert result["content"] == "works at Google as a software engineer"

    def test_parse_observation_with_multiple_pipes_in_content(self):
        """Should handle pipes in the content (only split on first pipe)."""
        line = "OBSERVATION: schedule | meeting at 2pm | with team"
        result = parse_observation_line(line)

        assert result is not None
        assert result["category"] == "schedule"
        assert result["content"] == "meeting at 2pm | with team"

    def test_parse_observation_with_whitespace(self):
        """Should strip whitespace correctly."""
        line = "  OBSERVATION:   work   |   has a job   "
        result = parse_observation_line(line)

        assert result is not None
        assert result["category"] == "work"
        assert result["content"] == "has a job"

    def test_parse_invalid_observation_no_pipe(self):
        """Should return None for line without pipe separator."""
        line = "OBSERVATION: this has no pipe"
        result = parse_observation_line(line)

        assert result is None

    def test_parse_non_observation_line(self):
        """Should return None for non-observation lines."""
        assert parse_observation_line("FOLLOW_UP: tomorrow | test | context") is None
        assert parse_observation_line("NOTHING_SIGNIFICANT") is None
        assert parse_observation_line("random text") is None

    @pytest.mark.parametrize("category", [
        "work",
        "relationships",
        "health",
        "goals",
        "preferences",
        "schedule",
        "emotional_state",
    ])
    def test_parse_observation_categories(self, category):
        """Should handle various observation categories."""
        line = f"OBSERVATION: {category} | some content here"
        result = parse_observation_line(line)

        assert result is not None
        assert result["category"] == category


class TestFollowUpLineParsing:
    """Test parsing of FOLLOW_UP: lines."""

    def test_parse_valid_follow_up(self):
        """Should parse valid follow-up line."""
        line = "FOLLOW_UP: tomorrow at 3pm | interview | Google interview follow-up"
        result = parse_follow_up_line(line)

        assert result is not None
        assert result["when"] == "tomorrow at 3pm"
        assert result["topic"] == "interview"
        assert result["context"] == "Google interview follow-up"

    def test_parse_follow_up_iso_time(self):
        """Should handle ISO timestamp format."""
        line = "FOLLOW_UP: 2026-02-06T15:00 | meeting | check how meeting went"
        result = parse_follow_up_line(line)

        assert result is not None
        assert result["when"] == "2026-02-06T15:00"

    def test_parse_follow_up_natural_language_time(self):
        """Should handle natural language time."""
        line = "FOLLOW_UP: in 3 hours | reminder | user asked for check-in"
        result = parse_follow_up_line(line)

        assert result is not None
        assert result["when"] == "in 3 hours"

    def test_parse_follow_up_with_whitespace(self):
        """Should strip whitespace correctly."""
        line = "  FOLLOW_UP:   tomorrow   |   topic   |   context here   "
        result = parse_follow_up_line(line)

        assert result is not None
        assert result["when"] == "tomorrow"
        assert result["topic"] == "topic"
        assert result["context"] == "context here"

    def test_parse_invalid_follow_up_missing_parts(self):
        """Should return None for line with fewer than 3 parts."""
        assert parse_follow_up_line("FOLLOW_UP: tomorrow | topic") is None
        assert parse_follow_up_line("FOLLOW_UP: tomorrow") is None
        assert parse_follow_up_line("FOLLOW_UP:") is None

    def test_parse_non_follow_up_line(self):
        """Should return None for non-follow-up lines."""
        assert parse_follow_up_line("OBSERVATION: work | content") is None
        assert parse_follow_up_line("NOTHING_SIGNIFICANT") is None

    @pytest.mark.parametrize("when_str", [
        "tomorrow at 10am",
        "in 2 hours",
        "next week",
        "2026-02-10T14:30",
        "tonight at 8pm",
        "tomorrow_morning",
        "Monday at 9am",
    ])
    def test_parse_various_time_formats(self, when_str):
        """Should handle various time format strings."""
        line = f"FOLLOW_UP: {when_str} | topic | context"
        result = parse_follow_up_line(line)

        assert result is not None
        assert result["when"] == when_str


class TestMultiLineResponse:
    """Test parsing multiple lines from observation agent response."""

    def test_parse_multiple_observations(self):
        """Should parse multiple observations from response."""
        response = """OBSERVATION: work | works at Google
OBSERVATION: relationships | has friend named Tony
OBSERVATION: goals | wants to learn piano"""

        observations = []
        for line in response.strip().split("\n"):
            result = parse_observation_line(line)
            if result:
                observations.append(result)

        assert len(observations) == 3
        assert observations[0]["category"] == "work"
        assert observations[1]["category"] == "relationships"
        assert observations[2]["category"] == "goals"

    def test_parse_mixed_response(self):
        """Should parse both observations and follow-ups."""
        response = """OBSERVATION: work | has interview at Google
FOLLOW_UP: tomorrow at 3pm | interview | check how it went
OBSERVATION: emotional_state | feeling nervous"""

        observations = []
        follow_ups = []

        for line in response.strip().split("\n"):
            obs = parse_observation_line(line)
            if obs:
                observations.append(obs)

            fu = parse_follow_up_line(line)
            if fu:
                follow_ups.append(fu)

        assert len(observations) == 2
        assert len(follow_ups) == 1

    def test_parse_nothing_significant(self):
        """Should handle NOTHING_SIGNIFICANT response."""
        response = "NOTHING_SIGNIFICANT"

        observations = []
        follow_ups = []

        for line in response.strip().split("\n"):
            obs = parse_observation_line(line)
            if obs:
                observations.append(obs)

            fu = parse_follow_up_line(line)
            if fu:
                follow_ups.append(fu)

        assert len(observations) == 0
        assert len(follow_ups) == 0
