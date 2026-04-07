"""Agent factory for the Narrative Summary Assistant (A2).

Builds shared resources once at startup and a fresh per-request Strands Agent.
A1–A3 are stateless (LangGraph owns session) — no S3SessionManager.
"""

from __future__ import annotations

import logging
from typing import Any

from strands import Agent  # noqa: PLC0415
from strands.models import LiteLLMModel  # noqa: PLC0415

from narrative_summary import config

logger = logging.getLogger(__name__)


def build_model() -> LiteLLMModel:
    """Instantiate LiteLLMModel once at startup."""
    logger.info(
        "Building LiteLLMModel",
        extra={"base_url": config.LITELLM_API_BASE, "model_id": config.LITELLM_MODEL},
    )
    return LiteLLMModel(
        model_id=config.LITELLM_MODEL,
        base_url=config.LITELLM_API_BASE,
        api_key=config.LITELLM_API_KEY,
    )


def build_agent(
    model: LiteLLMModel,
    tools: list[Any],
    system_prompt: str,
) -> Agent:
    """Create a per-request Strands Agent (stateless)."""
    return Agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        callback_handler=None,
    )
