# Test Documentation

## Quick Start

```bash
# Install test dependencies
uv sync --extra dev

# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v
```

---

## Test Structure

```
tests/
├── conftest.py                      # Shared fixtures
├── fixtures/
│   └── follow_up_scenarios.json     # Test data (40+ scenarios)
├── unit/
│   ├── test_time_parsing.py         # Time string parsing
│   ├── test_follow_up_decision.py   # AI scheduling decisions
│   └── test_observation_parsing.py  # Output line parsing
└── integration/                     # (Future DB tests)
```

---

## Test Files Explained

### `test_time_parsing.py`

Tests the `_parse_when_to_datetime()` method that converts user time expressions into datetime objects.

| Test Class | What It Tests |
|------------|---------------|
| `TestTimeParsing` | Core parsing functionality |
| `TestTimeParsingScenarios` | Real-world user requests |

**Key Tests:**

| Test | Input Example | Validates |
|------|---------------|-----------|
| `test_parse_iso_format_with_time` | `"2026-02-10T14:30"` | ISO 8601 timestamps work |
| `test_parse_natural_language_tomorrow` | `"tomorrow at 10am"` | dateparser handles natural language |
| `test_parse_relative_hours` | `"in 3 hours"` | Relative time expressions |
| `test_parse_legacy_*` | `"tomorrow_morning"` | Backwards-compatible formats |
| `test_parse_gibberish_defaults_to_24h` | `"asdfghjkl"` | Invalid input defaults safely |
| `test_returns_naive_datetime` | All inputs | Output is timezone-naive (for DB storage) |

**Known Limitations (xfail):**
- `"tomorrow evening"` - dateparser doesn't handle this
- `"tonight at 8pm"` - dateparser doesn't handle this

---

### `test_follow_up_decision.py`

Tests the observation agent's logic for deciding when to schedule follow-ups.

| Test Class | What It Tests |
|------------|---------------|
| `TestFollowUpParsing` | Parsing `FOLLOW_UP:` lines from LLM output |
| `TestFollowUpDecisionScenarios` | Should/shouldn't schedule scenarios |
| `TestObservationStorage` | Storing `OBSERVATION:` facts |

**Scenario Categories:**

| Category | Example Input | Expected Behavior |
|----------|---------------|-------------------|
| **Explicit Requests** | `"text me at 8:40am tomorrow"` | MUST schedule |
| **Upcoming Events** | `"I have an interview tomorrow"` | Should schedule |
| **Waiting for Resolution** | `"waiting to hear back"` | Should schedule |
| **Emotional Moments** | `"I'm nervous about tomorrow"` | May schedule |
| **Casual Messages** | `"thanks!"`, `"lol"` | Should NOT schedule |
| **Mundane Updates** | `"I had a good lunch"` | Should NOT schedule |

**How It Works:**
- Tests mock the LLM response with `observation_builder()` fixture
- Verifies `memory.add_scheduled_message()` was called (or not)
- Checks the scheduled message contains expected topic/context

---

### `test_observation_parsing.py`

Tests pure string parsing of observation agent output lines (no AI/mocks needed).

| Test Class | What It Tests |
|------------|---------------|
| `TestObservationLineParsing` | `OBSERVATION: category \| content` format |
| `TestFollowUpLineParsing` | `FOLLOW_UP: when \| topic \| context` format |
| `TestMultiLineResponse` | Mixed/multiple lines in one response |

**Key Tests:**

| Test | Input | Validates |
|------|-------|-----------|
| `test_parse_valid_observation` | `"OBSERVATION: work \| works at Google"` | Correct splitting |
| `test_parse_observation_with_multiple_pipes` | `"OBSERVATION: x \| a \| b"` | Only splits on first pipe |
| `test_parse_invalid_*` | Malformed lines | Returns `None` gracefully |
| `test_parse_mixed_response` | Multi-line output | Both types extracted |

---

## Running Tests

### Basic Commands

```bash
# Run all tests
uv run pytest

# Run specific file
uv run pytest tests/unit/test_time_parsing.py

# Run specific test class
uv run pytest tests/unit/test_time_parsing.py::TestTimeParsing

# Run specific test
uv run pytest tests/unit/test_time_parsing.py::TestTimeParsing::test_parse_iso_format_with_time

# Run tests matching a pattern
uv run pytest -k "follow_up"
uv run pytest -k "explicit_request"
uv run pytest -k "not slow"
```

### Output Options

```bash
# Verbose - see each test name
uv run pytest -v

# Extra verbose - see test parameters
uv run pytest -vv

# Show print statements and logs
uv run pytest -s

# Combine: verbose + print output
uv run pytest -vs

# Show local variables on failure
uv run pytest -l

# Stop on first failure
uv run pytest -x

# Stop after N failures
uv run pytest --maxfail=3

# Show slowest N tests
uv run pytest --durations=10
```

### Better Result Viewing

```bash
# Compact one-line-per-test (great for many tests)
uv run pytest -v --tb=line

# Short traceback (recommended)
uv run pytest -v --tb=short

# No traceback (just pass/fail)
uv run pytest -v --tb=no

# Full traceback (debugging)
uv run pytest -v --tb=long

# Show only failed tests
uv run pytest --tb=short --no-header -q
```

### HTML Report (Recommended)

```bash
# Install pytest-html
uv add pytest-html --dev

# Generate HTML report
uv run pytest --html=report.html --self-contained-html

# Open in browser
open report.html
```

### Watch Mode (Auto-rerun on file changes)

```bash
# Install pytest-watch
uv add pytest-watch --dev

# Run in watch mode
uv run ptw -- -v --tb=short
```

### Coverage Report

```bash
# Install pytest-cov
uv add pytest-cov --dev

# Run with coverage
uv run pytest --cov=agents --cov=memory --cov-report=html

# View coverage
open htmlcov/index.html
```

---

## Fixtures Reference

Defined in `conftest.py`:

| Fixture | Description |
|---------|-------------|
| `fixed_now` | Fixed datetime (2026-02-05 14:30 Toronto) for deterministic tests |
| `mock_datetime` | Patches `datetime.now()` to return `fixed_now` |
| `mock_memory` | AsyncMock of memory manager with all methods |
| `companion_agent` | CompanionAgent instance with mocked memory |
| `mock_llm` | AsyncMock of LLM client |
| `observation_builder` | Factory for building mock LLM observation responses |

**Using `observation_builder`:**

```python
async def test_example(self, agent, mock_memory, observation_builder):
    response = (
        observation_builder()
        .add_observation("work", "works at Google")
        .add_follow_up("tomorrow at 3pm", "interview", "check how it went")
        .build()
    )
    # response = "OBSERVATION: work | works at Google\nFOLLOW_UP: tomorrow at 3pm | interview | check how it went"
```

---

## Test Data

`fixtures/follow_up_scenarios.json` contains 40+ categorized test scenarios:

- `explicit_requests` - User asks for reminder (highest priority)
- `upcoming_events` - Interviews, dates, appointments
- `waiting_for_resolution` - Waiting for news/results
- `emotional_moments` - Anxiety, excitement, stress
- `should_not_schedule` - Casual/trivial messages
- `edge_cases` - Ambiguous scenarios

Use these to expand parametrized tests or for manual testing.

---

## Tips

1. **Start with `-v --tb=short`** - Best balance of info vs noise
2. **Use `-k` to filter** - Run only relevant tests during development
3. **Use `-x` to fail fast** - Stop on first failure when debugging
4. **Use `--durations=10`** - Find slow tests to optimize
5. **Install `pytest-html`** - Beautiful shareable reports
6. **Use `ptw` (pytest-watch)** - Auto-rerun on save
