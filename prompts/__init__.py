"""
Prompts module - All LLM prompts organized by feature.

Import prompts directly:
    from prompts import SYSTEM_FRAME, REACH_OUT_PROMPT

Or import personas:
    from prompts.personas import COMPANION_PERSONA
"""

from prompts.system_frame import SYSTEM_FRAME
from prompts.reflection import REFLECTION_PROMPT
from prompts.proactive import PROACTIVE_MESSAGE_PROMPT
from prompts.compact import COMPACT_PROMPT
from prompts.reach_out import REACH_OUT_PROMPT
from prompts.memory import MEMORY_PROMPT
from prompts.surface import SURFACE_PROMPT
from prompts.daily_message import DAILY_MESSAGE_PROMPT, FALLBACK_QUOTES
from prompts.personalized_insights import PERSONALIZED_INSIGHTS_PROMPT
from prompts.note_synthesis import NOTE_SYNTHESIS_PROMPT
from prompts.plan_synthesis import PLAN_SYNTHESIS_PROMPT

__all__ = [
    "SYSTEM_FRAME",
    "REFLECTION_PROMPT",
    "PROACTIVE_MESSAGE_PROMPT",
    "COMPACT_PROMPT",
    "REACH_OUT_PROMPT",
    "MEMORY_PROMPT",
    "SURFACE_PROMPT",
    "DAILY_MESSAGE_PROMPT",
    "FALLBACK_QUOTES",
    "PERSONALIZED_INSIGHTS_PROMPT",
    "NOTE_SYNTHESIS_PROMPT",
    "PLAN_SYNTHESIS_PROMPT",
]
