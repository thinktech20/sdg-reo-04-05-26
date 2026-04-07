"""API v1 — all chat endpoints for the Q&A Agent.

Routes:
  POST /api/v1/chat                                — internal contract
  POST /api/assessments/{id}/chat/reliability      — RE persona (frontend contract)
  POST /api/assessments/{id}/chat/outage           — OE persona (frontend contract)
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from question_answer.core import agent_factory
from question_answer.schemas import (
    AssessmentChatAgentResponse,
    AssessmentChatMessage,
    AssessmentChatRequest,
    AssessmentChatResponse,
    ChatRequest,
    ChatResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_ASSESSMENT_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,128}$")


def _extract_serial_number(context: str | dict[str, Any]) -> str | None:
    if not isinstance(context, dict):
        return None

    serial_number = context.get("serialNumber") or context.get("serial_number")
    if not serial_number:
        return None

    normalized = str(serial_number).strip()
    return normalized or None


def _build_assessment_prompt(message: str, assessment_id: str, context: str | dict[str, Any]) -> str:
    serial_number = _extract_serial_number(context)
    if not serial_number:
        return message

    return (
        "Assessment context:\n"
        f"- assessment_id: {assessment_id}\n"
        f"- serial_number: {serial_number}\n\n"
        "Use the serial number above when querying equipment-specific data.\n\n"
        f"User question: {message}"
    )


# ── Internal contract ─────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    request: Request,
) -> ChatResponse:
    """Invoke the Q&A Agent and return a single reply.

    Args:
        body: ChatRequest with prompt, persona, and optional session_id.
        request: FastAPI Request (contains app.state + request.state).

    Returns:
        ChatResponse with reply text and echoed session_id.
    """
    user_context = getattr(request.state, "user_context", None)
    session_id = getattr(request.state, "session_id", None) or body.session_id

    logger.info(
        "chat: session_id=%s persona=%s prompt_len=%d",
        session_id,
        body.persona,
        len(body.prompt),
    )

    try:
        reply = await agent_factory.run_agent(
            prompt=body.prompt,
            persona=body.persona,
            model=request.app.state.litellm_model,
            boto_session=request.app.state.boto_session,
            session_id=session_id,
            user_sso_id=user_context.sso_id if user_context else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Agent invocation failed: %s", exc)
        raise HTTPException(status_code=503, detail="Agent temporarily unavailable") from exc

    return ChatResponse(session_id=session_id, reply=reply)


# ── Frontend contract ─────────────────────────────────────────────────────────

async def _run_assessment_chat(
    assessment_id: str,
    persona: str,
    agent_label: str,
    body: AssessmentChatRequest,
    request: Request,
) -> AssessmentChatResponse:
    """Shared handler for assessment chat endpoints."""
    if not _ASSESSMENT_ID_RE.match(assessment_id):
        raise HTTPException(status_code=422, detail="Invalid assessment_id format")

    user_context = getattr(request.state, "user_context", None)
    now = datetime.now(UTC).isoformat()

    logger.info(
        "assessment_chat: assessment_id=%s persona=%s msg_len=%d context_type=%s serial_number=%s",
        assessment_id,
        persona,
        len(body.message),
        type(body.context).__name__,
        _extract_serial_number(body.context),
    )

    prompt = _build_assessment_prompt(body.message, assessment_id, body.context)

    try:
        reply = await agent_factory.run_agent(
            prompt=prompt,
            persona=persona,
            model=request.app.state.litellm_model,
            boto_session=request.app.state.boto_session,
            session_id=assessment_id,
            user_sso_id=user_context.sso_id if user_context else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Agent invocation failed: %s", exc)
        raise HTTPException(status_code=503, detail="Agent temporarily unavailable") from exc

    reply_timestamp = datetime.now(UTC).isoformat()

    return AssessmentChatResponse(
        response=AssessmentChatAgentResponse(
            message=reply,
            timestamp=reply_timestamp,
            agent=agent_label,
        ),
        chatHistory=[
            AssessmentChatMessage(role="user", content=body.message, timestamp=now),
            AssessmentChatMessage(role="assistant", content=reply, timestamp=reply_timestamp),
        ],
    )


@router.post(
    "/assessments/{assessment_id}/chat/reliability",
    response_model=AssessmentChatResponse,
)
async def chat_reliability(
    assessment_id: str,
    body: AssessmentChatRequest,
    request: Request,
) -> AssessmentChatResponse:
    """RE persona chat — frontend chatSlice contract."""
    return await _run_assessment_chat(assessment_id, "RE", "reliability-agent", body, request)


@router.post(
    "/assessments/{assessment_id}/chat/outage",
    response_model=AssessmentChatResponse,
)
async def chat_outage(
    assessment_id: str,
    body: AssessmentChatRequest,
    request: Request,
) -> AssessmentChatResponse:
    """OE persona chat — frontend chatSlice contract."""
    return await _run_assessment_chat(assessment_id, "OE", "outage-agent", body, request)
