"""
Prompts module - All LLM prompts organized by feature.

Import prompts directly:
    from prompts import COMPANION_SYSTEM_PROMPT, OBSERVATION_PROMPT

Or import from specific modules:
    from prompts.companion import COMPANION_SYSTEM_PROMPT
"""

from prompts.companion import COMPANION_SYSTEM_PROMPT
from prompts.observation import OBSERVATION_PROMPT
from prompts.reflection import REFLECTION_PROMPT, PROFILE_SUMMARY_PROMPT
from prompts.proactive import PROACTIVE_MESSAGE_PROMPT

__all__ = [
    "COMPANION_SYSTEM_PROMPT",
    "OBSERVATION_PROMPT",
    "REFLECTION_PROMPT",
    "PROFILE_SUMMARY_PROMPT",
    "PROACTIVE_MESSAGE_PROMPT",
]
