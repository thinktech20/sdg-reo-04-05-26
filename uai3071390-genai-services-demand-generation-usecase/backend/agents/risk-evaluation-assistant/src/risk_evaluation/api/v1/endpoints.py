"""API v1 route handlers for the Risk Evaluation Assistant."""

from __future__ import annotations

from fastapi import APIRouter, Request
from risk_evaluation.core.config.logger_config import get_logger
from risk_evaluation.core.agent_factory import build_agent
from risk_evaluation.prompts import SYSTEM_PROMPT
from risk_evaluation.schemas import RunRequest, RunResponse
from risk_evaluation.tools.stubs import RISK_EVAL_TOOLS

logger = get_logger(__name__)

router = APIRouter()

@router.post("/run", response_model=RunResponse)
async def run(request_body: RunRequest, http_request: Request) -> RunResponse:
    """Trigger risk evaluation for an assessment (per-request Strands Agent).

    Builds a fresh Agent for this request: Agent uses threading.Lock internally
    and is not safe to share across concurrent requests.
    """
    logger.info(
        "risk-eval run requested",
        extra={
            "assessment_id": request_body.assessment_id,
            "esn": request_body.esn,
            "persona": request_body.persona,
        },
    )

    prompt = (
        f"Evaluate risk for assessment '{request_body.assessment_id}', "
        f"asset ESN '{request_body.esn}'. "
        f"Requesting persona: {request_body.persona}. "
        "Retrieve relevant IBAT and PRISM data, score each risk finding, "
        "and return a structured risk evaluation report."
    )

    agent = build_agent(
        model=http_request.app.state.litellm_model,
        tools=RISK_EVAL_TOOLS,
        system_prompt=SYSTEM_PROMPT,
    )
    logger.info("risk-eval after build agent")
    try:
        result = await agent.invoke_async(prompt)
        logger.info("risk-eval after invoke agent")
        reply_text = result.message["content"][0]["text"]
        logger.info("risk-eval invoke agent message="+reply_text)
    finally:
        agent.cleanup()

    return RunResponse(
        status="accepted",
        assessment_id=request_body.assessment_id,
        message=reply_text,
    )
