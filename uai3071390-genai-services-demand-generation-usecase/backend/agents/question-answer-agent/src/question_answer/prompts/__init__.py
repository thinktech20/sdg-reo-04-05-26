"""Persona-specific system prompts for the Q&A Agent.

Each persona (RE, OE) has its own system prompt stored as a .txt file
alongside this module.  The prompts are loaded once at import time and
served via ``get_system_prompt(persona)``.
"""

from __future__ import annotations

from pathlib import Path

_DIR = Path(__file__).resolve().parent

_PROMPTS: dict[str, str] = {
    "RE": (_DIR / "re_system_prompt.txt").read_text(encoding="utf-8"),
    "OE": (_DIR / "oe_system_prompt.txt").read_text(encoding="utf-8"),
}


def get_system_prompt(persona: str) -> str:
    """Return the system prompt for *persona* (case-insensitive).

    Raises ``ValueError`` for unknown personas.
    """
    key = persona.upper()
    prompt = _PROMPTS.get(key)
    if prompt is None:
        raise ValueError(f"Unknown persona: {persona!r}. Must be one of {list(_PROMPTS)}")
    return prompt
