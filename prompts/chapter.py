"""
Chapter prompt for recursive memory compaction (Level 2).

Aggregates paired compact_summary + conversation_memory entries
into cohesive biographical "Chapters" that capture both facts and meaning.
"""

CHAPTER_PROMPT = """You are writing a biography chapter about {user_name}'s recent life.

Below are paired records from {pair_count} conversation exchanges, each with:
- FACTS: An objective log of what was discussed
- MEANING: A personal reflection on what it reveals about {user_name}

{paired_entries}

---
Write a cohesive narrative chapter (2-3 paragraphs) covering this period.

Guidelines:
- Use FACTS for timeline accuracy, specific details, dates, and events
- Use MEANING for emotional depth, character insights, and relationship threads
- Identify and connect major themes across exchanges
- Write in third person about {user_name}, as a biographer would
- Focus on life changes, decisions, growth, and meaningful patterns
- Ignore trivial pleasantries or repetitive greetings
- Include specific dates when available
- Length: 2-3 substantial paragraphs
"""
