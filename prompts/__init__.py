"""
Prompts module - All LLM prompts organized by feature.

Import prompts directly:
    from prompts import SYSTEM_FRAME, OBSERVATION_PROMPT

Or import personas:
    from prompts.personas import COMPANION_PERSONA
"""

from prompts.system_frame import SYSTEM_FRAME
from prompts.observation import OBSERVATION_PROMPT
from prompts.reflection import REFLECTION_PROMPT, PROFILE_SUMMARY_PROMPT
from prompts.proactive import PROACTIVE_MESSAGE_PROMPT

__all__ = [
    "SYSTEM_FRAME",
    "OBSERVATION_PROMPT",
    "REFLECTION_PROMPT",
    "PROFILE_SUMMARY_PROMPT",
    "PROACTIVE_MESSAGE_PROMPT",
]
