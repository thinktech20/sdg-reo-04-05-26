"""Pydantic I/O schemas for the Q&A Agent."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class ChatRequest(BaseModel):
    """Request body for POST /api/v1/chat."""

    prompt: str
    persona: Literal["RE", "OE"] = "RE"
    session_id: str | None = None  # optional — stateless if omitted


class ChatResponse(BaseModel):
    """Response body for POST /api/v1/chat."""

    reply: str
    session_id: str | None = None  # echoed back if provided


# ── Frontend-compatible schemas (POST /api/assessments/{id}/chat/{persona}) ──

class AssessmentChatRequest(BaseModel):
    """Request body matching the frontend chatSlice contract.

    Frontend sends: { message, context }
  context may include assessment metadata such as serialNumber.
    """

    message: str
    context: str | dict[str, Any] = ""


class AssessmentChatMessage(BaseModel):
    """Single chat message in the frontend chatHistory format."""

    role: str  # "user" | "assistant"
    content: str
    timestamp: str


class AssessmentChatAgentResponse(BaseModel):
    """Nested 'response' object the frontend expects inside AssessmentChatResponse."""

    message: str
    timestamp: str
    agent: str  # "reliability-agent" | "outage-agent"


class AssessmentChatResponse(BaseModel):
    """Response body matching the frontend chatSlice contract."""

    response: AssessmentChatAgentResponse
    chatHistory: list[AssessmentChatMessage]  # noqa: N815
