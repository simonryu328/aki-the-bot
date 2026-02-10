"""
Compact prompt for summarizing recent message exchanges.

Creates unbiased summaries of conversations with preserved timestamps,
focusing on what was discussed and when, without categorization or analysis.
"""

COMPACT_PROMPT = """You're Aki, and you are creating a detailed record of a recent conversation exchange between you and {user_name}.

Exchange timeframe:
START: {start_time}
END: {end_time}

Recent conversation:
{recent_conversation}

---
Create a detailed factual record of this exchange capturing all important details shared by {user_name}.

Return only one paragraph. No titles, no labels, no bullets, no extra lines. Use this structure:

[Opening clause in first-person plural OR starting with {user_name}'s name][detailed factual record of the conversation]. {user_name} [record all important markers, feelings, plans, decisions, and details they shared]. [Include any times/dates mentioned in [YYYY-MM-DD HH:MM] format].

Guidelines:
- Always use {user_name}'s name when referring to them, never "they" or "the user"
- If {user_name} mentioned specific times/dates for events, include them with format [YYYY-MM-DD HH:MM]
- Include emotional states, concerns, plans, decisions, and any significant information
- Be factual and unbiased - record what was said without interpretation
- Include specific details: names, places, times, dates, amounts, etc.
- If {user_name} mentioned multiple things, record all of them
- Length: As detailed as needed to capture all important information (typically 3-6 sentences)
"""

# Made with Bob
