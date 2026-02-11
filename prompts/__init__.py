"""
Prompts module - All LLM prompts organized by feature.

Import prompts directly:
    from prompts import SYSTEM_FRAME, OBSERVATION_PROMPT

Or import personas:
    from prompts.personas import COMPANION_PERSONA
"""

from prompts.system_frame import SYSTEM_FRAME
from prompts.observation import OBSERVATION_PROMPT
from prompts.reflection import REFLECTION_PROMPT
from prompts.condensation import CONDENSATION_PROMPT
from prompts.proactive import PROACTIVE_MESSAGE_PROMPT
from prompts.compact import COMPACT_PROMPT
from prompts.reach_out import REACH_OUT_PROMPT
from prompts.memory import MEMORY_PROMPT

__all__ = [
    "SYSTEM_FRAME",
    "OBSERVATION_PROMPT",
    "REFLECTION_PROMPT",
    "CONDENSATION_PROMPT",
    "PROACTIVE_MESSAGE_PROMPT",
    "COMPACT_PROMPT",
    "REACH_OUT_PROMPT",
    "MEMORY_PROMPT",
]
