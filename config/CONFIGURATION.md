# Configuration Settings Documentation

This document explains all configuration variables in `config/settings.py` and how they affect the AI companion bot's behavior.

## Table of Contents
- [Conversation Context Configuration](#conversation-context-configuration)
- [Observation and Compact Configuration](#observation-and-compact-configuration)
- [Database Fetch Limits](#database-fetch-limits)
- [How Compact Summaries Work](#how-compact-summaries-work)

---

## Conversation Context Configuration

These settings control how much conversation history is included in the AI's context when generating responses.

### `CONVERSATION_CONTEXT_LIMIT`
- **Default:** `20`
- **Type:** Integer (≥ 1)
- **Purpose:** Number of recent messages to include in the CURRENT CONVERSATION section
- **Used in:**
  - `agents/soul_agent.py`: `_build_conversation_context()`
  - `bot/telegram_handler.py`: Reach-out message generation
- **What it does:** Controls how many recent messages the AI sees when responding. Higher values give more context but use more tokens.
- **Example:** With value `20`, the AI sees the last 20 messages in the current conversation.

### `COMPACT_SUMMARY_LIMIT`
- **Default:** `2`
- **Type:** Integer (1-10)
- **Purpose:** Number of recent compact summaries to include in the RECENT EXCHANGES section.
- **Used in:**
  - `agents/soul_agent.py`: `_build_conversation_context()`
  - `bot/telegram_handler.py`: Reach-out message generation
- **What it does:** Compact summaries are timestamped conversation summaries created every N messages. This controls how many of those summaries are shown to the AI for historical context.
- **Example:** With value `2`, the AI sees summaries of the last 2 conversation batches.

### `MEMORY_ENTRY_LIMIT`
- **Default:** `2`
- **Type:** Integer (1-10)
- **Purpose:** Number of recent memory entries to include in the RECENT EXCHANGES section.
- **Used in:**
  - `agents/soul_agent.py`: `_build_conversation_context()`
  - `bot/telegram_handler.py`: Reach-out message generation
- **What it does:** Memory entries are timestamped reflections on conversation exchanges. This controls how many of those reflections are shown in addition to summaries.
- **Example:** With value `2`, the AI sees the last 2 memory entries.

**Note:** The system uses a sliding window strategy to provide 4 distinct time ranges in RECENT EXCHANGES. It picks the 2 most recent compact summaries for the newest historical context, and then picks the 2 most recent memory entries that are *older* than those summaries. 

In the prompt, they are ordered chronologically:
1. Memory (Oldest)
2. Memory
3. Summary
4. Summary (Newest)

This ensures the AI sees a deep, multi-stage history without overlapping content.

---

## Observation and Compact Configuration

These settings control when the AI creates summaries and observations.

### `OBSERVATION_INTERVAL`
- **Default:** `10`
- **Type:** Integer (≥ 1)
- **Purpose:** Number of exchanges before triggering observation agent
- **Status:** Currently disabled
- **What it does:** Observations extract facts about the user from conversations (e.g., "User likes coffee", "User has a cat named Nono"). This feature is currently disabled in favor of compact summaries.

### `COMPACT_INTERVAL`
- **Default:** `10`
- **Type:** Integer (≥ 1)
- **Purpose:** Number of messages before creating a compact summary
- **Used in:** `agents/soul_agent.py`: `_maybe_create_compact_summary()`
- **What it does:** After every N messages, the system automatically creates a timestamped summary of the conversation. This prevents token bloat while maintaining conversation history.
- **Example:** With value `10`, after every 10 messages, the bot creates a summary like:
  ```
  [Jan 15, 10:30 AM - 11:45 AM] Discussed user's new cat Nono and plans to visit parents this weekend.
  ```

### `CONDENSATION_THRESHOLD`
- **Default:** `50`
- **Type:** Integer (≥ 1)
- **Purpose:** Number of raw observations before triggering auto-condensation
- **Status:** Legacy feature
- **What it does:** Condensation converts raw observations into narrative form. This is mostly replaced by compact summaries but still used for the observation system if enabled.

---

## Database Fetch Limits

These settings control how many records to fetch from the database.

### `DIARY_FETCH_LIMIT`
- **Default:** `10`
- **Type:** Integer (5-50)
- **Purpose:** Number of diary entries to fetch when looking for compact summaries
- **Used in:**
  - `agents/soul_agent.py`: `_build_conversation_context()`
  - `agents/soul_agent.py`: `_maybe_create_compact_summary()`
- **What it does:** Fetches diary entries from the database, then filters to get only compact summaries. Should be ≥ `COMPACT_SUMMARY_LIMIT` to ensure we get enough compacts.
- **Why higher than COMPACT_SUMMARY_LIMIT:** Diary entries include other types (reflections, observations), so we fetch more to ensure we get enough compact summaries after filtering.

### `OBSERVATION_DISPLAY_LIMIT`
- **Default:** `20`
- **Type:** Integer (10-100)
- **Purpose:** Number of observations to display in context
- **Used in:** `agents/soul_agent.py`: `_build_profile_context()`
- **Status:** Currently disabled in favor of compact summaries
- **What it does:** When showing raw observations (legacy feature), this limits how many are displayed to prevent token bloat.

---

## How Compact Summaries Work

Compact summaries are the core memory system that allows the bot to maintain conversation history without token bloat.

### The Flow

1. **Trigger Check** (after each message)
   - System counts messages since last compact summary
   - If count ≥ `COMPACT_INTERVAL` (default: 10), trigger creation

2. **Summary Creation**
   - Fetches last `CONVERSATION_CONTEXT_LIMIT` messages (default: 20)
   - Extracts start/end timestamps from conversations
   - Calls LLM to generate concise summary
   - Stores in database as diary entry with type `compact_summary`

3. **Context Building** (when generating responses)
   - Fetches last `DIARY_FETCH_LIMIT` diary entries (default: 10)
   - Filters to get `COMPACT_SUMMARY_LIMIT` compact summaries (default: 5)
   - Formats with timestamps: `[Jan 15, 10:30 AM - 11:45 AM] Summary text`
   - Queries conversations AFTER last compact's end time to avoid duplication
   - Includes `CONVERSATION_CONTEXT_LIMIT` recent messages (default: 20)

### Database Storage

Compact summaries are stored in the `diary_entries` table:
- `entry_type`: `"compact_summary"`
- `content`: The actual summary text
- `timestamp`: When the summary was created (UTC)
- `exchange_start`: UTC timestamp of first message in range
- `exchange_end`: UTC timestamp of last message in range

### Deduplication

The system uses `exchange_end` timestamp to ensure no overlap:
- Compact summaries cover messages from `exchange_start` to `exchange_end`
- Current conversation shows only messages AFTER `exchange_end`
- This prevents the AI from seeing the same messages twice

### Example Context

```
RECENT EXCHANGES:
[Jan 14, 2:00 PM - 3:30 PM] Discussed user's job interview preparation and anxiety about the process.
[Jan 14, 8:00 PM - 9:15 PM] User shared excitement about getting the job offer. Celebrated together.
[Jan 15, 10:30 AM - 11:45 AM] Talked about user's new cat Nono and plans to visit parents this weekend.

CURRENT CONVERSATION:
[Jan 15, 2:00 PM] User: hey! nono just did the funniest thing
[Jan 15, 2:01 PM] You: omg what did she do? 😂
[Jan 15, 2:02 PM] User: she tried to jump on the counter and completely missed
```

---

## Tuning Recommendations

### For More Context (Higher Token Usage)
- Increase `CONVERSATION_CONTEXT_LIMIT` to 30-40
- Increase `COMPACT_SUMMARY_LIMIT` to 7-10
- Decrease `COMPACT_INTERVAL` to 5-7 (more frequent summaries)

### For Less Token Usage (More Efficient)
- Decrease `CONVERSATION_CONTEXT_LIMIT` to 10-15
- Decrease `COMPACT_SUMMARY_LIMIT` to 3-4
- Increase `COMPACT_INTERVAL` to 15-20 (less frequent summaries)

### For Better Long-term Memory
- Increase `COMPACT_SUMMARY_LIMIT` to 8-10
- Keep `COMPACT_INTERVAL` at 10
- Increase `DIARY_FETCH_LIMIT` to 20

---

## Environment Variables

All settings can be overridden via environment variables:
```bash
CONVERSATION_CONTEXT_LIMIT=30
COMPACT_SUMMARY_LIMIT=7
COMPACT_INTERVAL=10
DIARY_FETCH_LIMIT=15
OBSERVATION_DISPLAY_LIMIT=20
```

Add these to your `.env` file or set them in your deployment environment (Railway, etc.).