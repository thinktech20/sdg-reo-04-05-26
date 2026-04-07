"""
Internal routes — accessible only from within the private ECS subnet/ALB.
NOT exposed to the internet-facing load balancer.

PATCH /internal/assessments/{assessment_id}/execution-state
    Called by the orchestrator on every node transition to push live
    workflowStatus, activeNode, and nodeTimings without the data-service
    needing to poll for progress.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from data_service.db import assessments as db_assessments
from data_service.db import risk_analysis as risk_analysis_store

router = APIRouter(prefix="/dataservices/api/v1/internal", tags=["internal"])


class ExecutionStateUpdate(BaseModel):
    """Body accepted by the PATCH endpoint.

    All fields except workflowId are optional so the orchestrator can send
    progress-only updates (workflowStatus omitted) while still identifying
    which workflow row to update.
    """

    workflowId: str  # noqa: N815
    workflowStatus: str | None = None  # noqa: N815
    activeNode: str | None = None  # noqa: N815
    nodeTimings: dict[str, Any] | None = None  # noqa: N815
    errorMessage: str | None = None  # noqa: N815


class RiskEvalSamplePersistRequest(BaseModel):
    """Body accepted by the risk-eval sample persistence endpoint."""

    assessmentId: str | None = None  # noqa: N815
    esn: str | None = None
    payload: dict[str, Any]


def _sample_rows_to_grouped_findings(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        issue_name = str(row.get("Issue name") or f"Sample Risk {index}")
        component = str(row.get("Component and Issue Grouping") or "General")
        risk = str(row.get("Risk") or "Not Mentioned")
        overall_risk = "Light"
        if risk in {"Med", "Medium"}:
            overall_risk = "Medium"
        elif risk in {"Heavy", "IMMEDIATE ACTION"}:
            overall_risk = "Heavy"

        finding_id = f"sample-{index}"
        grouped.append(
            {
                "id": finding_id,
                "name": issue_name,
                "component": component,
                "overallRisk": overall_risk,
                "processDocument": str(row.get("Citation") or "Sample Citation"),
                "reliabilityModelRef": "SIMULATED",
                "description": str(row.get("Condition") or issue_name),
                "conditions": [
                    {
                        "id": f"{finding_id}-condition-1",
                        "findingId": f"{finding_id}-condition-1",
                        "category": component,
                        "condition": str(row.get("Condition") or issue_name),
                        "threshold": str(row.get("Threshold") or ""),
                        "actualValue": str(row.get("Actual Value") or ""),
                        "riskLevel": overall_risk,
                        "dataSource": "SIMULATED",
                        "justification": str(row.get("justification") or ""),
                        "primaryCitation": str(row.get("Citation") or ""),
                        "additionalCitations": [],
                        "status": "complete",
                    }
                ],
            }
        )
    return grouped


@router.patch("/assessments/{assessment_id}/execution-state", status_code=204)
async def patch_execution_state(
    assessment_id: str,
    body: ExecutionStateUpdate,
) -> None:
    """Push a partial execution-state update for an assessment.

    The orchestrator calls this:
    - On each LangGraph node completion  → body carries activeNode + nodeTimings
    - Optional workflow-status carriance → body may include workflowStatus

    Returns 204 No Content on success.
    Returns 404 if the assessment is not known to the execution-state store
    (indicates a stale / replayed push that can be safely ignored).
    """
    record = db_assessments.read_assessment_by_id(assessment_id, body.workflowId)
    if record is None:
        raise HTTPException(status_code=404, detail="Assessment not found in execution-state store")

    db_assessments.update_execution_state(
        assessment_id,
        body.workflowId,
        workflow_status=body.workflowStatus,
        error_message=body.errorMessage,
        active_node=body.activeNode,
        node_timings=body.nodeTimings,
    )


@router.post("/assessments/{assessment_id}/risk-eval-sample", status_code=204)
async def persist_risk_eval_sample(
    assessment_id: str,
    body: RiskEvalSamplePersistRequest,
) -> None:
    """Persist simulated risk-eval sample output for local integration testing."""
    assessment = db_assessments.read_latest_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found")

    payload = body.payload if isinstance(body.payload, dict) else {}
    sample_rows = payload.get("findings")
    if not isinstance(sample_rows, list):
        sample_rows = []
    sample_rows = [row for row in sample_rows if isinstance(row, dict)]

    esn = body.esn or assessment.get("esn") or ""
    grouped_findings = _sample_rows_to_grouped_findings(sample_rows)
    risk_analysis_store.write_risk_analysis(
        esn=str(esn),
        assessment_id=assessment_id,
        raw_rows=sample_rows,
        findings=grouped_findings,
    )
