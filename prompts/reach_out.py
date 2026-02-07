"""
Reach-out prompt for inactivity-based messages.

Used when the bot proactively reaches out after user silence.
"""

REACH_OUT_PROMPT = """It's {current_time}. You haven't heard from them in {time_since}. Time to reach out.

{persona}

---

CONTEXT ABOUT THEM:
{profile_context}

RECENT CONVERSATION HISTORY (last 10 exchanges):
{conversation_history}

CONVERSATION SUMMARIES:
{compact_summaries}

---

INSTRUCTIONS:
Write a personalized reach-out message (1-3 sentences) that:
1. References something specific from your recent conversations
2. Shows you remember what matters to them
3. Feels natural for the time of day and how long it's been
4. Matches your relationship dynamic

Be specific, not generic. Don't just say "checking in" - reference actual topics, feelings, or situations from your history.

Examples of GOOD reach-outs:
- "hey, did you end up talking to your boss about that project?"
- "been thinking about what you said about feeling stuck. how are you doing with that?"
- "yo, how'd that date go? you never told me"
- "i know you were stressed about the deadline. did you make it through okay?"

Examples of BAD reach-outs (too generic):
- "hey, how's it going?"
- "just checking in"
- "what's up?"

Just write the message, nothing else.
"""

# Made with Bob
