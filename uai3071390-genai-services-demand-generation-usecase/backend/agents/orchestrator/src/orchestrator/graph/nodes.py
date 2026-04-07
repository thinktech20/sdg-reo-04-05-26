"""LangGraph nodes for the Orchestrator pipeline.

Each node is an async callable: PipelineState -> dict (partial state update).
LangGraph merges the returned dict back into the shared PipelineState.

Two separate pipeline invocations:
    job_type="run"
        RE persona: risk_eval (A1) → narrative (A2) → finalize
    OE persona: risk_eval (A1) → event_history (A3) → finalize
  job_type="narrative"  (triggered ONLY after user submits feedback on A1 output)
    both personas: narrative (A2) → finalize

A1 output is immutable.  User feedback on A1 rows is stored by the data-service
feedback API and acts as the gate that allows the frontend to call /analyze/narrative.

Downstream calls use per-request httpx.AsyncClient (no shared connection pool --
  matches the per-request Strands Agent pattern used in A1-A3).

State writes to DynamoDB go through FOUNDATION_SERVICE_URL, never boto3 directly.
  This skeleton leaves those calls as stubs with clear markers.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from orchestrator import config
from orchestrator.graph.state import PipelineState

logger = logging.getLogger(__name__)


async def _call_agent(url: str, payload: dict) -> dict:  # type: ignore[type-arg]
    """POST to a downstream agent with retry on transient errors.

    Retries on:
      - httpx.TimeoutException  — agent is still starting or a slow MCP call
      - httpx.NetworkError      — transient connectivity blip
      - HTTP 5xx responses      — agent pod restarting / temporary failure

    Does NOT retry on 4xx (bad request — retrying won't help).
    Backoff: attempt N waits N × AGENT_CALL_RETRY_BACKOFF_SECS before the call.
    """
    last_exc: Exception | None = None
    timeout = config.AGENT_CALL_TIMEOUT_SECS if config.AGENT_CALL_TIMEOUT_SECS > 0 else None
    for attempt in range(config.AGENT_CALL_MAX_RETRIES):
        if attempt > 0:
            backoff = config.AGENT_CALL_RETRY_BACKOFF_SECS * attempt
            logger.warning(
                "orchestrator: retrying agent call url=%s attempt=%d/%d backoff=%.1fs",
                url,
                attempt + 1,
                config.AGENT_CALL_MAX_RETRIES,
                backoff,
            )
            await asyncio.sleep(backoff)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                return resp.json()
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            logger.warning(
                "orchestrator: agent call transient error url=%s attempt=%d/%d error=%s",
                url,
                attempt + 1,
                config.AGENT_CALL_MAX_RETRIES,
                exc,
            )
            last_exc = exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code >= 500:
                logger.warning(
                    "orchestrator: agent call 5xx url=%s attempt=%d/%d status=%d",
                    url,
                    attempt + 1,
                    config.AGENT_CALL_MAX_RETRIES,
                    exc.response.status_code,
                )
                last_exc = exc
            else:
                raise  # 4xx — not retryable
    raise last_exc  # type: ignore[misc]


def _normalize_risk_categories(risk_eval_resp: dict) -> dict:  # type: ignore[type-arg]
    risk_categories = risk_eval_resp.get("riskCategories")
    if isinstance(risk_categories, dict):
        return {str(key): value for key, value in risk_categories.items() if isinstance(value, dict)}

    findings = risk_categories if isinstance(risk_categories, list) else risk_eval_resp.get("findings")
    if not isinstance(findings, list):
        return {}

    normalized: dict = {}  # type: ignore[type-arg]
    for index, finding in enumerate(findings, start=1):
        if not isinstance(finding, dict):
            continue
        finding_id = str(finding.get("id") or f"finding-{index}")
        normalized[finding_id] = finding
    return normalized


async def risk_eval_node(state: PipelineState) -> dict:  # type: ignore[type-arg]
    """Call A1 risk-evaluation-assistant and store result.

    POST {RISK_EVAL_URL}/riskevaluationassistant/api/v1/risk-eval/run
    """
    logger.info("orchestrator: risk_eval_node start assessment_id=%s", state["assessment_id"])
    updated: dict = {"current_stage": "risk_eval"}  # type: ignore[type-arg]

    if config.ORCHESTRATOR_LOCAL_MODE:
        updated["risk_eval_result"] = {"stub": True, "stage": "risk_eval"}
        return updated

    try:
        input_payload = state.get("input_payload", {})
        filters = input_payload.get("filters") if isinstance(input_payload.get("filters"), dict) else {}
        data_types = input_payload.get("dataTypes")
        if not isinstance(data_types, list):
            data_types = input_payload.get("data_types")
        date_from = input_payload.get("dateFrom")
        if date_from is None:
            date_from = input_payload.get("date_from")
        date_to = input_payload.get("dateTo")
        if date_to is None:
            date_to = input_payload.get("date_to")
        if not isinstance(data_types, list):
            data_types = filters.get("data_types") if isinstance(filters.get("data_types"), list) else []
        if not isinstance(data_types, list):
            data_types = filters.get("dataTypes") if isinstance(filters.get("dataTypes"), list) else []
        if date_from is None:
            date_from = filters.get("date_from")
        if date_from is None:
            date_from = filters.get("dateFrom")
        if date_to is None:
            date_to = filters.get("date_to")
        if date_to is None:
            date_to = filters.get("dateTo")

        normalized_filters = {
            "data_types": data_types or [],
            "date_from": date_from,
            "date_to": date_to,
        }

        component_type = (
            input_payload.get("component_type")
            or input_payload.get("componentType")
            or input_payload.get("equipmentType")
            or input_payload.get("component")
        )
        updated["risk_eval_result"] = await _call_agent(
            f"{config.RISK_EVAL_URL}/riskevaluationassistant/api/v1/risk-eval/run",
            {
                "assessment_id": state["assessment_id"],
                "query": (
                    f"Generate a {state.get('persona', 'RE')} risk assessment for "
                    f"assessment {state['assessment_id']} and equipment ESN {state.get('esn', '')}."
                ),
                "esn": state.get("esn", ""),
                "component_type": component_type,
                "persona": state.get("persona", "RE"),
                "workflowId": input_payload.get("workflowId"),
                "reviewPeriod": input_payload.get("reviewPeriod"),
                "unitNumber": input_payload.get("unitNumber"),
                "filters": normalized_filters,
            },
        )
    except Exception as exc:
        logger.exception("orchestrator: risk_eval_node failed")
        updated["error"] = str(exc)

    return updated


async def narrative_node(state: PipelineState) -> dict:  # type: ignore[type-arg]
    """Call A2 narrative-summary-assistant and store result.

    Invoked only for job_type="narrative", AFTER the user has submitted feedback
    on every row of the A1 risk table.  A2 reads the stored A1 output and user
    feedback from DynamoDB (via the Foundation Service) to generate the narrative.

    POST {NARRATIVE_SUMMARY_URL}/summarizationassistant/api/v1/narrative/run
    """
    logger.info("orchestrator: narrative_node start assessment_id=%s", state["assessment_id"])
    updated: dict = {"current_stage": "narrative"}  # type: ignore[type-arg]

    if config.ORCHESTRATOR_LOCAL_MODE:
        updated["narrative_result"] = {"stub": True, "stage": "narrative"}
        return updated

    try:
        updated["narrative_result"] = await _call_agent(
            f"{config.NARRATIVE_SUMMARY_URL}/summarizationassistant/api/v1/narrative/run",
            {
                "assessment_id": state["assessment_id"],
                "esn": state.get("esn", ""),
                "persona": state.get("persona", "RE"),
                # When A2 runs as part of RE_DEFAULT, provide A1 output context directly.
                "risk_eval_result": state.get("risk_eval_result", {}),
            },
        )
    except Exception as exc:
        logger.exception("orchestrator: narrative_node failed")
        updated["error"] = str(exc)

    return updated


async def event_history_node(state: PipelineState) -> dict:  # type: ignore[type-arg]
    """Call A3 event-history-assistant and store result.

    POST {EVENT_HISTORY_URL}/eventhistoryassistant/api/v1/event-history/run
    """
    logger.info("orchestrator: event_history_node start assessment_id=%s", state["assessment_id"])
    updated: dict = {"current_stage": "event_history"}  # type: ignore[type-arg]

    if config.ORCHESTRATOR_LOCAL_MODE:
        updated["event_history_result"] = {"stub": True, "stage": "event_history"}
        return updated

    try:
        updated["event_history_result"] = await _call_agent(
            f"{config.EVENT_HISTORY_URL}/eventhistoryassistant/api/v1/event-history/run",
            {
                "assessment_id": state["assessment_id"],
                "esn": state.get("esn", ""),
                "persona": state.get("persona", "OE"),
                # OE risk_eval result passed as context so A3 can cross-reference
                # the Other Repairs risk categories when generating Event History.
                "risk_eval_result": state.get("risk_eval_result", {}),
            },
        )
    except Exception as exc:
        logger.exception("orchestrator: event_history_node failed")
        updated["error"] = str(exc)

    return updated


async def finalize_node(state: PipelineState) -> dict:  # type: ignore[type-arg]
    """Aggregate node results into a single result dict; mark pipeline COMPLETE.

    job_type="run":
      - RE: riskCategories (A1 output) only
      - OE: riskCategories (A1) + events (A3)
    job_type="narrative":
      - narrativeSummary (A2 output) only

    A1 output is immutable — user feedback is stored separately by the data-service
    feedback API and never re-runs A1.

    Status propagation: _run_pipeline in endpoints.py reads final_result from
    final_state after the graph completes and writes "COMPLETE" to the job store.
    data-service polls GET /api/v1/assessments/{id}/status, picks up COMPLETE,
    then calls _persist_result to write domain data to DynamoDB.
    """
    logger.info("orchestrator: finalize_node assessment_id=%s", state["assessment_id"])

    job_type = str(state.get("job_type", "run"))
    persona = str(state.get("persona", "RE")).upper()

    final_result: dict = {"_raw": {}}  # type: ignore[type-arg]

    if job_type == "narrative":
        narrative_resp = state.get("narrative_result", {})
        final_result["narrativeSummary"] = (
            narrative_resp.get("narrative_summary")
            or narrative_resp.get("narrativeSummary")
            or narrative_resp.get("message", "")
        )
        final_result["_raw"]["narrative"] = narrative_resp
    else:
        risk_eval_resp = state.get("risk_eval_result", {})
        # Promote data (raw LLM rows) and findings (flat per-row findings) to top level
        # so data-service _persist_result can read them without digging into _raw.
        final_result["data"] = risk_eval_resp.get("data") or []
        final_result["findings"] = risk_eval_resp.get("findings") or []
        final_result["riskCategories"] = _normalize_risk_categories(risk_eval_resp)
        final_result["retrieval"] = (
            risk_eval_resp.get("retrieval")
            if isinstance(risk_eval_resp.get("retrieval"), dict)
            else {}
        )
        final_result["_raw"]["risk_eval"] = risk_eval_resp

        if persona == "RE":
            narrative_resp = state.get("narrative_result", {})
            final_result["narrativeSummary"] = (
                narrative_resp.get("narrative_summary")
                or narrative_resp.get("narrativeSummary")
                or narrative_resp.get("message", "")
            )
            final_result["_raw"]["narrative"] = narrative_resp

        if persona == "OE":
            event_history_resp = state.get("event_history_result", {})
            final_result["events"] = (
                event_history_resp.get("history_events")
                or event_history_resp.get("events")
                or []
            )
            final_result["_raw"]["event_history"] = event_history_resp

    return {"current_stage": "COMPLETE", "final_result": final_result}
