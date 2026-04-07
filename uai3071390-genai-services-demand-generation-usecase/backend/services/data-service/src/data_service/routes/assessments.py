"""
Assessments routes.

POST /api/assessments
GET  /api/assessments/{id}
POST /api/assessments/{id}/analyze/run           → 202  (persona: RE|OE)
GET  /api/assessments/{id}/status?workflowId=
PUT  /api/assessments/{id}/reliability
PUT  /api/assessments/{id}/outage
POST /api/assessments/{id}/findings/{findingId}/feedback

Job status flow:
    - USE_MOCK_ASSESSMENTS=true  → analysis runs synchronously via mock services, job written as COMPLETE
    - USE_MOCK_ASSESSMENTS=false → write PENDING, background task calls orchestrator (routes by persona),
                                                                 polls until done, persists result to the appropriate DynamoDB table

Persona routing:
  RE (Reliability Engineer) → orchestrator runs risk_eval → narrative pipeline
  OE (Outage Engineer)      → orchestrator runs event_history pipeline
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict

from data_service import config
from data_service.db import event_history as event_history_store
from data_service.db import narrative_summary as narrative_summary_store
from data_service.db import risk_analysis as risk_analysis_store
from data_service.mock_services.assessments import (
    SAMPLE_ASSESSMENTS,
    analyze_outage,
    analyze_reliability,
    create_assessment,
    get_all_assessments,
    get_assessment,
    update_assessment,
    update_outage_scope,
    update_reliability_findings,
)
from data_service.db import assessments as db_assessments

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dataservices/api/v1/assessments", tags=["assessments"])


def _map_risk_level_to_display(risk_level: str) -> str:
    """Map riskLevel stored in riskCategory conditions (High/Medium/Low) back to
    the display labels used throughout the UI and narrative (Heavy/Med/Light)."""
    return {"high": "Heavy", "medium": "Med", "low": "Light"}.get(
        str(risk_level).lower(), risk_level
    )


def _format_findings_output(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    formatted_findings: list[dict[str, Any]] = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue

        # The finding ID may live at top-level ("id", "findingId") or inside
        # the "_meta" dict depending on which write path persisted it.
        meta = finding.get("_meta") or {}
        finding_id = (
            finding.get("id")
            or finding.get("findingId")
            or (meta.get("id") if isinstance(meta, dict) else None)
            or (meta.get("findingId") if isinstance(meta, dict) else None)
            or ""
        )

        # Support both LLM flat-row field names (Title Case / sentence case) and
        # riskCategory condition field names (camelCase / lowercase) so that
        # _format_findings_output works regardless of which store is the source.
        risk_raw = finding.get("Risk") or _map_risk_level_to_display(
            finding.get("riskLevel") or ""
        )

        formatted_finding = {
            "id": str(finding_id),
            "Issue name": (
                finding.get("Issue name")
                or finding.get("issueName")
                or finding.get("name")
                or finding.get("category")
                or ""
            ),
            "Component and Issue Grouping": (
                finding.get("Component and Issue Grouping")
                or finding.get("category")
                or ""
            ),
            "Condition": finding.get("Condition") or finding.get("condition") or "",
            "Threshold": finding.get("Threshold") or finding.get("threshold") or "",
            "Actual Value": finding.get("Actual Value") or finding.get("actualValue") or "",
            "Risk": risk_raw,
            "Evidence": finding.get("Evidence") or finding.get("evidence") or "",
            "Citation": finding.get("Citation") or finding.get("primaryCitation") or "",
            "justification": finding.get("justification") or "",
            "Ambiguity handling": (
                finding.get("Ambiguity handling") or finding.get("ambiguityHandling") or ""
            ),
            "_meta": meta,
        }

        formatted_findings.append(formatted_finding)

    return formatted_findings


def _serialize_narrative_summary_for_storage(narrative: Any) -> str:
    if isinstance(narrative, str):
        return narrative
    if isinstance(narrative, (dict, list)):
        return json.dumps(narrative, ensure_ascii=True)
    return str(narrative)


def _format_feedback_output(feedback_map: dict[str, Any]) -> dict[str, Any]:
    formatted_feedback: dict[str, Any] = {}

    def _rating_to_correctness(rating_value: Any) -> str:
        try:
            rating_int = int(rating_value)
        except (TypeError, ValueError):
            return ""
        if rating_int >= 4:
            return "Heavy"
        if rating_int == 3:
            return "Medium"
        if rating_int > 0:
            return "Light"
        return ""

    for finding_id in sorted(feedback_map.keys()):
        feedback = feedback_map.get(finding_id)
        if not isinstance(feedback, dict):
            continue

        formatted_entry = dict(feedback)
        rating = formatted_entry.get("rating")
        if rating is not None:
            try:
                formatted_entry["rating"] = int(rating)
            except (TypeError, ValueError):
                pass

        # Keep canonical feedback correction available for narrative generation.
        raw_correctness = str(
            formatted_entry.get("correctness")
            or formatted_entry.get("feedbackType")
            or ""
        ).strip()

        if raw_correctness.lower() in {"correct", "false-positive", "false-negative"}:
            raw_correctness = _rating_to_correctness(formatted_entry.get("rating")) or raw_correctness

        correctness = raw_correctness or _rating_to_correctness(formatted_entry.get("rating"))
        if correctness:
            formatted_entry["correctness"] = correctness
            formatted_entry["feedbackType"] = correctness

        formatted_feedback[finding_id] = formatted_entry

    return formatted_feedback


# ── Request models ────────────────────────────────────────────────────────────


class CreateAssessmentRequest(BaseModel):
    esn: str
    persona: str = "RE"  # RE | OE
    workflowId: str = "RE_DEFAULT"  # noqa: N815  RE_DEFAULT | OE_DEFAULT
    unitNumber: str | None = None  # noqa: N815
    component: str | None = None
    milestone: str | None = None  # deprecated; accepted for backward compatibility
    reviewPeriod: str | None = None  # noqa: N815  e.g. "18-month"
    equipmentType: str | None = None  # noqa: N815  e.g. "Generator"
    dataTypes: list[str] | None = None  # noqa: N815  selected data source IDs
    createdBy: str = "user_001"  # noqa: N815
    dateFrom: str | None = None  # noqa: N815  ISO-8601 date e.g. "2025-01-01"
    dateTo: str | None = None  # noqa: N815  ISO-8601 date e.g. "2025-12-31"


class AnalyzeRequest(BaseModel):
    """Payload for POST /analyze/run — persona drives orchestrator routing.

    workflowId may be passed explicitly (e.g. RE_NARRATIVE for narrative regeneration).
    When omitted the backend derives it as {persona}_DEFAULT.
    """

    persona: str = "RE"  # RE (Reliability Engineer) | OE (Outage Engineer)
    workflowId: str | None = None  # noqa: N815  explicit override e.g. RE_NARRATIVE
    model_config = ConfigDict(extra="allow")


class WriteRiskAnalysisRequest(BaseModel):
    """Combined payload for POST /{assessment_id}/risk-analysis — persist findings + retrieval in one call."""

    findings: list[dict[str, Any]]
    retrieval: dict[str, Any] | None = None  # optional retrieval evidence

class NarrativeRequest(BaseModel):
    """Payload for POST /analyze/narrative — triggers A2 after user submits feedback."""

    persona: str = "RE"  # RE | OE


class UpdateBody(BaseModel):
    """Generic update body — forwards all fields as-is."""

    model_config = ConfigDict(extra="allow")

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    userId: str = "user_001"  # noqa: N815
    userName: str = "Demo User"  # noqa: N815
    # Frontend sends feedback='up'|'down' + feedbackType; map to canonical fields
    feedback: str | None = None          # 'up' | 'down' | None
    feedbackType: str | None = None      # 'correct' | 'false-positive' | etc.  # noqa: N815
    correctness: str | None = None
    rating: int = 0                      # derived: 1=up, -1=down, 0=unset
    comments: str = ""
    helpful: bool = True

    def model_post_init(self, __context: object) -> None:  # noqa: ANN001
        """Derive rating + helpful from the frontend 'feedback' field."""
        if self.feedback == "up":
            self.rating = 1
            self.helpful = True
        elif self.feedback == "down":
            self.rating = -1
            self.helpful = False

        normalized = str(self.correctness or self.feedbackType or "").strip()
        if normalized:
            self.correctness = normalized
            self.feedbackType = normalized


# ── Orchestrator integration ───────────────────────────────────────────────────

_POLL_INTERVAL_SECONDS = config.ORCHESTRATOR_POLL_INTERVAL_SECONDS
_POLL_MAX_ATTEMPTS = config.ORCHESTRATOR_POLL_MAX_ATTEMPTS


async def _invoke_orchestrator(
    assessment_id: str,
    workflow_id: str,
    esn: str,
    persona: str,
    input_payload: dict[str, Any],
) -> None:
    """
    Background task: POST run request to the orchestrator, poll until done,
    then persist the result to the appropriate DynamoDB table.

    workflow_id identifies the execution row (RE_DEFAULT, OE_DEFAULT, RE_NARRATIVE, OE_NARRATIVE).
    The orchestrator receives job_type="run" for analysis or "narrative" for narrative.
    """
    orchestrator_base = config.ORCHESTRATOR_URL.rstrip("/")
    run_url = f"{orchestrator_base}/orchestrator/api/v1/assessments/{assessment_id}/run"
    status_url = f"{orchestrator_base}/orchestrator/api/v1/assessments/{assessment_id}/status"

    # Map workflow_id to orchestrator job_type
    orchestrator_job_type = "run" if workflow_id in ("RE_DEFAULT", "OE_DEFAULT") else "narrative"  # RE_NARRATIVE / OE_NARRATIVE → "narrative"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            run_resp = await client.post(
                run_url,
                json={
                    "assessment_id": assessment_id,
                    "job_type": orchestrator_job_type,
                    "esn": esn,
                    "persona": persona,
                    "input_payload": input_payload,
                },
            )
            run_resp.raise_for_status()

        db_assessments.update_execution_state(assessment_id, workflow_id=workflow_id, workflow_status="IN_PROGRESS")

        # Poll orchestrator until terminal state.
        # _POLL_MAX_ATTEMPTS <= 0 means no timeout (run until COMPLETE/FAILED).
        attempt = 0
        while _POLL_MAX_ATTEMPTS <= 0 or attempt < _POLL_MAX_ATTEMPTS:
            attempt += 1
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    poll_resp = await client.get(
                        status_url, params={"jobType": orchestrator_job_type}
                    )
                    poll_resp.raise_for_status()
                    data = poll_resp.json()
            except httpx.HTTPError as exc:
                logger.warning(
                    "Orchestrator poll error (attempt %d/%d): %s",
                    attempt + 1,
                    _POLL_MAX_ATTEMPTS,
                    exc,
                )
                continue

            orchestrator_status: str = data.get("status", "RUNNING")

            if orchestrator_status in ("RUNNING", "PENDING"):
                # Forward live node progress so the frontend can show which agent
                # is currently running.
                active_node: str | None = data.get("activeNode")
                node_timings: dict | None = data.get("nodeTimings")
                if active_node or node_timings:
                    db_assessments.update_execution_state(
                        assessment_id,
                        workflow_id=workflow_id,
                        active_node=active_node,
                        node_timings=node_timings,
                    )

            if orchestrator_status == "COMPLETE":
                result = data.get("result") or {}
                _persist_result(assessment_id, workflow_id, persona, result, esn)
                db_assessments.update_execution_state(assessment_id, workflow_id=workflow_id, workflow_status="COMPLETED")
                # Warm up the QnA session so the first user chat has context
                if not workflow_id.endswith("_NARRATIVE"):
                    await _init_qna_session(assessment_id, persona, result)
                return

            if orchestrator_status == "FAILED":
                db_assessments.update_execution_state(
                    assessment_id,
                    workflow_id=workflow_id,
                    workflow_status="FAILED",
                    error_message=data.get("errorMessage", "Orchestrator reported failure"),
                )
                return

        # Timed out
        db_assessments.update_execution_state(
            assessment_id,
            workflow_id=workflow_id,
            workflow_status="FAILED",
            error_message="Orchestrator did not complete within the timeout window",
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error invoking orchestrator for %s/%s", assessment_id, workflow_id)
        db_assessments.update_execution_state(assessment_id, workflow_id=workflow_id, workflow_status="FAILED", error_message=str(exc))


# ── Findings grouping ─────────────────────────────────────────────────────────

# v1 constant: all findings are grouped under a single "Rewind" operation.
# When v2 adds more operations, make this a parameter passed from the orchestrator.
_OPERATION_V1 = "Rewind"


def _group_by_operation(
    flat_findings: list[dict[str, Any]],
    operation: str = _OPERATION_V1,
) -> list[dict[str, Any]]:
    """Group flat per-row findings by (component, operation) into RiskCategory objects.

    Each input finding has one condition.  Findings sharing the same component
    are merged into a single RiskCategory with N conditions.
    The overall risk of the group is the highest severity across all its conditions.
    """
    _RISK_ORDER = {"Heavy": 3, "Medium": 2, "Light": 1}

    def _to_overall_risk(value: Any) -> str:
        text = str(value or "").strip().lower()
        if any(token in text for token in ("immediate", "heavy", "high")):
            return "Heavy"
        if "med" in text:
            return "Medium"
        return "Light"

    def _to_condition_risk_level(value: Any) -> str:
        text = str(value or "").strip().lower()
        if any(token in text for token in ("immediate", "heavy", "high")):
            return "High"
        if "med" in text:
            return "Medium"
        return "Low"

    def _condition_from_row(finding: dict[str, Any], fallback_id: str, component: str) -> dict[str, Any]:
        source_ref = str(
            finding.get("primaryCitation")
            or finding.get("Citation")
            or finding.get("Source Reference")
            or finding.get("sourceDocId")
            or ""
        )
        cond_id = str(finding.get("findingId") or finding.get("id") or fallback_id)
        severity = finding.get("riskLevel") or finding.get("Risk") or finding.get("severity") or finding.get("overallRisk")
        return {
            "id": cond_id,
            "findingId": cond_id,
            "issueName": str(
                finding.get("Issue name")
                or finding.get("issueName")
                or finding.get("condition")
                or finding.get("Condition")
                or ""
            ),
            "category": str(
                finding.get("category")
                or finding.get("Component and Issue Grouping")
                or component
            ),
            "condition": str(
                finding.get("condition")
                or finding.get("Condition")
                or finding.get("description")
                or finding.get("Issue name")
                or ""
            ),
            "threshold": str(finding.get("threshold") or finding.get("Threshold") or ""),
            "actualValue": str(finding.get("actualValue") or finding.get("Actual Value") or ""),
            "riskLevel": _to_condition_risk_level(severity),
            "testMethod": str(finding.get("testMethod") or ""),
            "evidence": str(finding.get("evidence") or finding.get("Evidence") or finding.get("excerptText") or ""),
            "dataSource": str(finding.get("dataSource") or finding.get("Datasource") or ""),
            "justification": str(finding.get("justification") or finding.get("Severity Rationale") or ""),
            "primaryCitation": source_ref,
            "additionalCitations": finding.get("additionalCitations") if isinstance(finding.get("additionalCitations"), list) else [],
            "status": str(finding.get("status") or "complete"),
        }

    _COMPONENT_CANONICAL: dict[str, str] = {
        "stator": "Stator",
        "rotor": "Rotor",
        "field": "Rotor",
    }

    def _canonical_component(raw: str) -> str:
        lower = raw.lower()
        for token, canonical in _COMPONENT_CANONICAL.items():
            if token in lower:
                return canonical
        return raw.strip() or "General"

    groups: dict[str, dict[str, Any]] = {}

    for finding in flat_findings:
        if not isinstance(finding, dict):
            continue
        component = _canonical_component(str(finding.get("component") or "General"))
        slug = f"{component.lower().replace(' ', '-')}-{operation.lower()}"
        group = groups.get(slug)
        if group is None:
            group = {
                "id": slug,
                "name": f"{component} {operation} Risk",
                "component": component,
                "operation": operation,
                "overallRisk": "Light",
                "processDocument": finding.get("processDocument", ""),
                "reliabilityModelRef": finding.get("reliabilityModelRef", ""),
                "description": f"{component} {operation} risk assessment",
                "conditions": [],
            }
            groups[slug] = group

        # Preserve assistant-provided condition IDs when available.
        # If findings arrive in flat row format, synthesize one condition row.
        conditions = finding.get("conditions")
        if isinstance(conditions, list) and conditions:
            for cond in conditions:
                if isinstance(cond, dict):
                    i = len(group["conditions"]) + 1
                    cond_id = str(cond.get("findingId") or cond.get("id") or f"{slug}-condition-{i}")
                    new_cond = {**cond, "id": cond_id, "findingId": cond_id}
                    group["conditions"].append(new_cond)
        else:
            i = len(group["conditions"]) + 1
            group["conditions"].append(_condition_from_row(finding, f"{slug}-condition-{i}", component))

        # Elevate group overallRisk if this finding is higher
        finding_risk = _to_overall_risk(finding.get("overallRisk"))
        if _RISK_ORDER.get(finding_risk, 0) > _RISK_ORDER.get(str(group["overallRisk"]), 0):
            group["overallRisk"] = finding_risk

    grouped = list(groups.values())
    for group in grouped:
        n = len(group["conditions"])
        group["description"] = f"{group['component']} {operation} risk assessment — {n} evidence record{'s' if n != 1 else ''} evaluated"
    # Sort categories: Heavy first, then Medium, then Light
    grouped.sort(key=lambda g: _RISK_ORDER.get(str(g.get("overallRisk", "")), 0), reverse=True)
    return grouped


def _persist_result(assessment_id: str, workflow_id: str, persona: str, result: dict[str, Any], esn: str = "") -> None:
    """Write orchestrator results to the appropriate domain table and update assessment status."""
    if workflow_id.endswith("_NARRATIVE"):
        narrative = result.get("narrativeSummary", "")
        if narrative:
            # DynamoDB narrative_summary.summary is a string attribute, so serialize
            # structured object/list payloads before writing to preserve the table contract.
            narrative_summary_store.write_narrative_summary(
                esn,
                assessment_id,
                persona,
                _serialize_narrative_summary_for_storage(narrative),
            )
    elif persona == "RE":
        raw_rows = result.get("data") or result.get("rawRows") or []
        if not isinstance(raw_rows, list):
            raw_rows = []

        grouped_findings = _group_by_operation(raw_rows)
        if not grouped_findings:
            fallback = result.get("riskCategories") or result.get("findings") or []
            if isinstance(fallback, dict):
                grouped_findings = [item for item in fallback.values() if isinstance(item, dict)]
            elif isinstance(fallback, list):
                grouped_findings = [item for item in fallback if isinstance(item, dict)]

        summary = result.get("summary") or result.get("message") or result.get("result") or None
        risk_analysis_store.write_risk_analysis(
            esn,
            assessment_id,
            raw_rows,
            grouped_findings,
            summary=str(summary) if summary else None,
        )

        retrieval_payload = result.get("retrieval")
        if isinstance(retrieval_payload, dict) and retrieval_payload:
            try:
                risk_analysis_store.write_retrieval(assessment_id, retrieval_payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "write_retrieval skipped assessment_id=%s — payload may exceed DynamoDB 400KB limit: %s",
                    assessment_id, exc,
                )

        # RE_DEFAULT pipeline runs risk_eval → narrative in one workflow.
        # Persist narrative summary if the orchestrator returned it.
        narrative = result.get("narrativeSummary", "")
        if narrative:
            # DynamoDB narrative_summary.summary is a string attribute, so serialize
            # structured object/list payloads before writing to preserve the table contract.
            narrative_summary_store.write_narrative_summary(
                esn,
                assessment_id,
                persona,
                _serialize_narrative_summary_for_storage(narrative),
            )
        update_assessment(assessment_id, {"workflowStatus": "COMPLETED", "reliabilityStatus": "completed"})
    elif persona == "OE":
        events = result.get("events") or result.get("eventHistory") or []
        if isinstance(events, dict):
            events = list(events.values())
        event_history_store.write_event_history(esn, assessment_id, events)
        update_assessment(assessment_id, {"workflowStatus": "COMPLETED", "outageStatus": "completed"})


async def _init_qna_session(
    assessment_id: str,
    persona: str,
    result: dict[str, Any],
) -> None:
    """Fire-and-forget: tell the Q&A agent about a completed assessment so it
    has context for the first user prompt without needing a cold-start retrieval.
    Failures are logged but do NOT propagate — analysis is already complete.
    """
    qna_base = config.QNA_AGENT_URL.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{qna_base}/questionansweragent/api/v1/sessions/init",
                json={
                    "assessment_id": assessment_id,
                    "persona": persona,
                    "context": result,
                },
            )
        logger.info("qna session init sent assessment_id=%s persona=%s", assessment_id, persona)
    except Exception as exc:  # noqa: BLE001
        logger.warning("qna session init failed assessment_id=%s: %s", assessment_id, exc)


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("")
async def list_assessments(
    status: str = Query(default=""),
    esn: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
) -> dict[str, Any]:
    """Return all assessments with optional status, ESN, or date-range filter."""
    return {"assessments": get_all_assessments(status=status, esn=esn, date_from=date_from, date_to=date_to)}


@router.post("", status_code=201)
async def create_new_assessment(request: CreateAssessmentRequest) -> dict[str, Any]:
    assessment = create_assessment(request.model_dump())
    return {"assessment": assessment}


@router.get("/{assessment_id}")
async def get_assessment_by_id(assessment_id: str) -> dict[str, Any]:
    assessment = get_assessment(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return {"assessment": assessment}


@router.get("/{assessment_id}/findings")
async def get_findings(assessment_id: str, request: Request) -> dict[str, Any]:
    """Return raw risk findings and per-finding feedback for an assessment.

    Used internally by the Narrative Summary Assistant to fetch scored findings
    (with any user feedback attached) before generating the narrative.
    """
    if request.url.path.startswith("/api/"):
        seeded = SAMPLE_ASSESSMENTS.get(assessment_id)
        if isinstance(seeded, dict):
            seeded_reliability = seeded.get("reliability") if isinstance(seeded.get("reliability"), dict) else {}
            seeded_rows = seeded_reliability.get("riskCategories") if isinstance(seeded_reliability.get("riskCategories"), list) else []
            seeded_feedback_rows = seeded.get("feedback") if isinstance(seeded.get("feedback"), list) else []
            seeded_feedback_map = {
                str(item.get("findingId", "")): item
                for item in seeded_feedback_rows
                if isinstance(item, dict) and item.get("findingId")
            }
            return {
                "assessmentId": assessment_id,
                "findings": _format_findings_output(seeded_rows),
                "summary": str(seeded_reliability.get("summary") or ""),
                "feedback": _format_feedback_output(seeded_feedback_map),
            }

    ra = risk_analysis_store.read_risk_analysis(assessment_id)
    if not ra:
        raise HTTPException(status_code=404, detail="No findings for this assessment")

    # Prefer the grouped findings (riskCategories) stored under "findings" — each
    # condition inside has a stable id/findingId that matches the feedback keys.
    # rawRows are the raw LLM flat rows which have no id, so feedback can never be
    # matched against them.
    grouped_findings = ra.get("findings") if isinstance(ra.get("findings"), list) else []
    if grouped_findings:
        # Flatten conditions out of their riskCategory groups so _format_findings_output
        # receives one flat row per condition (same shape as rawRows but with id present).
        flat_rows: list[dict[str, Any]] = []
        for group in grouped_findings:
            if not isinstance(group, dict):
                continue
            conditions = group.get("conditions")
            if isinstance(conditions, list) and conditions:
                for cond in conditions:
                    if isinstance(cond, dict):
                        flat_rows.append(cond)
            else:
                flat_rows.append(group)
        source_rows = flat_rows if flat_rows else grouped_findings
    else:
        # Fallback: rawRows (no IDs — feedback won't match, but findings still shown)
        source_rows = ra.get("rawRows") if isinstance(ra.get("rawRows"), list) else []

    if not source_rows:
        seeded_assessment = get_assessment(assessment_id)
        reliability = (
            seeded_assessment.get("reliability")
            if isinstance(seeded_assessment, dict)
            else None
        )
        if isinstance(reliability, dict) and isinstance(reliability.get("riskCategories"), list):
            source_rows = reliability["riskCategories"]

    feedback_map = ra.get("feedback", {})
    formatted_feedback = _format_feedback_output(feedback_map if isinstance(feedback_map, dict) else {})
    if not formatted_feedback:
        seeded = SAMPLE_ASSESSMENTS.get(assessment_id)
        seeded_feedback_rows = seeded.get("feedback") if isinstance(seeded, dict) else None
        if isinstance(seeded_feedback_rows, list):
            seeded_feedback_map = {
                str(item.get("findingId", "")): item
                for item in seeded_feedback_rows
                if isinstance(item, dict) and item.get("findingId")
            }
            formatted_feedback = _format_feedback_output(seeded_feedback_map)

    return {
        "assessmentId": assessment_id,
        "findings": _format_findings_output(source_rows if isinstance(source_rows, list) else []),
        "summary": ra.get("summary", ""),  ## To be removed
        "feedback": formatted_feedback,
    }


@router.get("/{assessment_id}/risk-analysis")
async def get_risk_analysis(assessment_id: str) -> dict[str, Any]:
    """Return combined findings + retrieval for an assessment in one call."""
    ra = risk_analysis_store.read_risk_analysis(assessment_id)
    retrieval_item = risk_analysis_store.read_retrieval(assessment_id)
    if not ra and not retrieval_item:
        raise HTTPException(status_code=404, detail="No risk analysis data for this assessment")
    return {
        "assessmentId": assessment_id,
        "findings": ra.get("findings", []) if ra else [],
        "feedback": ra.get("feedback", {}) if ra else {},
        "retrieval": retrieval_item.get("retrieval", {}) if retrieval_item else {},
    }


@router.post("/{assessment_id}/risk-analysis")
async def write_risk_analysis(assessment_id: str, request: WriteRiskAnalysisRequest) -> dict[str, Any]:
    """Persist findings (SK=FINDINGS) and optionally retrieval evidence (SK=RETRIEVAL) in one call."""
    logger.info("Writing %d findings for assessment %s", len(request.findings), assessment_id)
    assessment = get_assessment(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    esn = str(assessment.get("esn") or "")
    findings = [item for item in request.findings if isinstance(item, dict)]
    grouped_findings = findings if all(isinstance(item.get("conditions"), list) for item in findings) else _group_by_operation(findings)
    summaries = [
        str(item.get("summary")).strip()
        for item in findings
        if isinstance(item.get("summary"), str) and str(item.get("summary")).strip()
    ]
    summary = "\n\n".join(summaries) if summaries else None

    risk_analysis_store.write_risk_analysis(
        esn=esn,
        assessment_id=assessment_id,
        raw_rows=findings,
        findings=grouped_findings,
        summary=summary,
    )

    retrieval_count = 0
    if isinstance(request.retrieval, dict) and request.retrieval:
        retrieval_count = len(request.retrieval)
        logger.info(
            "Writing retrieval data for %d issues for assessment %s",
            retrieval_count,
            assessment_id,
        )
        risk_analysis_store.write_retrieval(assessment_id, request.retrieval)

    return {
        "assessmentId": assessment_id,
        "findingsCount": len(findings),
        "retrievalIssueCount": retrieval_count,
    }


@router.post("/{assessment_id}/analyze/run", status_code=202)
async def trigger_analysis(
    assessment_id: str,
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """
    Single entry-point for all analysis types.
    The orchestrator routes internally based on `persona`:
            RE → risk evaluation pipeline
      OE → event history pipeline

    Mock (USE_MOCK_ASSESSMENTS=True): runs the corresponding mock synchronously, writes COMPLETE.
    Live (USE_MOCK_ASSESSMENTS=False): writes PENDING, hands off to orchestrator as a background task.
    """
    assessment = get_assessment(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    persona = request.persona.upper()
    if persona not in ("RE", "OE"):
        raise HTTPException(status_code=422, detail="persona must be 'RE' or 'OE'")

    # workflowId may be supplied explicitly (e.g. RE_NARRATIVE for regeneration);
    # fall back to the default analysis workflow for this persona.
    workflow_id = request.workflowId or f"{persona}_DEFAULT"
    is_narrative = workflow_id.endswith("_NARRATIVE")

    if config.USE_MOCK_ASSESSMENTS:
        if is_narrative:
            mock_result: dict = {"narrativeSummary": f"Narrative summary regenerated for assessment {assessment_id} ({persona})."}
        else:
            mock_result = (
                analyze_reliability(assessment_id)
                if persona == "RE"
                else analyze_outage(assessment_id)
            ) or {}
        db_assessments.update_execution_state(assessment_id, workflow_id=workflow_id, workflow_status="COMPLETED")
        _persist_result(assessment_id, workflow_id, persona, mock_result, esn=assessment.get("esn", ""))
    else:
        esn_val = assessment.get("esn", "")
        request_payload = request.model_dump()
        assessment_filters = (assessment.get("filters") or {}) if isinstance(assessment.get("filters"), dict) else {}
        data_types = request_payload.get("dataTypes")
        if not isinstance(data_types, list):
            data_types = assessment_filters.get("dataTypes") if isinstance(assessment_filters.get("dataTypes"), list) else []

        date_from = request_payload.get("dateFrom")
        if date_from is None:
            date_from = assessment_filters.get("fromDate")

        date_to = request_payload.get("dateTo")
        if date_to is None:
            date_to = assessment_filters.get("toDate")

        input_payload = {
            **request_payload,
            "dataTypes": data_types,
            "dateFrom": date_from,
            "dateTo": date_to,
            "filters": {
                "dataTypes": data_types,
                "dateFrom": date_from,
                "dateTo": date_to,
            },
        }
        db_assessments.update_execution_state(assessment_id, workflow_id=workflow_id, workflow_status="IN_QUEUE")
        background_tasks.add_task(
            _invoke_orchestrator,
            assessment_id=assessment_id,
            workflow_id=workflow_id,
            esn=esn_val,
            persona=persona,
            input_payload=input_payload,
        )

    return {"assessmentId": assessment_id, "workflowId": workflow_id, "workflowStatus": "PENDING"}


@router.post("/{assessment_id}/analyze/narrative", status_code=202)
async def trigger_narrative(
    assessment_id: str,
    request: NarrativeRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """
    Trigger A2 (Narrative Summary) after the user has submitted feedback on the
    risk table.  This is a separate invocation from /analyze/run; the risk table
    is already stored in DynamoDB and the orchestrator reads it via the narrative
    assistant.

    Mock (USE_MOCK_ASSESSMENTS=True): returns a stub narrative immediately as COMPLETE.
    Live (USE_MOCK_ASSESSMENTS=False): writes PENDING, hands off to orchestrator.
    """
    assessment = get_assessment(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    persona = request.persona.upper()
    if persona not in ("RE", "OE"):
        raise HTTPException(status_code=422, detail="persona must be 'RE' or 'OE'")

    workflow_id = f"{persona}_NARRATIVE"
    if config.USE_MOCK_ASSESSMENTS:
        mock_result = {"narrativeSummary": f"Narrative summary regenerated for assessment {assessment_id} ({persona})."}
        db_assessments.update_execution_state(assessment_id, workflow_id=workflow_id, workflow_status="COMPLETED")
        _persist_result(assessment_id, workflow_id, persona, mock_result, esn=assessment.get("esn", ""))
    else:
        esn_val = assessment.get("esn", "")
        db_assessments.update_execution_state(assessment_id, workflow_id=workflow_id, workflow_status="IN_QUEUE")
        background_tasks.add_task(
            _invoke_orchestrator,
            assessment_id=assessment_id,
            workflow_id=workflow_id,
            esn=esn_val,
            persona=persona,
            input_payload=request.model_dump(),
        )

    return {"assessmentId": assessment_id, "workflowId": workflow_id, "workflowStatus": "PENDING"}


@router.get("/{assessment_id}/status")
async def get_analysis_status(
    assessment_id: str,
    workflowId: str = Query(...),  # noqa: N803
) -> dict[str, Any]:
    """Single-shot status poll for a specific workflow execution.

    workflowId: RE_DEFAULT | OE_DEFAULT | RE_NARRATIVE | OE_NARRATIVE
    Returns execution-state fields directly so the frontend reads the same
    field names that are stored in DynamoDB.
    """
    record = db_assessments.read_assessment_by_id(assessment_id, workflowId)
    if not record:
        return {
            "assessmentId": assessment_id,
            "workflowId": workflowId,
            "workflowStatus": "PENDING",
        }
    return {
        "assessmentId": assessment_id,
        "workflowId": workflowId,
        "workflowStatus": record.get("workflowStatus", "PENDING"),
        "activeNode": record.get("activeNode"),
        "nodeTimings": record.get("nodeTimings"),
        "errorMessage": record.get("errorMessage"),
    }


@router.put("/{assessment_id}/reliability")
async def update_reliability(assessment_id: str, body: UpdateBody) -> dict[str, Any]:
    assessment = update_reliability_findings(assessment_id, body.to_dict())
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return {"assessment": assessment}


@router.put("/{assessment_id}/outage")
async def update_outage(assessment_id: str, body: UpdateBody) -> dict[str, Any]:
    assessment = update_outage_scope(assessment_id, body.to_dict())
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return {"assessment": assessment}


@router.post("/{assessment_id}/findings/{finding_id}/feedback")
async def post_feedback(
    assessment_id: str,
    finding_id: str,
    feedback: FeedbackRequest,
) -> dict[str, Any]:
    assessment = get_assessment(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    # Feedback is part of the risk-analysis domain record consumed by /findings.
    ra = risk_analysis_store.read_risk_analysis(assessment_id)
    if not ra:
        raise HTTPException(status_code=404, detail="No findings for this assessment")

    payload = {
        # Preserve the existing feedback record ID on updates so that re-saving
        # the same finding always mutates one record rather than generating a new ID.
        "id": (ra.get("feedback") or {}).get(finding_id, {}).get("id")
               or f"feedback_{uuid.uuid4().hex[:8]}",
        "findingId": finding_id,
        "userId": feedback.userId,
        "userName": feedback.userName,
        "feedback": feedback.feedback,
        "feedbackType": feedback.feedbackType,
        "correctness": feedback.correctness,
        "rating": feedback.rating,
        "comments": feedback.comments,
        "helpful": feedback.helpful,
    }
    risk_analysis_store.write_feedback(assessment_id, finding_id, payload)

    # Read-after-write ensures the response matches persisted data format.
    updated = risk_analysis_store.read_risk_analysis(assessment_id) or {}
    stored_feedback = (updated.get("feedback") or {}).get(finding_id)
    if not stored_feedback:
        stored_feedback = {**payload, "submittedAt": datetime.now(tz=timezone.utc).isoformat()}
    return {"findingId": finding_id, "feedback": stored_feedback}
