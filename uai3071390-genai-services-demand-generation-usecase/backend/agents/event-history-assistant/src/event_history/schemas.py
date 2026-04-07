"""Pydantic I/O schemas for the Event History Assistant."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class RunRequest(BaseModel):
    """Request body for POST /api/v1/event-history/run."""

    assessment_id: str
    esn: str
    persona: str  # "RE" | "OE"
    event_data: list[dict[str, Any]]  # Records from Read Event Master / Event Report tools


class RunResponse(BaseModel):
    """Response body for POST /api/v1/event-history/run."""

    status: str
    assessment_id: str
    message: str
    # Structured event history list — populated by simulate mode and future LLM-tool integration.
    # Each dict matches the frontend EventRecord interface.
    history_events: list[dict[str, Any]] | None = None
