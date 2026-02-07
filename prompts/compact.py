"""
Compact prompt for summarizing recent message exchanges.

Creates unbiased summaries of conversations with preserved timestamps,
focusing on what was discussed and when, without categorization or analysis.
"""

COMPACT_PROMPT = """You are creating a detailed record of a recent conversation exchange.

What you know about {user_name}:
{profile_context}

Exchange timeframe:
START: {start_time}
END: {end_time}

Recent conversation:
{recent_conversation}

---

Create a detailed factual record of this exchange that captures EVERY important marker, detail, event, decision, action, feeling, or plan mentioned by {user_name}.

Format your response as:

SUMMARY:
[START: {start_time}] [END: {end_time}]
We discussed [detailed factual record of the conversation]. {user_name} [record every important marker, indicator, feeling, plan, or detail they shared]. [Include any specific times, dates, or events mentioned with their timestamps].

Guidelines:
- Write in first person plural: "We discussed..." not "They said..."
- Always use {user_name}'s name when referring to them, never "they" or "the user"
- Be thorough - capture EVERY important detail, marker, or indicator from {user_name}
- If {user_name} mentioned specific times/dates for events, include them with format [YYYY-MM-DD HH:MM]
- Include emotional states, concerns, plans, decisions, and any significant information
- Be factual and unbiased - record what was said without interpretation
- Include specific details: names, places, times, dates, amounts, etc.
- If {user_name} mentioned multiple things, record all of them
- Length: As detailed as needed to capture all important information (typically 3-6 sentences)
"""

# Made with Bob
