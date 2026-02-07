"""
Persona definitions.

Each persona is a string that defines the AI's personality and behavior.
It gets slotted into the system frame as the {persona} variable.

Usage:
    from prompts.personas import COMPANION_PERSONA, FRIEND_PERSONA
"""

from prompts.personas.companion import COMPANION_PERSONA
from prompts.personas.friend import FRIEND_PERSONA

__all__ = [
    "COMPANION_PERSONA",
    "FRIEND_PERSONA",
]
