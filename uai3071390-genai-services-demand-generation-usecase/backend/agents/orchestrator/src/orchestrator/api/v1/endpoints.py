"""Orchestrator API v1 routes."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Request

from orchestrator import config, job_store
from orchestrator.schemas import RunAcceptedResponse, RunRequest, StatusResponse

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Progress push helper — fire-and-forget, never blocks the pipeline
# ---------------------------------------------------------------------------

_MAX_PUSH_RETRIES = 3
_PUSH_TIMEOUT_SECONDS = 2.0


async def _push_progress(
    assessment_id: str,
    workflow_id: str,
    active_node: str | None,
    node_timings: dict[str, Any],
    circuit_open: list[bool],  # mutable flag shared across one pipeline run
) -> None:
    """PATCH progress to the data-service.  Retries up to 3x with exponential
    back-off (0.5s → 1s → 2s).  After all retries are exhausted the circuit-open
    flag is set so subsequent node transitions skip the push entirely rather than
    adding cumulative delay to the pipeline."""
    if circuit_open[0]:
        return

    url = (
        f"{config.DATA_SERVICE_URL.rstrip('/')}"
        f"/dataservices/api/v1/internal/assessments/{assessment_id}/execution-state"
    )
    payload: dict[str, Any] = {"workflowId": workflow_id, "nodeTimings": node_timings}
    if active_node is not None:
        payload["activeNode"] = active_node

    for attempt in range(_MAX_PUSH_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=_PUSH_TIMEOUT_SECONDS) as client:
                await client.patch(url, json=payload)
            return  # success — reset nothing, circuit stays closed
        except Exception as exc:  # noqa: BLE001
            wait = 0.5 * (2 ** attempt)  # 0.5s, 1s, 2s
            logger.warning(
                "progress push attempt %d/%d failed assessment_id=%s: %s (retry in %.1fs)",
                attempt + 1, _MAX_PUSH_RETRIES, assessment_id, exc, wait,
            )
            if attempt < _MAX_PUSH_RETRIES - 1:
                await asyncio.sleep(wait)

    # All retries exhausted — open the circuit for this pipeline run
    logger.warning(
        "progress push circuit opened assessment_id=%s — "
        "subsequent node updates will not be pushed",
        assessment_id,
    )
    circuit_open[0] = True


# ---------------------------------------------------------------------------
# Background pipeline runner
# ---------------------------------------------------------------------------


async def _run_pipeline(
    graph: Any,
    assessment_id: str,
    job_type: str,
    esn: str,
    persona: str,
    input_payload: dict[str, Any],
) -> None:
    workflow_id = f"{persona.upper()}_{'DEFAULT' if job_type == 'run' else 'NARRATIVE'}"

    def _now() -> str:
        return datetime.now(UTC).isoformat()

    first_node = "narrative" if job_type == "narrative" else "risk_eval"
    node_timings: dict[str, dict[str, str]] = {first_node: {"startedAt": _now()}}

    # Circuit-open flag: mutable list so the nested helper can flip it. When
    # open, progress pushes are skipped so repeated failures don't stall the
    # pipeline with cumulative retry waits.
    circuit_open: list[bool] = [False]

    job_store.write_job(
        assessment_id, job_type, "RUNNING",
        persona=persona,
        esn=esn,
        activeNode=first_node,
        nodeTimings=dict(node_timings),
    )
    asyncio.create_task(_push_progress(assessment_id, workflow_id, first_node, dict(node_timings), circuit_open))

    initial_state: dict[str, Any] = {
        "assessment_id": assessment_id,
        "job_type": job_type,
        "esn": esn,
        "persona": persona,
        "input_payload": input_payload,
        "current_stage": "starting",
        "error": None,
    }
    config = {"configurable": {"thread_id": f"{assessment_id}:{job_type}:{persona}"}}
    final_state: dict[str, Any] = dict(initial_state)

    try:
        async for chunk in graph.astream(initial_state, config=config):
            for node_name, state_update in chunk.items():
                if node_name.startswith("__"):  # skip internal LangGraph nodes
                    continue
                ts = _now()
                final_state.update(state_update)

                # Mark current node as completed
                if node_name not in node_timings:
                    node_timings[node_name] = {"startedAt": ts}
                node_timings[node_name]["completedAt"] = ts

                job_store.write_job(
                    assessment_id, job_type, "RUNNING",
                    persona=persona,
                    esn=esn,
                    activeNode=None,
                    nodeTimings=dict(node_timings),
                )
                asyncio.create_task(_push_progress(assessment_id, workflow_id, None, dict(node_timings), circuit_open))

        error_msg: str | None = final_state.get("error")
        status = "FAILED" if error_msg else "COMPLETE"
        result: dict[str, Any] = final_state.get("final_result", {})
        result.pop("_raw", None)  # strip debug payload — can push item past DynamoDB 400KB limit
        job_store.write_job(
            assessment_id,
            job_type,
            status,
            persona=persona,
            esn=esn,
            result=result,
            errorMessage=error_msg,
            nodeTimings=dict(node_timings),
        )
    except Exception as exc:
        logger.exception("orchestrator: pipeline failed assessment_id=%s", assessment_id)
        job_store.write_job(
            assessment_id,
            job_type,
            "FAILED",
            persona=persona,
            esn=esn,
            errorMessage=str(exc),
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/health")
@router.get("/orchestrator/")
@router.get("/orchestrator/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "orchestrator"}


@router.post(
    "/api/v1/assessments/{assessment_id}/run",
    response_model=RunAcceptedResponse,
    status_code=202,
    summary="Trigger the LangGraph parallel pipeline for a given assessment",
)
async def run_assessment(
    assessment_id: str,
    body: RunRequest,
    request: Request,
    background_tasks: BackgroundTasks,
) -> RunAcceptedResponse:
    """Accept the job, write PENDING to the job store, and kick off the
    LangGraph pipeline in a FastAPI background task.  Returns 202 immediately
    so the frontend can start polling /status without blocking.
    """
    graph = request.app.state.graph
    job_store.write_job(
        assessment_id,
        body.job_type,
        "PENDING",
        persona=body.persona,
        esn=body.esn,
    )
    background_tasks.add_task(
        _run_pipeline,
        graph,
        assessment_id,
        body.job_type,
        body.esn,
        body.persona,
        body.input_payload,
    )
    return RunAcceptedResponse(
        assessmentId=assessment_id,
        status="PENDING",
    )


@router.get(
    "/api/v1/assessments/{assessment_id}/status",
    response_model=StatusResponse,
    summary="Poll current pipeline status for a given assessment",
)
async def get_status(assessment_id: str, jobType: str = "run") -> StatusResponse:
    """Return the current execution status for an assessment.

    jobType: "run" (A1/A3 phase) | "narrative" (A2 phase)
    Falls back to PENDING if the job hasn't been registered yet.
    """
    job = job_store.read_job(assessment_id, jobType)
    if job:
        return StatusResponse(**job)
    return StatusResponse(
        assessmentId=assessment_id,
        jobType=jobType,
        status="PENDING",
    )
