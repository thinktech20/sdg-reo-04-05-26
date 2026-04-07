"""API v1 route handlers for the Event History Assistant."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Request

from event_history import config
from event_history.core.agent_factory import build_agent
from event_history.prompts import SYSTEM_PROMPT
from event_history.schemas import RunRequest, RunResponse
from event_history.simulate import simulate_run
from event_history.tools.stubs import EVENT_HISTORY_TOOLS

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/run", response_model=RunResponse)
async def run(request_body: RunRequest, http_request: Request) -> RunResponse:
    """Compile event history for an assessment (per-request Strands Agent).

    Builds a fresh Agent for this request: Agent uses threading.Lock internally
    and is not safe to share across concurrent requests.
    """
    logger.info(
        "event-history run requested",
        extra={
            "assessment_id": request_body.assessment_id,
            "esn": request_body.esn,
            "persona": request_body.persona,
            "event_count": len(request_body.event_data),
        },
    )

    if config.AGENT_SIMULATE_MODE:
        return await simulate_run(request_body)

    events_summary = json.dumps(request_body.event_data[:5], default=str)
    prompt = (
        f"Analyse the event history for assessment '{request_body.assessment_id}', "
        f"asset ESN '{request_body.esn}'. "
        f"Requesting persona: {request_body.persona}. "
        f"Event data ({len(request_body.event_data)} events, showing first 5): {events_summary}. "
        "Identify patterns, recurring failures, and key findings from the event history."
    )

    agent = build_agent(
        model=http_request.app.state.litellm_model,
        tools=EVENT_HISTORY_TOOLS,
        system_prompt=SYSTEM_PROMPT,
    )
    try:
        result = await agent.invoke_async(prompt)
        reply_text = result.message["content"][0]["text"]
    finally:
        agent.cleanup()

    return RunResponse(
        status="accepted",
        assessment_id=request_body.assessment_id,
        message=reply_text,
    )
