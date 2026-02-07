"""
Condensation prompt for compressing raw observations into narrative.

Works for any observation category. The persona shapes the voice,
the static context grounds it in who the person is, and the category
determines what aspect to focus on.
"""

CONDENSATION_PROMPT = """You are {persona_name}.
{persona_description}

You've been getting to know {user_name} over time. Here's what you know about them:
{static_context}

Below are your raw notes about their {category}, ordered by date.

RAW OBSERVATIONS:
{timestamped_observations}

---

Distill these into a living narrative. Write naturally, as yourself.

Guidelines:
- Preserve the arc of time: when things started, how they shifted, where they are now
- If you noticed the same thing repeatedly, say it once — but with the weight of repetition
- Highlight turning points ("something shifted when...")
- Current state matters most, but history gives it meaning
- 2-4 sentences. Dense with understanding, not padded with filler.

Write your condensed understanding of their {category}:"""
